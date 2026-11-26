"""Start/stop control of the VN-100 reader inside the unified bench dashboard.

The bench dashboard starts with every instrument stopped. ``VNControl`` opens
and closes the VN-100 serial reader on request; ``BenchMeasurements`` reports
``stopped`` while no reader runs, so the browser never shows stale data as live.
"""
import threading

from sensors.vn100 import Measurements, VN100Reader


class BenchMeasurements(Measurements):
    """VN-100 measurements whose status reads ``stopped`` while acquisition is off."""

    acquisition_running = False

    def snapshot(self, after=0):
        """The measurement snapshot after sequence ``after``, marked stopped when off."""
        data = super().snapshot(after)
        if not self.acquisition_running:
            data['status'] = 'stopped'
        return data


class VNControl:
    """Owns the VN-100 reader of the bench dashboard; start and stop are idempotent."""

    def __init__(self, device, measurements):
        """Control the serial ``device`` path, writing samples to ``measurements``."""
        self.device = device
        self.measurements = measurements
        self.reader = None
        self.lock = threading.Lock()

    def start(self):
        """Start the reader if it is not running; returns the control state."""
        with self.lock:
            if self.reader is None:
                self.measurements.acquisition_running = True
                self.reader = VN100Reader(self.device, self.measurements)
                self.reader.start()
        return {'running': True, 'device': self.device}

    def stop(self):
        """Stop the reader and any recording; returns the control state."""
        with self.lock:
            if self.reader is not None:
                self.reader.stop()
                self.reader = None
            self.measurements.stop_recording()
            self.measurements.acquisition_running = False
            self.measurements.connection(False, 'VN-100 acquisition stopped')
        return {'running': False, 'device': self.device}

    def snapshot(self):
        """Whether the reader runs, and its device path."""
        with self.lock:
            return {'running': self.reader is not None, 'device': self.device}
