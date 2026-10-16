"""Integration tests for the stateful Inventory & Intent Super Over round engine."""

from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app, rooms
from app.rules import Outcome


def test_moves_are_hidden_until_both_players_submit():
    rooms.clear()
    with patch("random.choices", return_value=[Outcome(runs=6)]):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as bowler:
                bowler.send_json({"type": "create_room"})
                created = bowler.receive_json()
                assert created["type"] == "room_created"
                code = created["room_code"]

                with client.websocket_connect("/ws") as batsman:
                    batsman.send_json({"type": "join_room", "room_code": code})
                    joined = batsman.receive_json()
                    assert joined["type"] == "room_joined"
                    assert joined["role"] == "batsman"
                    assert joined["current_phase"] == "SELECT_PROFILE"

                    # Bowler receives player_joined with SELECT_PROFILE phase
                    notification = bowler.receive_json()
                    assert notification["type"] == "player_joined"
                    assert notification["players_connected"] == 2
                    assert notification["current_phase"] == "SELECT_PROFILE"

                    # Bowler selects FAST profile
                    bowler.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    bowler_prof = bowler.receive_json()
                    batsman_prof = batsman.receive_json()

                    assert bowler_prof["type"] == "profile_selected"
                    assert bowler_prof["bowler_profile"] == "FAST"
                    assert bowler_prof["bowler_inventory"]["YORKER"] == 1
                    assert bowler_prof["bowler_inventory"]["HALF_VOLLEY"] == 2
                    assert bowler_prof["current_phase"] == "PLAYING"

                    assert batsman_prof["type"] == "profile_selected"
                    assert batsman_prof["bowler_profile"] == "FAST"

                    # Bowler locks Half-Volley
                    bowler.send_json({"type": "submit_move", "payload": {"move": "HALF_VOLLEY"}})
                    bowler_lock = bowler.receive_json()
                    assert bowler_lock["type"] == "move_locked"
                    assert bowler_lock["waiting_for_opponent"] is True

                    # Batsman picks SLOG_6 → triggers round resolution
                    batsman.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    batsman_lock = batsman.receive_json()
                    assert batsman_lock["type"] == "move_locked"

                    # Both players receive round_result
                    bowler_result = bowler.receive_json()
                    batsman_result = batsman.receive_json()

                    assert bowler_result["type"] == "round_result"
                    assert batsman_result["type"] == "round_result"

                    # Half-Volley vs SLOG_6 → 6 runs, no wicket
                    assert bowler_result["delivery"] == "HALF_VOLLEY"
                    assert bowler_result["shot"] == "SLOG_6"
                    assert bowler_result["runs_scored"] == 6
                    assert bowler_result["wicket"] is False

                    # Half-Volley inventory should be decremented from 2 to 1
                    assert bowler_result["bowler_inventory"]["HALF_VOLLEY"] == 1
                    assert bowler_result["scoreboard"]["runs"] == 6
                    assert bowler_result["scoreboard"]["legal_balls"] == 1


def test_wicket_ends_innings():
    rooms.clear()
    with patch("random.choices", return_value=[Outcome(runs=0, wicket=True)]):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as bowler:
                bowler.send_json({"type": "create_room"})
                code = bowler.receive_json()["room_code"]

                with client.websocket_connect("/ws") as batsman:
                    batsman.send_json({"type": "join_room", "room_code": code})
                    batsman.receive_json()  # room_joined
                    bowler.receive_json()   # player_joined

                    # Bowler selects FAST profile
                    bowler.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    bowler.receive_json()
                    batsman.receive_json()

                    # Yorker vs SLOG_6 → Wicket!
                    bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    bowler.receive_json()  # move_locked

                    batsman.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    batsman.receive_json()  # move_locked

                    result = bowler.receive_json()
                    assert result["wicket"] is True
                    assert result["scoreboard"]["innings_finished"] is True
                    assert result["status"] == "INNINGS_BREAK"


