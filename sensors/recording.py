"""Pi-local CSV recording of validated samples, independent of browser history.

Owned by Measurements; its lock serializes sample writes and start/stop commands.
"""
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import time
import uuid

HEADER = ['received_utc', 'received_ms', 'sequence', 'yaw_deg', 'pitch_deg', 'roll_deg',
          'magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss',
          'acceleration_x_m_s2', 'acceleration_y_m_s2', 'acceleration_z_m_s2',
          'angular_rate_x_rad_s', 'angular_rate_y_rad_s', 'angular_rate_z_rad_s']


class CSVRecording:
    def __init__(self, directory):
        self.directory = Path(directory) if directory is not None else None
        self.file = None
        self.writer = None
        self.path = None
        self.rows = 0
        self.error = None
        self.last_flush = 0

    def snapshot(self):
        return dict(active=self.file is not None, path=self.path, rows=self.rows,
                    error=self.error, available=self.directory is not None)

    def start(self):
        if self.file is not None:
            return
        if self.directory is None:
            raise ValueError('Recording is not configured')
        self.error = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
            path = self.directory / ('vn100-' + stamp + '-' + uuid.uuid4().hex[:8] + '.csv')
            self.file = path.open('x', newline='', encoding='utf-8')
            self.path = str(path.resolve())
            self.rows = 0
            self.writer = csv.writer(self.file)
            self.writer.writerow(HEADER)
            self.file.flush()
            self.last_flush = time.monotonic()
        except OSError as error:
            self._fail(error)

    def write(self, sample):
        if self.file is None:
            return
        try:
            timestamp = datetime.fromtimestamp(sample['received_ms'] / 1000, timezone.utc).isoformat(timespec='milliseconds')
            self.writer.writerow([timestamp, sample['received_ms'], sample['sequence']] +
                                 [v for group in ('attitude', 'magnetic', 'acceleration', 'angular_rate') for v in sample[group]])
            if time.monotonic() - self.last_flush >= .5:
                self.file.flush()
                self.last_flush = time.monotonic()
            self.rows += 1
        except OSError as error:
            self._fail(error)

    def stop(self):
        if self.file is None:
            return
        try:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            self.file = None
        except OSError as error:
            self._fail(error)

    def _fail(self, error):
        self.error = str(error)
        if self.file is not None:
            try:
                self.file.close()
            except OSError:
                pass
        self.file = None
