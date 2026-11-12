"""A tiny in-memory HTTP service used as the system under test.

Endpoints
---------
GET    /health        -> {"status": "ok"}
GET    /items         -> list of items
POST   /items         -> create item (requires "name"), returns 201
GET    /items/<id>    -> item or 404
DELETE /items/<id>    -> 204 or 404
POST   /reset         -> clear all items (test isolation helper)
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.items: dict[int, dict] = {}
        self.next_id = 1


def _make_handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output clean
            pass

        def _send(self, code: int, body=None) -> None:
            payload = b"" if body is None else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _item_id(self):
            parts = self.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "items" and parts[1].isdigit():
                return int(parts[1])
            return None

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"status": "ok"})
            if self.path == "/items":
                with state.lock:
                    return self._send(200, list(state.items.values()))
            item_id = self._item_id()
            if item_id is not None:
                with state.lock:
                    item = state.items.get(item_id)
                return self._send(200, item) if item else self._send(404, {"error": "not found"})
            self._send(404, {"error": "unknown route"})

        def do_POST(self):
            if self.path == "/reset":
                with state.lock:
                    state.items.clear()
                    state.next_id = 1
                return self._send(204)
            if self.path == "/items":
                length = int(self.headers.get("Content-Length", 0))
                try:
                    data = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, {"error": "invalid json"})
                name = data.get("name") if isinstance(data, dict) else None
                if not isinstance(name, str) or not name.strip():
                    return self._send(400, {"error": "name is required"})
                with state.lock:
                    item = {"id": state.next_id, "name": name.strip()}
                    state.items[state.next_id] = item
                    state.next_id += 1
                return self._send(201, item)
            self._send(404, {"error": "unknown route"})

        def do_DELETE(self):
            item_id = self._item_id()
            if item_id is None:
                return self._send(404, {"error": "unknown route"})
            with state.lock:
                removed = state.items.pop(item_id, None)
            self._send(204) if removed else self._send(404, {"error": "not found"})

    return Handler


class MockService:
    """Starts the service on a free port in a background thread."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(_State()))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
