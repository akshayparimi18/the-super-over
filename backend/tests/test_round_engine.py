"""Integration tests for the Step 3 real-time round engine."""

from fastapi.testclient import TestClient

from app.main import app, rooms


def test_moves_are_hidden_until_both_players_submit():
    rooms.clear()
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

                # Existing player receives join notification
                notification = bowler.receive_json()
                assert notification["type"] == "player_joined"
                assert notification["players_connected"] == 2

                # Bowler locks a secret delivery
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                bowler_lock = bowler.receive_json()
                assert bowler_lock["type"] == "move_locked"
                assert bowler_lock["waiting_for_opponent"] is True

                # Batsman picks a shot → triggers round resolution
                batsman.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                batsman_lock = batsman.receive_json()
                assert batsman_lock["type"] == "move_locked"

                # Both players receive the round result
                bowler_result = bowler.receive_json()
                batsman_result = batsman.receive_json()

                assert bowler_result["type"] == "round_result"
                assert batsman_result["type"] == "round_result"

                # Yorker vs Helicopter → 6 runs, no wicket, no wide
                assert bowler_result["delivery"] == "YORKER"
                assert bowler_result["shot"] == "HELICOPTER"
                assert bowler_result["runs_scored"] == 6
                assert bowler_result["wicket"] is False
                assert bowler_result["wide"] is False

                # Scoreboard should be identical for both players
                assert bowler_result["scoreboard"] == batsman_result["scoreboard"]
                assert bowler_result["scoreboard"]["runs"] == 6
                assert bowler_result["scoreboard"]["legal_balls"] == 1


def test_wide_does_not_count_as_legal_ball():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()  # room_joined
                bowler.receive_json()   # player_joined

                # Bouncer vs Duck → wide (+1 run, no legal ball)
                bowler.send_json({"type": "submit_move", "payload": {"move": "BOUNCER"}})
                bowler.receive_json()  # move_locked

                batsman.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                batsman.receive_json()  # move_locked

                result = bowler.receive_json()
                assert result["type"] == "round_result"
                assert result["wide"] is True
                assert result["runs_scored"] == 1
                assert result["scoreboard"]["legal_balls"] == 0  # wide does not count
                assert result["scoreboard"]["runs"] == 1


def test_wicket_ends_innings():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()  # room_joined
                bowler.receive_json()   # player_joined

                # Yorker vs Duck → wicket
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                bowler.receive_json()

                batsman.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                batsman.receive_json()

                result = bowler.receive_json()
                assert result["wicket"] is True
                assert result["scoreboard"]["innings_finished"] is True


def test_duplicate_move_rejected():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()  # room_joined
                bowler.receive_json()   # player_joined

                # Bowler submits once
                bowler.send_json({"type": "submit_move", "payload": {"move": "SPIN"}})
                bowler.receive_json()  # move_locked

                # Bowler tries to submit again
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                error = bowler.receive_json()
                assert error["type"] == "error"


def test_wrong_role_move_is_rejected_without_crashing():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                batsman.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                error = batsman.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "invalid_move"
                assert "batsman" in error["message"].lower()

                bowler.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                bowler_error = bowler.receive_json()
                assert bowler_error["type"] == "error"
                assert "bowler" in bowler_error["message"].lower()


def test_innings_break_and_role_swap():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler:
            bowler.send_json({"type": "create_room"})
            code = bowler.receive_json()["room_code"]

            with client.websocket_connect("/ws") as batsman:
                batsman.send_json({"type": "join_room", "room_code": code})
                batsman.receive_json()
                bowler.receive_json()

                # Yorker vs Duck → Wicket ends Innings 1 with 0 runs
                bowler.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                bowler.receive_json()
                batsman.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                batsman.receive_json()

                # Both receive round_result
                bowler_res = bowler.receive_json()
                batsman_res = batsman.receive_json()
                assert bowler_res["status"] == "INNINGS_BREAK"
                assert batsman_res["status"] == "INNINGS_BREAK"

                # Both receive innings_break with roles swapped
                bowler_break = bowler.receive_json()
                batsman_break = batsman.receive_json()

                assert bowler_break["type"] == "innings_break"
                assert bowler_break["target_score"] == 1  # 0 runs + 1
                assert bowler_break["current_innings"] == 2
                assert bowler_break["role"] == "batsman"  # swapped!

                assert batsman_break["type"] == "innings_break"
                assert batsman_break["target_score"] == 1
                assert batsman_break["current_innings"] == 2
                assert batsman_break["role"] == "bowler"  # swapped!


