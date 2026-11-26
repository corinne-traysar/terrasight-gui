"""One local-network application: VN-100 acquisition and browser display.

Serves the VN-100 page and scripts, a server-sent event stream of measurement
batches (``/api/events``), a diagnostic snapshot (``/api/samples``) and same-origin
CSV recording controls. The unified bench dashboard builds on this handler.
"""

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import time
from urllib.parse import parse_qs, urlsplit

if __name__ == '__main__':  # run by path: make the repository root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.web_assets import ASSETS
from sensors.vn100 import Measurements, VN100Reader

SCRIPTS = ("app.js", "pose.js", "capsule.js", "telemetry.js", "live-calibration.js",
           "live-calibration-sensors.js", "live-calibration-panel.js")
FILES = {"/": ("index.html", "text/html"), "/vn100-reference.png": ("vn100-reference.png", "image/png"),
         "/style.css": ("style.css", "text/css"), **{"/" + name: (name, "text/javascript") for name in SCRIPTS}}


class Handler(BaseHTTPRequestHandler):
    """HTTP handler of the VN-100 view: page files, measurement stream and recording."""

    def __init__(self, *args, measurements, **kwargs):
        """Serve the shared ``measurements`` store of the running reader."""
        self.measurements = measurements
        super().__init__(*args, **kwargs)

    def do_POST(self):
        """Start or stop CSV recording; only requests from this GUI's own origin (and port) count."""
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
        self.send_content(json.dumps(result, allow_nan=False).encode(), "application/json", code)

    def do_GET(self):
        """Serve the event stream, the diagnostic snapshot or one of the page files."""
        url = urlsplit(self.path)
        if url.path == "/api/events":
            self.stream_events()
        elif url.path == "/api/samples":
            self.send_samples(url.query)
        elif url.path in FILES:
            name, content_type = FILES[url.path]
            self.send_content(ASSETS.read(name), content_type)
        else:
            self.send_error(404)

    def send_samples(self, query):
        """The measurement snapshot after the ``after`` sequence of ``query``, as JSON."""
        try:
            after = int(parse_qs(query).get("after", ["0"])[0])
            if after < 0:
                raise ValueError()
        except ValueError:
            self.send_error(400, "after must be a non-negative integer")
            return
        content = json.dumps(self.measurements.snapshot(after), allow_nan=False).encode()
        self.send_content(content, "application/json")

    def send_content(self, content, content_type, code=200):
        """Send ``content`` uncached with status ``code``; text types are marked UTF-8."""
        self.send_response(code)
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
        """Stream new batches every 50 ms on one open connection, so Wi-Fi round trips never gate updates."""
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
        """Log only unsuccessful requests; routine polls would flood the shared terminal."""
        if not args or str(args[1]) != "200":
            super().log_message(format, *args)


def make_server(host, port, measurements):
    """A threading VN-100 server on ``host``:``port`` serving ``measurements``."""
    return ThreadingHTTPServer((host, port), partial(Handler, measurements=measurements))


def main():
    """Read the VN-100 on ``--device`` and serve its view until Ctrl+C."""
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
