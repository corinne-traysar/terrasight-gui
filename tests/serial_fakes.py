"""A fake serial device for the sensor readers, usable on any operating system.

``FakeSerial.patch(*modules)`` replaces the ``os``, ``select``, ``termios`` and
``fcntl`` names inside the given sensor modules only, so nothing else in the test run
is affected. Reads return the queued chunks in order; ``b''`` is a disconnect,
and an empty queue means "no bytes ready yet" (select times out).
"""
import contextlib
import threading
from types import SimpleNamespace
from unittest.mock import patch

FD = 42


class FakeSerial:
    """One fake serial port: queued input chunks, recorded writes and settings."""

    def __init__(self, chunks=(), open_error=None):
        """Queue ``chunks`` for reading; ``open_error`` is raised by os.open when given."""
        self.chunks = list(chunks)
        self.open_error = open_error
        self.written = []
        self.settings = []
        self.opened = []
        self.closed = 0
        self.lock = threading.Lock()
        self.os = SimpleNamespace(open=self._open, read=self._read, write=self._write, close=self._close,
                                  O_RDWR=2, O_NOCTTY=256, O_NONBLOCK=2048)
        self.select = SimpleNamespace(select=self._select)
        self.termios = SimpleNamespace(tcgetattr=lambda fd: [1, 1, 1, 1, 1, 1, [1] * 32],
                                       tcsetattr=lambda fd, when, attrs: self.settings.append(attrs),
                                       tcflush=lambda fd, queue: None, error=OSError, TIOCEXCL=0x540C,
                                       CS8=48, CREAD=128, CLOCAL=2048, B9600=13, B115200=4098,
                                       VMIN=6, VTIME=5, TCSANOW=0, TCIFLUSH=0)
        self.fcntl = SimpleNamespace(ioctl=lambda fd, request: None, flock=lambda fd, operation: None,
                                     LOCK_EX=2, LOCK_NB=4)

    def _open(self, path, flags):
        """Open ``path``; raise the configured error instead when there is one."""
        if self.open_error is not None:
            raise self.open_error
        self.opened.append(path)
        return FD

    def _select(self, read, write, error, timeout):
        """Ready when a chunk is queued; otherwise wait briefly like a select timeout."""
        with self.lock:
            ready = bool(self.chunks)
        if not ready:
            threading.Event().wait(min(timeout, .01))
        return (read if ready else []), [], []

    def _read(self, fd, size):
        """The next queued chunk (b'' when the queue is empty: a disconnect)."""
        with self.lock:
            return self.chunks.pop(0) if self.chunks else b''

    def _write(self, fd, data):
        """Record ``data`` and report it written."""
        self.written.append(data)
        return len(data)

    def _close(self, fd):
        """Count closes."""
        self.closed += 1

    def feed(self, *chunks):
        """Queue more input while a reader runs."""
        with self.lock:
            self.chunks.extend(chunks)

    def patch(self, *modules):
        """Context manager replacing the os, select, termios and fcntl each of ``modules`` imports."""
        stack = contextlib.ExitStack()
        for module in modules:
            for name in ('os', 'select', 'termios', 'fcntl'):
                if hasattr(module, name):
                    stack.enter_context(patch.object(module, name, getattr(self, name)))
        return stack
