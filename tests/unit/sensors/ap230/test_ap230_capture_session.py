"""Tests of sensors/ap230_capture_session.py: one finite capture on a fake serial port.

Rows are ASCII gauss; stored values are microtesla (1 G = 100 uT), so
+0.3000 -0.4000 +0.0000 G is (30, -40, 0) uT with |B| = 50 uT (3-4-5 triangle).
"""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from serial_fakes import FakeSerial
from sensors import ap230_serial
from sensors import ap230_capture_session as session
from sensors.ap230_capture_session import AP230Capture

ROW_A = b' A +0.3000 -0.4000 +0.0000\r'


class CaptureTests(unittest.TestCase):
    """A capture that ends when the fake device disconnects (an empty read)."""

    def setUp(self):
        """A temporary capture folder; progress prints are silenced."""
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)
        self.quiet = patch('builtins.print')
        self.quiet.start()

    def tearDown(self):
        """Remove the folder and restore print."""
        self.quiet.stop()
        self.folder.cleanup()

    def capture(self, serial, seconds=5):
        """Run one capture of ``seconds`` against ``serial`` and return its summary."""
        with serial.patch(session, ap230_serial):
            return AP230Capture('/dev/fake', seconds, self.path).run()

    def test_rows_are_written_in_microtesla_until_disconnect(self):
        summary = self.capture(FakeSerial([ROW_A, b'\nnoise\r+0.1000 +0.0000 -0.1000\r', b'']))
        self.assertEqual((summary['samples'], summary['nonmeasurement_lines']), (2, 1))
        self.assertEqual(summary['error'], 'OSError: Serial connection stopped returning bytes.')
        with (self.path / 'samples.csv').open(newline='') as data:
            rows = list(csv.reader(data))
        self.assertEqual(rows[0][2:], ['x_uT', 'y_uT', 'z_uT', 'magnitude_uT'])
        self.assertEqual([float(v) for v in rows[1][2:]], [30.0, -40.0, 0.0, 50.0])
        self.assertEqual((self.path / 'raw.bin').read_bytes(), ROW_A + b'\nnoise\r+0.1000 +0.0000 -0.1000\r')

    def test_summary_file_matches_the_returned_summary(self):
        summary = self.capture(FakeSerial([ROW_A, b'']))
        written = json.loads((self.path / 'summary.json').read_text())
        self.assertEqual(written['samples'], summary['samples'])
        self.assertEqual((written['baud'], written['raw_bytes']), (9600, len(ROW_A)))

    def test_port_is_configured_raw_9600_and_restored(self):
        serial = FakeSerial([ROW_A, b''])
        self.capture(serial)
        raw = serial.settings[0]
        self.assertEqual((raw[4], raw[5]), (serial.termios.B9600,) * 2)
        self.assertEqual(raw[2], serial.termios.CS8 | serial.termios.CREAD | serial.termios.CLOCAL)
        self.assertEqual(serial.settings[-1], [1, 1, 1, 1, 1, 1, [1] * 32], 'old settings restored')
        self.assertEqual((serial.written[0], serial.closed), (b'\r', 1))

    def test_open_failure_is_reported_without_closing(self):
        serial = FakeSerial(open_error=OSError('no such device'))
        summary = self.capture(serial)
        self.assertEqual(summary['error'], 'OSError: no such device')
        self.assertEqual((summary['samples'], serial.closed), (0, 0))

    def test_overlong_partial_line_is_dropped_and_counted(self):
        summary = self.capture(FakeSerial([b'x' * 4097, b'']))
        self.assertEqual((summary['nonmeasurement_lines'], summary['partial_trailing_bytes']), (1, 0))

    def test_rate_needs_two_readings_over_time(self):
        capture = AP230Capture('/dev/fake', 1, self.path)
        self.assertIsNone(capture.rate_hz())
        capture.count, capture.first, capture.last = 11, 100.0, 102.0
        rate = capture.rate_hz()
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate or 0.0, 5.0)  # 10 intervals in 2 s


if __name__ == '__main__':
    unittest.main()
