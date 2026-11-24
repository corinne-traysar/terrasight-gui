"""Finite AP230 capture at 9600 baud using the supplied USB interface box."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import select
import termios
import time

ROW = re.compile(rb'\s*(?:[AD]\s+)?([+-]\d+\.\d{4}) +([+-]\d+\.\d{4}) +([+-]\d+\.\d{4})\s*')


def parse_row(line):
    match = ROW.fullmatch(line)
    if match is None:
        return None
    xyz = [float(value) * 100 for value in match.groups()]  # Gauss to microtesla.
    return [*xyz, math.sqrt(sum(value * value for value in xyz))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path.home() / 'bench-data' / 'ap230')
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600:
        parser.error('--seconds must be between 0 and 3600')
    folder = args.output / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    folder.mkdir(parents=True, exist_ok=False)
    fd = None
    old = None
    requested = False
    count = rejected = byte_count = 0
    failure = None
    first = last = None
    started = time.monotonic()
    print('AP230: 9600 baud, 8N1; raw bytes and XYZ capture: ' + str(folder), flush=True)
    print('Times are Pi receipt times; this is not a measurement accuracy or synchronization test.', flush=True)
    try:
        fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.ioctl(fd, termios.TIOCEXCL)
        old = termios.tcgetattr(fd)
        attrs = termios.tcgetattr(fd)
        attrs[0] = attrs[1] = attrs[3] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[4] = attrs[5] = termios.B9600
        attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        os.write(fd, b'\r')  # Complete any partial command left by a previous reader.
        started = time.monotonic()
        pending = b''
        next_report = started
        with (folder / 'raw.bin').open('xb') as raw, (folder / 'samples.csv').open('x', newline='') as data:
            writer = csv.writer(data)
            writer.writerow(['receipt_unix_s', 'elapsed_s', 'x_uT', 'y_uT', 'z_uT', 'magnitude_uT'])
            while time.monotonic() - started < args.seconds:
                if not requested and not count and time.monotonic() - started >= 2:
                    os.write(fd, b'A\r')
                    requested = True
                    print('Requested Auto-Send (A + carriage return).', flush=True)
                ready, _, _ = select.select([fd], [], [], 0.2)
                if not ready:
                    continue
                chunk = os.read(fd, 4096)
                if not chunk:
                    raise OSError('Serial connection stopped returning bytes.')
                now = time.monotonic()
                wall = time.time()
                byte_count += len(chunk)
                raw.write(chunk)
                pending += chunk.replace(b'\r', b'\n')
                lines = pending.split(b'\n')
                pending = lines.pop()
                if len(pending) > 4096:
                    pending = b''
                    rejected += 1
                for line in lines:
                    if not line.strip():
                        continue
                    values = parse_row(line)
                    if values is None:
                        rejected += 1
                        continue
                    count += 1
                    first = now if first is None else first
                    last = now
                    writer.writerow([f'{wall:.6f}', f'{now-started:.6f}', *values])
                    if now >= next_report:
                        print(f'{count} XYZ readings; X={values[0]:+.2f}, Y={values[1]:+.2f}, '
                              f'Z={values[2]:+.2f}, |B|={values[3]:.2f} uT; '
                              f'{rejected} nonmeasurement lines', flush=True)
                        next_report = now + 1
    except (OSError, KeyboardInterrupt) as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    finally:
        if fd is not None:
            try:
                if requested:
                    os.write(fd, b'S\r')
                if old is not None:
                    termios.tcsetattr(fd, termios.TCSANOW, old)
            except OSError as exc:
                failure = failure or 'Serial cleanup: ' + str(exc)
            os.close(fd)
        summary = dict(port=args.port, baud=9600, samples=count, raw_bytes=byte_count,
                       nonmeasurement_lines=rejected, partial_trailing_bytes=len(pending) if 'pending' in locals() else 0,
                       requested_seconds=args.seconds, elapsed_seconds=time.monotonic()-started,
                       observed_rate_hz=(count-1)/(last-first) if count > 1 and last > first else None,
                       requested_auto_send=requested, error=failure,
                       units='microtesla; ASCII values in Gauss multiplied by 100',
                       timing='Pi serial receipt times; no sensor timestamps or cross-sensor synchronization',
                       accuracy='Not verified')
        (folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    if failure or count == 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
