"""Tests of sensors/vn100.py's serial side: open_serial and the VN100Reader thread.

Fake-serial tests run anywhere; the pseudo-terminal test needs a POSIX machine.
"""
import os
from pathlib import Path
try:
    import pty
except (ImportError, NameError):  # Windows: pty and tty are POSIX-only (tty fails with NameError)
    pty = None
import tempfile
import time
import unittest
import unittest.mock

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)
from serial_fakes import FD, FakeSerial
from sensors import vn100
from sensors.vn100 import Measurements, VN100Reader, open_serial
from vn100_helpers import PACKET, eventually


@unittest.skipIf(pty is None, 'pseudo-terminals need a POSIX machine')
class PtyReaderTests(unittest.TestCase):
    """The reader on real pseudo-terminals, including a replaced device."""

    def test_disconnect_and_reconnect_with_replaced_device(self):
        masters, slaves = [], []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sensor'

            def device():
                assert pty is not None
                master, slave = pty.openpty()
                masters.append(master)
                slaves.append(slave)
                if path.is_symlink():
                    path.unlink()
                path.symlink_to(os.ttyname(slave))
                return master

            master = device()
            state = Measurements()
            reader = VN100Reader(str(path), state, retry_seconds=.05)
            reader.start()
            try:
                eventually(lambda: state.snapshot()['status'] == 'waiting')
                os.write(master, PACKET[:30])
                time.sleep(.02)
                os.write(master, PACKET[30:])
                eventually(lambda: state.snapshot()['received'] == 1)
                os.close(master)
                masters.remove(master)
                eventually(lambda: state.snapshot()['status'] == 'disconnected')
                master = device()
                eventually(lambda: state.snapshot()['status'] == 'waiting')
                os.write(master, PACKET)
                eventually(lambda: state.snapshot()['received'] == 2)
                self.assertEqual(state.snapshot()['latest']['attitude'], [-83.439, 17.941, -14.121])
            finally:
                reader.stop()
                for fd in masters + slaves:
                    os.close(fd)


class FakeSerialReaderTests(unittest.TestCase):
    """The reader thread on a fake port: decoding, rejects, disconnect and reconnect."""

    def test_packets_rejects_and_reconnect(self):
        serial = FakeSerial([PACKET[:30], PACKET[30:] + b'$VNYMR,garbled*00\r\n', b''])
        state = Measurements()
        reader = VN100Reader('/dev/fake', state, retry_seconds=.01)
        with serial.patch(vn100), unittest.mock.patch('builtins.print'):
            reader.start()
            try:
                eventually(lambda: len(serial.opened) >= 2)  # disconnected, then reopened
                serial.feed(PACKET)
                eventually(lambda: state.snapshot()['received'] == 2)
            finally:
                reader.stop()
        snapshot = state.snapshot()
        self.assertEqual((snapshot['rejected'], snapshot['status']), (1, 'disconnected'))
        self.assertEqual(snapshot['latest']['attitude'], [-83.439, 17.941, -14.121])

    def test_open_failure_is_reported_and_retried(self):
        serial = FakeSerial(open_error=OSError('no such device'))
        state = Measurements()
        reader = VN100Reader('/dev/fake', state, retry_seconds=.01)
        with serial.patch(vn100), unittest.mock.patch('builtins.print'):
            reader.start()
            try:
                eventually(lambda: state.snapshot()['error'] == 'no such device')
            finally:
                reader.stop()
        self.assertEqual(state.snapshot()['status'], 'disconnected')

    def test_open_serial_sets_raw_115200(self):
        serial = FakeSerial()
        with serial.patch(vn100):
            self.assertEqual(open_serial('/dev/fake', 115200), FD)
        raw = serial.settings[0]
        self.assertEqual((raw[4], raw[5]), (serial.termios.B115200,) * 2)
        self.assertEqual(raw[2], serial.termios.CS8 | serial.termios.CREAD | serial.termios.CLOCAL)


if __name__ == '__main__':
    unittest.main()


