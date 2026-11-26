"""Tests of sensors/ap230_serial.py: the AP230 row format (gauss to microtesla) and port setup."""
import unittest

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from serial_fakes import FD, FakeSerial
from sensors import ap230_serial
from sensors.ap230_serial import configure_port, parse_row


class ParseRowTests(unittest.TestCase):
    """parse_row: gauss text to uT, and refusal of incomplete or garbled rows."""

    def test_units_and_incomplete_or_garbled_rows(self):
        # 1 G = 100 uT: (0.3, -0.4, 0) G -> (30, -40, 0) uT and |B| = 50 uT.
        self.assertEqual(parse_row(b' A +0.3000 -0.4000 +0.0000 '), [30, -40, 0, 50])
        for line in [b'+0.3000 -0.4000', b'junk +0.3000 -0.4000 +0.0000',
                     b'\x00+0.3000 -0.4000 +0.0000']:
            self.assertIsNone(parse_row(line))

    def test_d_prefix_and_negative_values(self):
        values = parse_row(b'D -0.0100 +0.0000 +0.0000')
        self.assertIsNotNone(values)
        self.assertAlmostEqual((values or [0])[0], -1.0, delta=1e-12)  # -0.01 G = -1 uT
        self.assertIsNone(parse_row(b'+0.100 +0.0000 +0.0000'), 'four decimals are required')


class ConfigurePortTests(unittest.TestCase):
    """configure_port: raw 9600 8N1 with non-blocking reads, old settings returned."""

    def test_raw_9600_8n1_and_old_settings(self):
        serial = FakeSerial()
        with serial.patch(ap230_serial):
            old = configure_port(FD)
        raw = serial.settings[0]
        self.assertEqual(old, [1, 1, 1, 1, 1, 1, [1] * 32])
        self.assertEqual((raw[0], raw[1], raw[3]), (0, 0, 0), 'no input, output or local processing')
        self.assertEqual(raw[2], serial.termios.CS8 | serial.termios.CREAD | serial.termios.CLOCAL)
        self.assertEqual((raw[4], raw[5]), (serial.termios.B9600,) * 2)
        self.assertEqual((raw[6][serial.termios.VMIN], raw[6][serial.termios.VTIME]), (0, 0))


if __name__ == '__main__':
    unittest.main()
