"""Local MC95A voltage display, served by the Raspberry Pi."""
import argparse
import gzip
import math
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, parse_qs

if __name__ == '__main__':  # run by path: make the repository root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.web_assets import ASSETS, WEB  # noqa: F401  (WEB: the web root, re-exported)
from sensors.mc95a import MC95AReader

FILES = {"/": ("mc95a.html", "text/html"),
         "/telemetry.js": ("telemetry.js", "text/javascript"),
         "/mc95a.js": ("mc95a.js", "text/javascript"),
         "/style.css": ("style.css", "text/css")}


def display_snapshot(reader, path):
    """The reader's display snapshot for the ``after`` and ``spectrum_max_hz`` query of ``path``.

    Raises ValueError for a negative cursor or a spectrum range outside 0-100 kHz.
    """
    query = parse_qs(urlsplit(path).query)
    after = int(query['after'][0]) if 'after' in query else None
    maximum = float(query['spectrum_max_hz'][0]) if 'spectrum_max_hz' in query else None
    if after is not None and after < 0:
        raise ValueError('Invalid history cursor')
    if maximum is not None and (not math.isfinite(maximum) or maximum < 0 or maximum > 100000):
        raise ValueError('Invalid spectrum range')
    return reader.snapshot(after=after, spectrum_max_hz=maximum)


class Handler(BaseHTTPRequestHandler):
    """HTTP handler of the MC95A view: page files, live voltages and pause/resume."""

    def __init__(self, *args, reader, **kwargs):
        """Serve the running MC95A ``reader``."""
        self.reader = reader
        super().__init__(*args, **kwargs)

    def do_POST(self):
        """Pause or resume acquisition; only requests from this GUI's own origin count."""
        if self.headers.get("Origin") != "http://" + self.headers.get("Host", ""):
            self.send_error(403, "Acquisition controls require the same GUI origin")
            return
        if self.path not in ("/api/acquisition/pause", "/api/acquisition/resume"):
            self.send_error(404)
            return
        result = self.reader.set_paused(self.path.endswith("/pause"))
        content = json.dumps(result, allow_nan=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        """Serve the live display snapshot as JSON or one of the page files."""
        path = urlsplit(self.path).path
        if path == "/api/live":
            try:
                data = display_snapshot(self.reader, self.path)
            except ValueError:
                self.send_error(400, 'Invalid display query')
                return
            self._send(json.dumps(data, allow_nan=False, separators=(',', ':')).encode(), "application/json")
        elif path in FILES:
            filename, mime = FILES[path]
            self._send(ASSETS.read(filename), mime)
        else:
            self.send_error(404)

    def _send(self, content, mime):
        """Send ``content`` uncached; JSON is gzip-compressed when the client accepts it."""
        compressed = mime == 'application/json' and 'gzip' in self.headers.get('Accept-Encoding', '')
        if compressed:
            content = gzip.compress(content, compresslevel=1)
        self.send_response(200)
        if compressed:
            self.send_header('Content-Encoding', 'gzip')
        if mime == 'application/json':
            self.send_header('Vary', 'Accept-Encoding')
        self.send_header("Content-Type", mime+"; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):  # noqa: A002  (the base class names it format)
        """Log only unsuccessful requests; routine polls would flood the shared terminal."""
        if len(args) > 1 and str(args[1]) != "200":
            super().log_message(format, *args)


def parse_args():
    """The command line: host, port, HAT address, optional third sensor and start paused."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--address", type=int, default=0, choices=range(8))
    parser.add_argument("--third", action="store_true", help="add CH0 of the next HAT address")
    parser.add_argument("--start-paused", action="store_true")
    return parser.parse_args()


def main():
    """Read the MC95A HAT at ``--address`` and serve its view until Ctrl+C."""
    args = parse_args()
    # Fail clearly before starting the server if the Pi library is unavailable.
    import daqhats  # noqa: F401  # pyright: ignore[reportMissingImports]  (Pi-only library)
    import numpy  # noqa: F401
    reader = MC95AReader(args.address, third=args.third)
    if args.start_paused:
        reader.set_paused(True)
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, reader=reader))
    reader.start()
    print("Inputs:", reader.inputs, flush=True)
    print(f"MC95A GUI: http://mypi.local:{args.port} — CH0 + CH1, IEPE OFF", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping MC95A acquisition", flush=True)
    finally:
        server.server_close()
        reader.stop()


if __name__ == "__main__":
    main()
