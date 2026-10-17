import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def default_test_origin_header(monkeypatch: pytest.MonkeyPatch):
    """Automatically attach a valid origin header to TestClient.websocket_connect

    calls so integration tests pass the WebSocket origin validation check.
    """
    orig_ws_connect = TestClient.websocket_connect

    def patched_websocket_connect(self, url, subprotocols=None, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        # If origin is explicitly provided (including empty or None in kwargs), keep it as is
        if "origin" not in {k.lower() for k in headers}:
            headers["origin"] = "http://localhost:5173"
        return orig_ws_connect(self, url, subprotocols=subprotocols, headers=headers, **kwargs)

    monkeypatch.setattr(TestClient, "websocket_connect", patched_websocket_connect)
