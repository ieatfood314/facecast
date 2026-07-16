#!/usr/bin/env python3
"""facecast: tiny static + WebRTC-signaling server (stdlib only).

Serves:
  /          sender page (open on the PC, click Share Screen)
  /vr.html   viewer page (open on the phone, side-by-side for Cardboard)
  /signal    dumb message-queue signaling: POST ?ch=<name> to append,
             GET ?ch=<name> to drain (returns JSON array of messages)
"""
import http.server
import json
import pathlib
import socketserver
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).parent
PORT = 8765

queues: dict[str, list[str]] = {}
last_poll: dict[str, float] = {}  # channel -> last time someone drained it
lock = threading.Lock()

# viewer settings live on the PC: the phone's localStorage is keyed by origin,
# and the viewer URL (tethering IP) changes every session
CFG_PATH = pathlib.Path.home() / ".local" / "state" / "facecast" / "cfg.json"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/cfg":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                json.loads(body)
            except Exception:
                self.send_error(400)
                return
            with lock:
                CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
                CFG_PATH.write_bytes(body)
            self.send_response(204)
            self.end_headers()
            return
        if url.path != "/signal":
            self.send_error(404)
            return
        ch = urllib.parse.parse_qs(url.query).get("ch", ["default"])[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        with lock:
            queues.setdefault(ch, []).append(body)
        try:
            mtype = json.loads(body).get("type", "?")
        except Exception:
            mtype = "?"
        print(f"[signal] {self.client_address[0]} -> {ch}: {mtype}", flush=True)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/status":
            # a peer polling its channel within the last 2s counts as present
            now = time.time()
            with lock:
                data = json.dumps({
                    "sender": now - last_poll.get("to-sender", 0) < 2,
                    "viewer": now - last_poll.get("to-viewer", 0) < 2,
                }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/cfg":
            with lock:
                data = CFG_PATH.read_bytes() if CFG_PATH.exists() else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path != "/signal":
            super().do_GET()
            return
        ch = urllib.parse.parse_qs(url.query).get("ch", ["default"])[0]
        with lock:
            msgs = queues.pop(ch, [])
            last_poll[ch] = time.time()
        data = json.dumps(msgs).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # /signal is polled constantly; logging it would drown everything else
        if args and "/signal" in str(args[0]):
            return
        super().log_message(fmt, *args)


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True

if __name__ == "__main__":
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as srv:
        print(f"facecast listening on http://0.0.0.0:{PORT}")
        print(f"  PC (sender):    http://localhost:{PORT}/")
        print(f"  Phone (viewer): http://<this-machine's-IP>:{PORT}/vr.html")
        srv.serve_forever()