def test_exhausted_delivery_is_rejected():
    rooms.clear()
    with patch("random.choices", return_value=[Outcome(runs=0)]):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as bowler:
                bowler.send_json({"type": "create_room"})
                code = bowler.receive_json()["room_code"]

                with client.websocket_connect("/ws") as batsman:
                    batsman.send_json({"type": "join_room", "room_code": code})
                    batsman.receive_json()
                    bowler.receive_json()

                    bowler.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    bowler.receive_json()
                    batsman.receive_json()

                    # Fast profile only has 1 Yorker
                    # Ball 1: Yorker vs Defend (0 runs)
                    bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    bowler.receive_json()
                    batsman.send_json({"type": "submit_move", "payload": {"move": "DEFEND_0"}})
                    batsman.receive_json()
                    bowler.receive_json()  # round_result
                    batsman.receive_json()

                    # Ball 2: Bowler attempts to bowl Yorker again (0 remaining!)
                    bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    err = bowler.receive_json()
                    assert err["type"] == "error"
                    assert err["code"] == "delivery_exhausted"


def test_submitting_move_before_profile_selection_is_rejected():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                # Bowler tries to submit move before choosing profile
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                err = bowler.receive_json()
                assert err["type"] == "error"
                assert err["code"] == "waiting_for_profile"


def test_batsman_cannot_select_bowler_profile():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                batsman.send_json({"type": "select_profile", "payload": {"profile": "SPIN"}})
                err = batsman.receive_json()
                assert err["type"] == "error"
                assert err["code"] == "unauthorized"


def test_duplicate_move_rejected():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                bowler.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                bowler.receive_json()
                batsman.receive_json()

                # Bowler submits once
                bowler.send_json({"type": "submit_move", "payload": {"move": "BOUNCER"}})
                bowler.receive_json()  # move_locked

                # Bowler tries to submit again
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                error = bowler.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "move_already_submitted"


def test_wrong_role_move_is_rejected():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                bowler.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                bowler.receive_json()
                batsman.receive_json()

                # Batsman tries to submit a bowler delivery
                batsman.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                error = batsman.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "invalid_move"

                # Bowler tries to submit a batsman intent
                bowler.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                bowler_error = bowler.receive_json()
                assert bowler_error["type"] == "error"
                assert bowler_error["code"] == "invalid_move"


def test_full_match_with_inventory_and_role_swap():
    rooms.clear()
    # Ball 1: 4 runs; Ball 2: wicket; Ball 3 (Innings 2): 6 runs (target reached)
    mock_outcomes = [
        [Outcome(runs=4)],
        [Outcome(runs=0, wicket=True)],
        [Outcome(runs=6)],
    ]
    with patch("random.choices", side_effect=mock_outcomes):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as p1:
                p1.send_json({"type": "create_room"})
                code = p1.receive_json()["room_code"]

                with client.websocket_connect("/ws") as p2:
                    p2.send_json({"type": "join_room", "room_code": code})
                    p2.receive_json()
                    p1.receive_json()

                    # --- Innings 1: p1 is bowler, p2 is batsman ---
                    # p1 selects SPIN profile
                    p1.send_json({"type": "select_profile", "payload": {"profile": "SPIN"}})
                    p1.receive_json()
                    p2.receive_json()

                    # Ball 1: p1 bowls OFF_BREAK, p2 plays HIT_4 = 4 runs
                    p1.send_json({"type": "submit_move", "payload": {"move": "OFF_BREAK"}})
                    p1.receive_json()
                    p2.send_json({"type": "submit_move", "payload": {"move": "HIT_4"}})
                    p2.receive_json()
                    p1_res = p1.receive_json()
                    p2.receive_json()
                    assert p1_res["runs_scored"] == 4

                    # Ball 2: p1 bowls GOOGLY, p2 plays SLOG_6 = Wicket! (Innings 1 over at 4 runs)
                    p1.send_json({"type": "submit_move", "payload": {"move": "GOOGLY"}})
                    p1.receive_json()
                    p2.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    p2.receive_json()
                    p1.receive_json()  # round_result
                    p2.receive_json()

                    # Both receive innings_break (Target is 4 + 1 = 5 runs)
                    p1_break = p1.receive_json()
                    p2_break = p2.receive_json()
                    assert p1_break["type"] == "innings_break"
                    assert p1_break["target_score"] == 5
                    assert p1_break["current_phase"] == "SELECT_PROFILE"
                    assert p1_break["role"] == "batsman"  # p1 is now batsman
                    assert p2_break["role"] == "bowler"   # p2 is now bowler

                    # --- Innings 2: p2 is bowler, p1 is batsman ---
                    # p2 selects FAST profile
                    p2.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    p2.receive_json()
                    p1.receive_json()

                    # Ball 1: p2 bowls HALF_VOLLEY, p1 plays SLOG_6 = 6 runs! (Total 6 >= 5 target)
                    p2.send_json({"type": "submit_move", "payload": {"move": "HALF_VOLLEY"}})
                    p2.receive_json()
                    p1.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    p1.receive_json()

                    p1_win = p1.receive_json()
                    p2_win = p2.receive_json()
                    assert p1_win["type"] == "round_result"
                    assert p1_win["status"] == "MATCH_OVER"
                    assert p1_win["scoreboard"]["winner"] == "Team 2"

                    p1_over = p1.receive_json()
                    p2_over = p2.receive_json()
                    assert p1_over["type"] == "match_over"
                    assert p1_over["winner"] == "Team 2"


