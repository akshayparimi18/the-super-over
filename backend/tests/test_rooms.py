"""Integration tests for the native WebSocket room workflow."""

from fastapi.testclient import TestClient

from app.main import Room, app, rooms


def test_create_and_join_room_assigns_roles_and_notifies_bowler():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as bowler_ws:
            bowler_ws.send_json({"type": "create_room"})
            created = bowler_ws.receive_json()
            assert created["type"] == "room_created"
            assert created["role"] == "bowler"
            assert len(created["room_code"]) == 6

            with client.websocket_connect("/ws") as batsman_ws:
                batsman_ws.send_json({"type": "join_room", "room_code": created["room_code"]})
                joined = batsman_ws.receive_json()
                assert joined["type"] == "room_joined"
                assert joined["role"] == "batsman"
                assert joined["players_connected"] == 2

                notification = bowler_ws.receive_json()
                assert notification["type"] == "player_joined"
                assert notification["players_connected"] == 2


def test_joining_unknown_room_returns_error():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "join_room", "room_code": "ZZZZZZ"})
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert response["code"] == "room_not_found"


def test_joining_closed_room_returns_error():
    rooms.clear()
    rooms["ZZZZZZ"] = Room(code="ZZZZZZ", closed=True)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"type": "join_room", "room_code": "ZZZZZZ"})
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert response["code"] == "room_not_found"
    rooms.clear()


def test_room_full_error_when_third_player_joins():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()

                # Third player attempts to join
                with client.websocket_connect("/ws") as p3:
                    p3.send_json({"type": "join_room", "room_code": code})
                    err = p3.receive_json()
                    assert err["type"] == "error"
                    assert err["code"] == "room_full"


def test_cannot_join_or_create_room_if_already_in_room():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_room"})
            ws.receive_json()

            # Attempt to create again
            ws.send_json({"type": "create_room"})
            err1 = ws.receive_json()
            assert err1["type"] == "error"
            assert err1["code"] == "already_in_room"

            # Attempt to join another room
            ws.send_json({"type": "join_room", "room_code": "ABCDEF"})
            err2 = ws.receive_json()
            assert err2["type"] == "error"
            assert err2["code"] == "already_in_room"


def test_player_disconnect_notifies_remaining_player_and_cleans_up():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as p1:
            p1.send_json({"type": "create_room"})
            code = p1.receive_json()["room_code"]

            with client.websocket_connect("/ws") as p2:
                p2.send_json({"type": "join_room", "room_code": code})
                p2.receive_json()
                p1.receive_json()

                # p2 disconnects by leaving the context
            # Now p1 receives room_closed
            msg = p1.receive_json()
            assert msg["type"] == "room_closed"
            assert "disconnected" in msg["message"].lower()

    # Room is cleaned up from rooms dict
    assert code not in rooms

