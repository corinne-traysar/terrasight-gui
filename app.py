"""One local-network application: VN-100 acquisition and browser display."""

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import time
from urllib.parse import parse_qs, urlsplit

from vn100 import Measurements, VN100Reader


WEB = Path(__file__).parent / "web"
FILES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
         "/pose.js": ("pose.js", "text/javascript"),
         "/vn100-reference.png": ("vn100-reference.png", "image/png"),
         "/style.css": ("style.css", "text/css")}


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, measurements, **kwargs):
        self.measurements = measurements
        super().__init__(*args, **kwargs)

    def do_POST(self):
        # Browser controls must originate from this GUI, including its port.
        if self.headers.get("Origin") != "http://" + self.headers.get("Host", ""):
            self.send_error(403, "Recording controls require the same GUI origin")
            return
        action = {"/api/recording/start": self.measurements.start_recording,
                  "/api/recording/stop": self.measurements.stop_recording}.get(self.path)
        if action is None:
            self.send_error(404)
            return
        try:
            result = action()
            code = 500 if result["error"] else 200
        except ValueError as error:
            result, code = {"error": str(error)}, 409
        content = json.dumps(result, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/events":
            self.stream_events()
            return
        if url.path == "/api/samples":
            try:
                after = int(parse_qs(url.query).get("after", ["0"])[0])
                if after < 0:
                    raise ValueError()
            except ValueError:
                self.send_error(400, "after must be a non-negative integer")
                return
            content = json.dumps(self.measurements.snapshot(after), allow_nan=False).encode()
            content_type = "application/json"
        elif url.path in FILES:
            name, content_type = FILES[url.path]
            content = (WEB / name).read_bytes()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type != "image/png" else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def stream_events(self):
        # Keep one connection open: Wi-Fi round trips do not gate every update.
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.connection.settimeout(5)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        after = 0
        try:
            while True:
                snapshot = self.measurements.snapshot(after)
                content = json.dumps(snapshot, allow_nan=False, separators=(",", ":"))
                self.wfile.write(("data: " + content + "\n\n").encode())
                self.wfile.flush()
                after = snapshot["received"]
                time.sleep(.05)
        except (OSError, TimeoutError):
            pass

    def log_message(self, format, *args):
        # Poll requests are routine; keep the shared terminal readable.
        if not args or str(args[1]) != "200":
            super().log_message(format, *args)


def make_server(host, port, measurements):
    return ThreadingHTTPServer((host, port), partial(Handler, measurements=measurements))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="stable /dev/serial/by-id path")
    parser.add_argument("--baud", type=int, default=115200, choices=[115200])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--recording-dir", type=Path, default=Path.home() / "terrasight-bench" / "captures")
    args = parser.parse_args()
    measurements = Measurements(recording_directory=args.recording_dir)
    server = make_server(args.host, args.port, measurements)
    reader = VN100Reader(args.device, measurements, baud=args.baud)
    reader.start()
    print("Terrasight GUI: http://mypi.local:%d (local network)" % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping acquisition and GUI", flush=True)
    finally:
        server.server_close()
        reader.stop()
        measurements.stop_recording()


if __name__ == "__main__":
    main()
