"""Tests of dashboard/pi_health.py: throttling flags and the thermal guard.
"""
import unittest

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from dashboard.pi_health import PiHealth, decode_throttled


class HealthTests(unittest.TestCase):
    def test_guard_hysteresis_and_no_automatic_resume(self):
        calls=[];temperature=[76]
        h=PiHealth(on_hot=lambda:calls.append('paused'),temperature_reader=lambda:temperature[0],throttle_reader=lambda:0)
        h.sample();self.assertFalse(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=73;h.sample();self.assertFalse(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=69;h.sample();self.assertTrue(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=76;h.sample();self.assertEqual(calls,['paused','paused'])

    def test_current_and_historical_throttle_flags_are_distinct(self):
        flags=decode_throttled((1<<2)|(1<<16))
        self.assertTrue(flags['throttled']);self.assertFalse(flags['undervoltage'])
        self.assertTrue(flags['undervoltage_occurred']);self.assertFalse(flags['throttled_occurred'])

    def test_missing_telemetry_is_reported(self):
        def missing():raise OSError('not present')
        h=PiHealth(temperature_reader=missing,throttle_reader=missing);h.sample()
        self.assertIsNone(h.snapshot()['temperature_C']);self.assertIsNone(h.snapshot()['flags'])
        self.assertEqual(len(h.snapshot()['errors']),2)

if __name__ == '__main__':
    unittest.main()
