"""Local MC95A voltage display, served by the Raspberry Pi."""
import argparse
import gzip
import math
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from mc95a import MC95AReader

WEB = Path(__file__).parent / "web"
FILES = {"/": ("mc95a.html", "text/html"),
         "/telemetry.js": ("telemetry.js", "text/javascript"),
         "/mc95a.js": ("mc95a.js", "text/javascript"),
         "/style.css": ("style.css", "text/css")}


def display_snapshot(reader, path):
    query = parse_qs(urlsplit(path).query)
    after = int(query['after'][0]) if 'after' in query else None
    maximum = float(query['spectrum_max_hz'][0]) if 'spectrum_max_hz' in query else None
    if after is not None and after < 0:
        raise ValueError('Invalid history cursor')
    if maximum is not None and (not math.isfinite(maximum) or maximum < 0 or maximum > 100000):
        raise ValueError('Invalid spectrum range')
    return reader.snapshot(after=after, spectrum_max_hz=maximum)


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, reader, **kwargs):
        self.reader = reader
        super().__init__(*args, **kwargs)

    def do_POST(self):
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
        path = urlsplit(self.path).path
        if path == "/api/live":
            try:
                data = display_snapshot(self.reader, self.path)
            except ValueError:
                self.send_error(400, 'Invalid display query')
                return
            content = json.dumps(data, allow_nan=False, separators=(',', ':')).encode()
            mime = "application/json"
        elif path in FILES:
            filename, mime = FILES[path]
            content = (WEB / filename).read_bytes()
        else:
            self.send_error(404)
            return
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

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]) != "200":
            super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--address", type=int, default=0, choices=range(8))
    parser.add_argument("--third", action="store_true", help="add CH0 of the next HAT address")
    parser.add_argument("--start-paused", action="store_true")
    args = parser.parse_args()
    # Fail clearly before starting the server if the Pi library is unavailable.
    import daqhats  # noqa: F401
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
