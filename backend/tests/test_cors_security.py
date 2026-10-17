"""Unit and integration tests for CORS middleware and WebSocket origin security."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


def test_health_check_cors_headers_allowed_origin():
    with TestClient(app) as client:
        response = client.get("/health", headers={"origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert response.headers.get("access-control-allow-credentials") == "true"


def test_health_check_cors_headers_disallowed_origin():
    with TestClient(app) as client:
        response = client.get("/health", headers={"origin": "http://untrusted-site.com"})
        assert response.status_code == 200
        # Disallowed origins do not receive access-control-allow-origin header
        assert "access-control-allow-origin" not in response.headers


def test_websocket_accepts_valid_localhost_origin():
    with TestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
            ws.send_json({"type": "create_room"})
            res = ws.receive_json()
            assert res["type"] == "room_created"


def test_websocket_accepts_valid_127_0_0_1_origin():
    with TestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:5173"}) as ws:
            ws.send_json({"type": "create_room"})
            res = ws.receive_json()
            assert res["type"] == "room_created"


def test_websocket_rejects_unauthorized_origin_with_code_1008():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws", headers={"origin": "http://malicious-site.com"}):
                pass
        assert exc_info.value.code == 1008


def test_websocket_rejects_missing_origin_with_code_1008():
    with TestClient(app) as client:
        # Pass empty origin explicitly to test rejection of missing/empty origin
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws", headers={"origin": ""}):
                pass
        assert exc_info.value.code == 1008
