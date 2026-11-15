"""VN-100 VNYMR acquisition. No sensor configuration commands are transmitted."""

from collections import deque
import fcntl
import math
import os
import select
import termios
import threading
import time
import uuid

from recording import CSVRecording


GROUPS = ("attitude", "magnetic", "acceleration", "angular_rate")


def decode_packet(line):
    """Return the four XYZ/YPR groups, or raise ValueError for invalid VNYMR."""
    try:
        payload, checksum = line.strip(b"\r\n")[1:].split(b"*", 1)
        if not line.startswith(b"$VNYMR,") or len(checksum) != 2:
            raise ValueError("not a complete VNYMR packet")
        expected = 0
        for byte in payload:
            expected ^= byte
        if expected != int(checksum, 16):
            raise ValueError("checksum mismatch")
        fields = payload.split(b",")[1:]
        values = [float(value) for value in fields]
        if len(values) != 12 or not all(math.isfinite(v) for v in values):
            raise ValueError("expected 12 finite measurements")
        return {name: values[i * 3:i * 3 + 3] for i, name in enumerate(GROUPS)}
    except (IndexError, TypeError, OverflowError) as error:
        raise ValueError("malformed packet") from error


class PacketStream:
    """Reassemble arbitrary serial chunks, bounded even on malformed input."""

    def __init__(self):
        self.pending = b""

    def feed(self, chunk):
        self.pending += chunk
        lines = []
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            # Recover from an initial partial packet or noise before a new header.
            start = line.rfind(b"$VNYMR,")
            if start >= 0:
                lines.append(line[start:])
        if len(self.pending) > 1024:
            self.pending = b""
        return lines


class Measurements:
    """Thread-safe bounded history and current connection state."""

    def __init__(self, capacity=2400, stale_after=1.0, recording_directory=None):
        self.recording = CSVRecording(recording_directory)
        self.samples = deque(maxlen=capacity)
        self.capacity = capacity
        self.stale_after = stale_after
        self.session = uuid.uuid4().hex
        self.lock = threading.Lock()
        self.sequence = 0
        self.opened = False
        self.error = None
        self.last_received = None
        self.rejected = 0

    def connection(self, opened, error=None):
        with self.lock:
            if opened and not self.opened:
                self.last_received = None
            self.opened = opened
            self.error = error

    def reject(self):
        with self.lock:
            self.rejected += 1

    def add(self, values):
        with self.lock:
            self.sequence += 1
            self.last_received = time.monotonic()
            sample = dict(values, sequence=self.sequence, received_ms=time.time() * 1000)
            self.samples.append(sample)
            self.recording.write(sample)

    def start_recording(self):
        with self.lock:
            if not self.recording.snapshot()['active']:
                if not self.opened or self.last_received is None or time.monotonic() - self.last_received > self.stale_after:
                    raise ValueError('Wait for live sensor data before recording')
                self.recording.start()
                print("CSV recording: " + str(self.recording.path), flush=True)
            return self.recording.snapshot()

    def stop_recording(self):
        with self.lock:
            was_active = self.recording.file is not None
            self.recording.stop()
            if was_active:
                print("CSV recording stopped: %s (%d rows)" % (self.recording.path, self.recording.rows), flush=True)
            return self.recording.snapshot()

    def snapshot(self, after=0):
        with self.lock:
            age = None if self.last_received is None else time.monotonic() - self.last_received
            state = "disconnected" if not self.opened else (
                "waiting" if age is None else ("stale" if age > self.stale_after else "live"))
            oldest = self.samples[0]["sequence"] if self.samples else 0
            return {
                "recording": self.recording.snapshot(),
                "session": self.session,
                "status": state,
                "error": self.error,
                "age_seconds": age,
                "received": self.sequence,
                "rejected": self.rejected,
                "history_truncated": bool(after and oldest > after + 1),
                "latest": self.samples[-1] if self.samples else None,
                "samples": [sample for sample in self.samples if sample["sequence"] > after],
            }


def open_serial(path, baud):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        # Readers in this application cannot accidentally split the byte stream.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = termios.tcgetattr(fd)
        settings[0] = 0
        settings[1] = 0
        settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        settings[3] = 0
        settings[4] = settings[5] = getattr(termios, "B" + str(baud))
        settings[6][termios.VMIN] = 0
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        termios.tcflush(fd, termios.TCIFLUSH)
        return fd
    except BaseException:
        os.close(fd)
        raise


class VN100Reader:
    def __init__(self, path, measurements, baud=115200, retry_seconds=1.0):
        self.path = path
        self.measurements = measurements
        self.baud = baud
        self.retry_seconds = retry_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="vn100-reader", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=3)

    def run(self):
        while not self.stop_event.is_set():
            fd = None
            try:
                fd = open_serial(self.path, self.baud)
                stream = PacketStream()
                self.measurements.connection(True)
                print("VN-100 serial connection opened", flush=True)
                while not self.stop_event.is_set():
                    ready, _, _ = select.select([fd], [], [], 0.2)
                    if not ready:
                        continue
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        raise OSError("serial device disconnected")
                    for line in stream.feed(chunk):
                        try:
                            values = decode_packet(line)
                        except ValueError:
                            self.measurements.reject()
                        else:
                            self.measurements.add(values)
            except (OSError, termios.error) as error:
                self.measurements.connection(False, str(error))
                print("VN-100 unavailable: " + str(error), flush=True)
            finally:
                if fd is not None:
                    os.close(fd)
            self.stop_event.wait(self.retry_seconds)
        self.measurements.connection(False)