def test_defending_target_in_second_innings():
    rooms.clear()
    # Ball 1: 4 runs; Ball 2: wicket (Target 5); Innings 2 Ball 1: wicket (Target defended!)
    mock_outcomes = [
        [Outcome(runs=4)],
        [Outcome(runs=0, wicket=True)],
        [Outcome(runs=0, wicket=True)],
    ]
    with patch("random.choices", side_effect=mock_outcomes):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as p1:
                p1.send_json({"type": "create_room"})
                code = p1.receive_json()["room_code"]

                with client.websocket_connect("/ws") as p2:
                    p2.send_json({"type": "join_room", "room_code": code})
                    p2.receive_json()
                    p1.receive_json()

                    # Innings 1: p1 is bowler, selects FAST
                    p1.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    p1.receive_json()
                    p2.receive_json()

                    # Ball 1: Half-Volley vs HIT_4 = 4 runs
                    p1.send_json({"type": "submit_move", "payload": {"move": "HALF_VOLLEY"}})
                    p1.receive_json()
                    p2.send_json({"type": "submit_move", "payload": {"move": "HIT_4"}})
                    p2.receive_json()
                    p1.receive_json()
                    p2.receive_json()

                    # Ball 2: Yorker vs SLOG_6 = Wicket (Innings 1 over at 4 runs, Target = 5)
                    p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    p1.receive_json()
                    p2.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    p2.receive_json()
                    p1.receive_json()
                    p2.receive_json()
                    p1.receive_json()  # innings_break
                    p2.receive_json()  # innings_break

                    # Innings 2: p2 is bowler, selects FAST
                    p2.send_json({"type": "select_profile", "payload": {"profile": "FAST"}})
                    p2.receive_json()
                    p1.receive_json()

                    # Ball 1: p2 bowls Yorker, p1 plays SLOG_6 = Wicket!
                    p2.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    p2.receive_json()
                    p1.send_json({"type": "submit_move", "payload": {"move": "SLOG_6"}})
                    p1.receive_json()

                    p1_over = p1.receive_json()
                    p2_over = p2.receive_json()
                    assert p1_over["status"] == "MATCH_OVER"
                    assert p1_over["scoreboard"]["winner"] == "Team 1"

                    p1_end = p1.receive_json()
                    assert p1_end["type"] == "match_over"
                    assert p1_end["winner"] == "Team 1"
