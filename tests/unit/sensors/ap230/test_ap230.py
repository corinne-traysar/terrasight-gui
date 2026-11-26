"""Tests of sensors/ap230.py: the AP230 reader on a fake serial port and, on POSIX, a pseudo-terminal.

Rows are ASCII gauss stored as microtesla: +0.3000 -0.4000 +0.0000 G is (30, -40, 0) uT, |B| 50 uT.
"""
import os
try:
    import pty
except (ImportError, NameError):  # Windows: pty and tty are POSIX-only (tty fails with NameError)
    pty = None
import select
import threading
import time
import unittest

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from serial_fakes import FakeSerial
from sensors import ap230_serial
from sensors import ap230
from sensors.ap230 import AP230Reader

SPLIT_ROWS = [b'garbled\r\n A +0.3000 -0.', b'4000 +0.0000\r\n+0.1000 +0.2000 +0.3000\r\n']


@unittest.skipIf(pty is None, 'pseudo-terminals need a POSIX machine')
class AP230Tests(unittest.TestCase):
    """The reader on a real pseudo-terminal."""

    def test_real_serial_framing_start_and_stop(self):
        assert pty is not None
        master, slave = pty.openpty()
        reader = AP230Reader(os.ttyname(slave))
        try:
            reader.start()
            ready, _, _ = select.select([master], [], [], 3)
            self.assertTrue(ready, 'Reader did not clear the partial command')
            self.assertEqual(os.read(master, 100), b'S\r')
            ready, _, _ = select.select([master], [], [], 3)
            self.assertTrue(ready, 'Reader did not request Auto-Send')
            self.assertEqual(os.read(master, 100), b'A\r')
            os.write(master, SPLIT_ROWS[0])
            time.sleep(.02)
            os.write(master, SPLIT_ROWS[1])
            deadline = time.monotonic()+2
            while reader.snapshot()['count'] < 2 and time.monotonic() < deadline:
                time.sleep(.01)
            data = reader.snapshot()
            self.assertEqual(data['status'], 'live')
            self.assertEqual(data['count'], 2)
            self.assertEqual(data['nonmeasurement_lines'], 1)
            self.assertEqual(data['samples'][0][1:], [30, -40, 0, 50])
            self.assertEqual(data['latest'][1:4], [10,20,30])
            self.assertEqual(reader.stop()['status'], 'stopped')
            self.assertFalse(reader.snapshot()['running'])
            self.assertEqual(os.read(master, 100), b'S\r')
        finally:
            reader.stop()
            os.close(master)
            os.close(slave)


class SnapshotTests(unittest.TestCase):
    """Status derived from the age of the last reading, and the sample cursor."""

    def test_stale_measurements_are_not_live(self):
        reader = AP230Reader()
        release = threading.Event()
        reader.thread = threading.Thread(target=release.wait, daemon=True)  # a running acquisition
        reader.thread.start()
        try:
            reader.accept(b'+0.1000 +0.2000 +0.3000', time.time() - 5, time.monotonic() - 5)
            self.assertEqual(reader.snapshot()['status'], 'stale')
        finally:
            release.set()

    def test_snapshot_after_a_count_returns_only_newer_samples(self):
        reader = AP230Reader()
        for value in (b'+0.1000', b'+0.2000', b'+0.3000'):
            reader.accept(value + b' +0.0000 +0.0000', 0.0, 1.0)
        self.assertEqual([s[1] for s in reader.snapshot(after=1)['samples']], [20.0, 30.0])
        self.assertEqual(len(reader.snapshot(after=99)['samples']), 3, 'an unknown cursor returns everything')


class FakeSerialTests(unittest.TestCase):
    """The reader thread on a fake port: framing, errors and cleanup (runs on any OS)."""

    def run_reader(self, serial):
        """Run a reader against ``serial`` until its thread ends; return the reader."""
        reader = AP230Reader('/dev/fake')
        with serial.patch(ap230, ap230_serial):
            reader.start()
            deadline = time.monotonic() + 3
            while reader.snapshot()['running'] and time.monotonic() < deadline:
                time.sleep(.01)
        return reader

    def test_rows_split_across_chunks_are_reassembled(self):
        data = self.run_reader(FakeSerial([*SPLIT_ROWS, b''])).snapshot()
        self.assertEqual((data['count'], data['nonmeasurement_lines']), (2, 1))
        self.assertEqual(data['samples'][0][1:], [30, -40, 0, 50])
        self.assertEqual((data['status'], data['error']), ('error', 'Serial device disconnected.'))

    def test_port_is_configured_and_restored_on_exit(self):
        serial = FakeSerial([SPLIT_ROWS[1], b''])
        self.run_reader(serial)
        self.assertEqual(serial.written, [b'S\r', b'S\r'], 'clear the command at start and stop Auto-Send at exit')
        self.assertEqual(serial.settings[0][4], serial.termios.B9600)
        self.assertEqual(serial.settings[-1], [1, 1, 1, 1, 1, 1, [1] * 32])
        self.assertEqual(serial.closed, 1)

    def test_open_failure_is_reported(self):
        data = self.run_reader(FakeSerial(open_error=OSError('no such device'))).snapshot()
        self.assertEqual((data['status'], data['error'], data['running']), ('error', 'no such device', False))


if __name__ == '__main__':
    unittest.main()