def test_full_match_team2_chases_target_successfully():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()  # room_joined
                p1.receive_json()  # player_joined

                # --- Innings 1 ---
                # p1 = bowler, p2 = batsman
                # Ball 1: Yorker vs Helicopter = 6 runs
                p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                p2.receive_json()

                p1_res = p1.receive_json()
                p2_res = p2.receive_json()
                assert p1_res["runs_scored"] == 6

                # Ball 2: Yorker vs Duck = Wicket (Innings 1 over at 6 runs)
                p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                p2.receive_json()

                p1.receive_json()  # round_result
                p2.receive_json()  # round_result

                # Both get innings_break
                p1_break = p1.receive_json()
                p2_break = p2.receive_json()
                assert p1_break["type"] == "innings_break"
                assert p1_break["target_score"] == 7
                assert p1_break["role"] == "batsman"  # p1 is now batsman
                assert p2_break["role"] == "bowler"   # p2 is now bowler

                # --- Innings 2 ---
                # Ball 1: p2 (bowler) bowls YORKER, p1 (batsman) hits HELICOPTER = 6 runs
                p2.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p2.receive_json()
                p1.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                p1.receive_json()

                p1.receive_json()  # round_result (score 6/0, target 7)
                p2.receive_json()  # round_result

                # Ball 2: p2 (bowler) bowls BOUNCER, p1 (batsman) hits SWEEP = 2 runs (Total 8 runs >= 7)
                p2.send_json({"type": "submit_move", "payload": {"move": "BOUNCER"}})
                p2.receive_json()
                p1.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                p1.receive_json()

                p1_win_res = p1.receive_json()
                p2_win_res = p2.receive_json()
                assert p1_win_res["type"] == "round_result"
                assert p1_win_res["status"] == "MATCH_OVER"
                assert p1_win_res["scoreboard"]["winner"] == "Team 2"

                p1_match_over = p1.receive_json()
                p2_match_over = p2.receive_json()
                assert p1_match_over["type"] == "match_over"
                assert p1_match_over["winner"] == "Team 2"
                assert p2_match_over["winner"] == "Team 2"

                # Submitting after match over is rejected
                p1.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                err = p1.receive_json()
                assert err["type"] == "error"
                assert err["code"] == "match_over"


def test_full_match_team1_defends_target_successfully():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()
                p1.receive_json()

                # Innings 1: p1 bowls SPIN, p2 hits SWEEP = 4 runs
                p1.send_json({"type": "submit_move", "payload": {"move": "SPIN"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                p2.receive_json()
                p1.receive_json()
                p2.receive_json()

                # Innings 1 Ball 2: p1 bowls BOUNCER, p2 plays HELICOPTER = Wicket!
                p1.send_json({"type": "submit_move", "payload": {"move": "BOUNCER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                p2.receive_json()
                p1.receive_json()
                p2.receive_json()

                # Innings break (target is 4 + 1 = 5)
                p1_break = p1.receive_json()
                p2_break = p2.receive_json()
                assert p1_break["target_score"] == 5

                # Innings 2: p2 bowls SPIN, p1 hits HELICOPTER = Wicket!
                p2.send_json({"type": "submit_move", "payload": {"move": "SPIN"}})
                p2.receive_json()
                p1.send_json({"type": "submit_move", "payload": {"move": "HELICOPTER"}})
                p1.receive_json()

                p1_res = p1.receive_json()
                p2_res = p2.receive_json()
                assert p1_res["wicket"] is True
                assert p1_res["status"] == "MATCH_OVER"
                assert p1_res["scoreboard"]["winner"] == "Team 1"

                p1_over = p1.receive_json()
                assert p1_over["type"] == "match_over"
                assert p1_over["winner"] == "Team 1"


def test_six_legal_balls_ends_first_innings():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()
                p1.receive_json()

                # 6 deliveries of Yorker vs Sweep (1 run each, no wicket, legal ball)
                for i in range(5):
                    p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                    p1.receive_json()
                    p2.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                    p2.receive_json()
                    res = p1.receive_json()
                    p2.receive_json()
                    assert res.get("status") is None

                # 6th delivery
                p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                p2.receive_json()
                res = p1.receive_json()
                p2.receive_json()
                assert res["status"] == "INNINGS_BREAK"

                p1_break = p1.receive_json()
                p2_break = p2.receive_json()
                assert p1_break["type"] == "innings_break"
                assert p1_break["target_score"] == 7  # 6 runs + 1


def test_match_tie_in_second_innings():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()
                p1.receive_json()

                # Innings 1: Yorker vs Sweep (1 run)
                p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                p2.receive_json()
                p1.receive_json()
                p2.receive_json()

                # Innings 1: Yorker vs Duck (wicket) -> Target = 2
                p1.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p1.receive_json()
                p2.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                p2.receive_json()
                p1.receive_json()
                p2.receive_json()
                p1.receive_json()  # innings_break
                p2.receive_json()  # innings_break

                # Innings 2: p2 bowls Yorker, p1 plays Sweep (1 run) -> score 1
                p2.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p2.receive_json()
                p1.send_json({"type": "submit_move", "payload": {"move": "SWEEP"}})
                p1.receive_json()
                p1.receive_json()
                p2.receive_json()

                # Innings 2: p2 bowls Yorker, p1 plays Duck (wicket) -> score 1 (tied with team 1's score 1)
                p2.send_json({"type": "submit_move", "payload": {"move": "YORKER"}})
                p2.receive_json()
                p1.send_json({"type": "submit_move", "payload": {"move": "DUCK"}})
                p1.receive_json()

                res = p1.receive_json()
                p2.receive_json()
                assert res["status"] == "MATCH_OVER"
                assert res["scoreboard"]["winner"] == "Tie"

                over = p1.receive_json()
                assert over["winner"] == "Tie"

