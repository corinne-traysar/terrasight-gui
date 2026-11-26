"""Tests of magnetic_calibration/magnetic_recording.py: reading B and attitude columns of a scan.

Needs numpy, scipy and onyx ``calibration`` (Python 3.12+); skipped where they are
missing, as on the Pi. The synthetic model is described in tests/calibration_model.py.
"""
import math
import unittest

from calibration_model import MISSING, scan

if MISSING:
    raise unittest.SkipTest(MISSING)

from offline_analysis.magnetic_calibration.magnetic_recording import read_recording  # noqa: E402


class ReadRecordingTest(unittest.TestCase):
    """read_recording converts units and drops incomplete rows."""

    def test_field_columns_in_nt_become_tesla(self):
        data = read_recording(scan(Bx=(1.0, 2.0, 3.0), By=(0.0, 0.0, 0.0), Bz=(5.0, 5.0, 5.0)))
        self.assertAlmostEqual(float(data.field_t[2, 0]), 3e-9, delta=1e-21)
        self.assertEqual(data.field_columns, ('Bx', 'By', 'Bz'))
        self.assertFalse(data.has_attitude)

    def test_vn100_gauss_and_degrees(self):
        data = read_recording(scan(yaw_deg=(90.0,) * 3, pitch_deg=(0.0,) * 3, roll_deg=(-45.0,) * 3,
                                   magnetic_x_gauss=(0.5,) * 3, magnetic_y_gauss=(0.0,) * 3,
                                   magnetic_z_gauss=(0.0,) * 3))
        self.assertAlmostEqual(float(data.field_t[0, 0]), 5e-5, delta=1e-17)  # 0.5 G = 50 µT
        self.assertAlmostEqual(float(data.attitude_rad[0, 0]), math.pi / 2, delta=1e-12)
        self.assertAlmostEqual(float(data.attitude_rad[0, 2]), -math.pi / 4, delta=1e-12)

    def test_rows_with_missing_values_are_dropped_with_their_axis_value(self):
        data = read_recording(scan(Bx=(1.0, math.nan, 3.0), By=(0.0,) * 3, Bz=(0.0,) * 3,
                                   yaw=(0.0, 0.0, math.nan), pitch=(0.0,) * 3, roll=(0.0,) * 3))
        self.assertEqual((data.count, data.axis_values.tolist()), (1, [0.0]))

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, 'no row'):
            read_recording(scan(Bx=(math.nan,) * 3, By=(0.0,) * 3, Bz=(0.0,) * 3))
        with self.assertRaisesRegex(ValueError, 'no magnetic B-field'):
            read_recording(scan(temperature=(1.0, 2.0, 3.0)))

if __name__ == '__main__':
    unittest.main()
