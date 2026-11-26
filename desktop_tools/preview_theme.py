#!/usr/bin/env python3
"""Local visual preview with read-only Pi telemetry. No sensor devices are opened.

Run by path: ``python3 desktop_tools/preview_theme.py [--port 8766] [--pi-url URL]``.
The handler lives in ``preview_handler`` and the server in ``preview_server``.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard.connection import load_connection, validate_pi_url  # noqa: E402
from desktop_tools.preview_handler import READ_APIS, ROUTES, Preview  # noqa: E402,F401  (re-exported)
from desktop_tools.preview_server import TTLS, PreviewServer  # noqa: E402,F401  (re-exported)


def parse_args(argv=None):
    """The command line: local ``--port`` and the Pi dashboard ``--pi-url``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--pi-url', default=load_connection()['pi_url'])
    return parser.parse_args(argv)


def main(argv=None):
    """Serve the preview on 127.0.0.1 until Ctrl+C."""
    args = parse_args(argv)
    server = PreviewServer(('127.0.0.1', args.port), Preview, validate_pi_url(args.pi_url))
    server.resolve_pi_host()
    print(f'Local read-only preview: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
