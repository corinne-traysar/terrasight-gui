"""Controlled AP230 serial acquisition for the unified bench dashboard.

``AP230Reader`` runs one background thread that opens the interface box at
9600 baud 8N1, asks for Auto-Send and keeps the last 2,400 readings (microtesla,
Pi receipt times). Start and stop come from the dashboard; errors stop the thread
and are reported in ``snapshot``.
"""
from collections import deque
import os
import select
import termios
import threading
import time
from typing import Any

from sensors.ap230_serial import configure_port, parse_row

DEFAULT_DEVICE = '/dev/serial/by-id/usb-APS_Applied_Physics_USB_Interface_Box_AP0D3YPD-if00-port0'


class AP230Reader:
    """AP230 acquisition thread with a bounded, thread-safe history of readings."""

    def __init__(self, device=DEFAULT_DEVICE):
        """Read ``device`` once started; nothing is opened yet."""
        self.device = device
        self.lock = threading.Lock()
        self.control = threading.Lock()
        self.quit = threading.Event()
        self.thread: threading.Thread | None = None
        self.samples = deque(maxlen=2400)
        self.count = self.rejected = 0
        self.first: float | None = None
        self.last: float | None = None
        self.error: str | None = None

    def start(self) -> dict[str, Any]:
        """Start a fresh acquisition (history cleared) unless one is running; return the snapshot."""
        with self.control:
            if self.thread is None or not self.thread.is_alive():
                with self.lock:
                    self.samples.clear()
                    self.count = self.rejected = 0
                    self.first = self.last = None
                    self.error = None
                self.quit.clear()
                self.thread = threading.Thread(target=self.run, daemon=True, name='ap230')
                self.thread.start()
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        """Stop the acquisition thread (waiting up to 2 s); return the snapshot."""
        with self.control:
            self.quit.set()
            if self.thread is not None:
                self.thread.join(timeout=2)
        return self.snapshot()

    def accept(self, line, wall, monotonic):
        """Store one received line as a reading, or count it when it is not one (blank lines are ignored)."""
        values = parse_row(line)
        with self.lock:
            if values is None:
                if line.strip():
                    self.rejected += 1
                return
            self.count += 1
            self.first = monotonic if self.first is None else self.first
            self.last = monotonic
            self.samples.append([wall, *values])

    def snapshot(self, after=None) -> dict[str, Any]:
        """Status, counts and the readings after count ``after`` (all kept readings when None or unknown)."""
        with self.lock:
            running = self.thread is not None and self.thread.is_alive()
            age = None if self.last is None else time.monotonic() - self.last
            status = ('error' if self.error else 'stopped' if not running else
                      'waiting' if age is None else 'stale' if age > 2 else 'live')
            samples = list(self.samples)
            start_count = self.count - len(samples) + 1
            if after is not None and 0 <= after <= self.count:
                samples = samples[max(0, after - start_count + 1):]
            return dict(status=status, running=running, device=self.device, baud=9600,
                        count=self.count, nonmeasurement_lines=self.rejected,
                        age_s=age, error=self.error, samples=samples,
                        stream_id=self.first, history_start_count=start_count,
                        samples_start_count=self.count-len(samples)+1,
                        latest=self.samples[-1] if self.samples else None, rate_hz=self._rate_hz())

    def _rate_hz(self) -> float | None:
        """Readings per second between the first and last reading (call with the lock held)."""
        if self.first is None or self.last is None or self.count < 2 or self.last <= self.first:
            return None
        return (self.count - 1) / (self.last - self.first)

    def run(self):
        """Thread body: open the port, read until stopped; an error is kept for ``snapshot``."""
        fd = old = None
        try:
            fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            old = configure_port(fd)
            # In command mode a bare S can remain buffered. Terminate it before
            # Auto-Send, otherwise the next A becomes part of an S...A command.
            os.write(fd, b'S\r')
            self._read(fd)
        except (OSError, ValueError) as exc:
            with self.lock:
                self.error = str(exc)
        finally:
            if fd is not None:
                self._close(fd, old)

    def _read(self, fd):
        """Request Auto-Send until readings arrive, then store complete lines until stopped."""
        requests, next_request, pending = 0, time.monotonic() + 1, b''
        while not self.quit.is_set():
            if not self.count and time.monotonic() >= next_request:
                if requests >= 5:
                    raise OSError('No valid XYZ readings after repeated Auto-Send requests. Check sensor power and the interface cable.')
                os.write(fd, b'A\r')
                requests, next_request = requests + 1, time.monotonic() + 2
            ready, _, _ = select.select([fd], [], [], .2)
            if ready:
                pending = self._receive(os.read(fd, 4096), pending)

    def _receive(self, chunk, pending) -> bytes:
        """Accept every complete line of ``pending`` + ``chunk``; return the incomplete rest."""
        if not chunk:
            raise OSError('Serial device disconnected.')
        lines = (pending + chunk.replace(b'\r', b'\n')).split(b'\n')
        pending = lines.pop()
        wall, mono = time.time(), time.monotonic()
        for line in lines:
            self.accept(line, wall, mono)
        if len(pending) > 4096:
            with self.lock:
                self.rejected += 1
            return b''
        return pending

    @staticmethod
    def _close(fd, old):
        """Stop Auto-Send and restore the settings (when configured), then close the port."""
        try:
            if old is not None:
                os.write(fd, b'S\r')
                termios.tcsetattr(fd, termios.TCSANOW, old)
        except OSError:
            pass
        os.close(fd)
