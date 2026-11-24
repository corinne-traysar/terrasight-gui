"""Controlled AP230 serial acquisition for the unified bench dashboard."""
from collections import deque
import fcntl
import os
import select
import termios
import threading
import time
from ap230_capture import parse_row

DEFAULT_DEVICE = '/dev/serial/by-id/usb-APS_Applied_Physics_USB_Interface_Box_AP0D3YPD-if00-port0'


class AP230Reader:
    def __init__(self, device=DEFAULT_DEVICE):
        self.device = device
        self.lock = threading.Lock()
        self.control = threading.Lock()
        self.quit = threading.Event()
        self.thread = None
        self.samples = deque(maxlen=2400)
        self.count = self.rejected = 0
        self.first = self.last = None
        self.error = None

    def start(self):
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

    def stop(self):
        with self.control:
            self.quit.set()
            if self.thread is not None:
                self.thread.join(timeout=2)
        return self.snapshot()

    def accept(self, line, wall, monotonic):
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

    def snapshot(self, after=None):
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
                        latest=self.samples[-1] if self.samples else None,
                        rate_hz=(self.count-1)/(self.last-self.first)
                        if self.count > 1 and self.last > self.first else None)

    def run(self):
        fd = old = None
        try:
            fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            fcntl.ioctl(fd, termios.TIOCEXCL)
            old = termios.tcgetattr(fd)
            attrs = termios.tcgetattr(fd)
            attrs[0] = attrs[1] = attrs[3] = 0
            attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attrs[4] = attrs[5] = termios.B9600
            attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            # In command mode a bare S can remain buffered. Terminate it before
            # Auto-Send, otherwise the next A becomes part of an S...A command.
            os.write(fd, b'S\r')
            started = time.monotonic()
            requests = 0
            next_request = started + 1
            pending = b''
            while not self.quit.is_set():
                if not self.count and time.monotonic() >= next_request:
                    if requests >= 5:
                        raise OSError('No valid XYZ readings after repeated Auto-Send requests. Check sensor power and the interface cable.')
                    os.write(fd, b'A\r')
                    requests += 1
                    next_request = time.monotonic() + 2
                ready, _, _ = select.select([fd], [], [], .2)
                if not ready:
                    continue
                chunk = os.read(fd, 4096)
                if not chunk:
                    raise OSError('Serial device disconnected.')
                pending += chunk.replace(b'\r', b'\n')
                lines = pending.split(b'\n')
                pending = lines.pop()
                wall, mono = time.time(), time.monotonic()
                for line in lines:
                    self.accept(line, wall, mono)
                if len(pending) > 4096:
                    pending = b''
                    with self.lock:
                        self.rejected += 1
        except (OSError, ValueError) as exc:
            with self.lock:
                self.error = str(exc)
        finally:
            if fd is not None:
                try:
                    if old is not None:
                        os.write(fd, b'S\r')
                        termios.tcsetattr(fd, termios.TCSANOW, old)
                except OSError:
                    pass
                os.close(fd)
