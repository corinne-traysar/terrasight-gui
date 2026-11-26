"""One finite AP230 capture session: raw bytes, parsed X/Y/Z rows and a summary.

Readings are stored in microtesla with Pi receipt times (row format and port
setup: ``ap230_serial``). ``ap230_capture`` is the command line.
"""
import csv
import json
import os
import select
import termios
import time

from sensors.ap230_serial import configure_port, parse_row


class AP230Capture:
    """One finite capture from ``port`` for ``seconds`` into ``folder``; ``run`` returns the summary."""

    def __init__(self, port, seconds, folder):
        """Prepare a capture; nothing is opened until ``run``."""
        self.port, self.seconds, self.folder = port, seconds, folder
        self.fd = self.old = None
        self.requested = False
        self.count = self.rejected = self.byte_count = 0
        self.failure = None
        self.first = self.last = None
        self.started = time.monotonic()
        self.pending = b''

    def run(self):
        """Capture, restore the port and write ``summary.json``; errors end up in the summary."""
        print('AP230: 9600 baud, 8N1; raw bytes and XYZ capture: ' + str(self.folder), flush=True)
        print('Times are Pi receipt times; this is not a measurement accuracy or synchronization test.', flush=True)
        try:
            self._capture(self._open())
        except (OSError, KeyboardInterrupt) as exc:
            self.failure = type(exc).__name__ + ': ' + str(exc)
        finally:
            self._close()
            summary = self.summary()
            (self.folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        return summary

    def _open(self):
        """Open the port exclusively as raw 9600 8N1, end any partial command; return its fd."""
        fd = self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.old = configure_port(fd)
        os.write(fd, b'\r')  # Complete any partial command left by a previous reader.
        return fd

    def _capture(self, fd):
        """Read ``fd`` until ``seconds`` have passed, writing raw bytes and parsed rows."""
        self.started = time.monotonic()
        next_report = [self.started]
        with (self.folder / 'raw.bin').open('xb') as raw, (self.folder / 'samples.csv').open('x', newline='') as data:
            writer = csv.writer(data)
            writer.writerow(['receipt_unix_s', 'elapsed_s', 'x_uT', 'y_uT', 'z_uT', 'magnitude_uT'])
            while time.monotonic() - self.started < self.seconds:
                self._request_auto_send(fd)
                ready, _, _ = select.select([fd], [], [], 0.2)
                if ready:
                    self._receive(os.read(fd, 4096), raw, writer, next_report)

    def _request_auto_send(self, fd):
        """Ask for Auto-Send once, when no reading has arrived after 2 s."""
        if not self.requested and not self.count and time.monotonic() - self.started >= 2:
            os.write(fd, b'A\r')
            self.requested = True
            print('Requested Auto-Send (A + carriage return).', flush=True)

    def _receive(self, chunk, raw, writer, next_report):
        """Store ``chunk`` and write every complete line; an empty chunk means disconnected."""
        if not chunk:
            raise OSError('Serial connection stopped returning bytes.')
        now, wall = time.monotonic(), time.time()
        self.byte_count += len(chunk)
        raw.write(chunk)
        self.pending += chunk.replace(b'\r', b'\n')
        lines = self.pending.split(b'\n')
        self.pending = lines.pop()
        if len(self.pending) > 4096:
            self.pending = b''
            self.rejected += 1
        for line in lines:
            if line.strip():
                self._row(line, now, wall, writer, next_report)

    def _row(self, line, now, wall, writer, next_report):
        """Write one reading (or count a non-measurement line) and report progress once a second."""
        values = parse_row(line)
        if values is None:
            self.rejected += 1
            return
        self.count += 1
        self.first = now if self.first is None else self.first
        self.last = now
        writer.writerow([f'{wall:.6f}', f'{now-self.started:.6f}', *values])
        if now >= next_report[0]:
            print(f'{self.count} XYZ readings; X={values[0]:+.2f}, Y={values[1]:+.2f}, '
                  f'Z={values[2]:+.2f}, |B|={values[3]:.2f} uT; '
                  f'{self.rejected} nonmeasurement lines', flush=True)
            next_report[0] = now + 1

    def _close(self):
        """Stop Auto-Send, restore the port settings and close it."""
        if self.fd is None:
            return
        try:
            if self.requested:
                os.write(self.fd, b'S\r')
            if self.old is not None:
                termios.tcsetattr(self.fd, termios.TCSANOW, self.old)
        except OSError as exc:
            self.failure = self.failure or 'Serial cleanup: ' + str(exc)
        os.close(self.fd)

    def rate_hz(self):
        """Readings per second between the first and last reading, or None with fewer than two."""
        if self.first is None or self.last is None or self.count < 2 or self.last <= self.first:
            return None
        return (self.count - 1) / (self.last - self.first)

    def summary(self):
        """Counts, timing and the error (if any) of this capture."""
        return dict(port=self.port, baud=9600, samples=self.count, raw_bytes=self.byte_count,
                    nonmeasurement_lines=self.rejected, partial_trailing_bytes=len(self.pending),
                    requested_seconds=self.seconds, elapsed_seconds=time.monotonic()-self.started,
                    observed_rate_hz=self.rate_hz(), requested_auto_send=self.requested, error=self.failure,
                    units='microtesla; ASCII values in Gauss multiplied by 100',
                    timing='Pi serial receipt times; no sensor timestamps or cross-sensor synchronization',
                    accuracy='Not verified')
