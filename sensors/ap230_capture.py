"""Finite AP230 capture at 9600 baud using the supplied USB interface box.

Writes ``raw.bin`` (every received byte), ``samples.csv`` (Pi receipt time and
X/Y/Z/|B| in microtesla) and ``summary.json`` into a new UTC-stamped folder.
Run by path on the Pi: ``python3 sensors/ap230_capture.py --port /dev/... [--seconds 30]``.
The session itself is ``ap230_capture_session.AP230Capture``.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

if __name__ == '__main__':  # run by path: make the repository root importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sensors.ap230_capture_session import AP230Capture  # noqa: E402
from sensors.ap230_serial import ROW, parse_row  # noqa: E402,F401  (re-exported)


def parse_args(argv=None):
    """The command line: ``--port``, ``--seconds`` (0-3600] and the ``--output`` folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path.home() / 'bench-data' / 'ap230')
    args = parser.parse_args(argv)
    if not 0 < args.seconds <= 3600:
        parser.error('--seconds must be between 0 and 3600')
    return args


def main(argv=None):
    """Capture into a new UTC-stamped folder; exit 1 on an error or without readings."""
    args = parse_args(argv)
    folder = args.output / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    folder.mkdir(parents=True, exist_ok=False)
    summary = AP230Capture(args.port, args.seconds, folder).run()
    print(json.dumps(summary, indent=2), flush=True)
    if summary['error'] or summary['samples'] == 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
