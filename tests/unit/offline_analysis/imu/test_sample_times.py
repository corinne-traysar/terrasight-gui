"""Tests of imu/sample_times.py: time-axis units and spreading repeated receipt times."""
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from offline_analysis.imu.sample_times import SampleTimes  # noqa: E402


class SecondsPerUnitTest(unittest.TestCase):
    """The axis name decides whether it is time, and its unit."""

    def test_time_names_and_units(self):
        cases = {'time_s': 1.0, 'time [s]': 1.0, 'received_utc': 1.0, 'received_ms': 1e-3, 'timestamp_us': 1e-6}
        for axis, scale in cases.items():
            self.assertEqual(SampleTimes.seconds_per_unit(axis), scale, axis)

    def test_distance_and_row_axes_are_not_time(self):
        for axis in ('distance_m', 'row', 'source_index'):
            self.assertIsNone(SampleTimes.seconds_per_unit(axis), axis)


class StrictlyIncreasingTest(unittest.TestCase):
    """Equal times are spread evenly up to the next distinct time."""

    def test_repeated_times_are_spread(self):
        # [0, 0] -> 0, 0.5 (step 1); [1, 1, 1] -> 1, 4/3, 5/3; the last time 2 stays.
        spread = SampleTimes.strictly_increasing([0.0, 0.0, 1.0, 1.0, 1.0, 2.0])
        for got, want in zip(spread, [0.0, 0.5, 1.0, 4 / 3, 5 / 3, 2.0]):
            self.assertAlmostEqual(got, want, delta=1e-12)

    def test_last_group_uses_the_median_step(self):
        spread = SampleTimes.strictly_increasing([0.0, 1.0, 2.0, 2.0])  # median step 1
        self.assertAlmostEqual(spread[3], 2.5, delta=1e-12)

    def test_backwards_or_constant_times_raise(self):
        with self.assertRaisesRegex(ValueError, 'goes backwards'):
            SampleTimes.strictly_increasing([0.0, 2.0, 1.0])
        with self.assertRaisesRegex(ValueError, 'two distinct'):
            SampleTimes.strictly_increasing([3.0, 3.0])


class OfAxisTest(unittest.TestCase):
    """of_axis scales to seconds and rejects non-time axes."""

    def test_milliseconds_become_seconds(self):
        self.assertEqual(list(SampleTimes.of_axis('received_ms', [1000.0, 1500.0])), [1.0, 1.5])

    def test_distance_axis_raises(self):
        with self.assertRaisesRegex(ValueError, 'not a time axis'):
            SampleTimes.of_axis('distance_m', [0.0, 1.0])


if __name__ == '__main__':
    unittest.main()
