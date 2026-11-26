"""Tests of imu/imu_columns.py: finding raw accelerometer and gyroscope triples and their units."""
import math
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from analysis_helpers import VN100_HEADER  # noqa: E402
from offline_analysis.imu.imu_columns import RawImuColumns, acceleration_scale, rate_scale  # noqa: E402


class FindTest(unittest.TestCase):
    """RawImuColumns.find picks the triples by name."""

    def test_vn100_recording_has_both_triples_in_si_units(self):
        found = RawImuColumns.find(VN100_HEADER)
        assert found is not None
        self.assertEqual(found.accelerometer, ('acceleration_x_m_s2', 'acceleration_y_m_s2', 'acceleration_z_m_s2'))
        self.assertEqual(found.gyroscope, ('angular_rate_x_rad_s', 'angular_rate_y_rad_s', 'angular_rate_z_rad_s'))
        self.assertEqual((found.to_m_s2, found.to_rad_s), (1.0, 1.0))
        self.assertEqual(len(found.names), 6)

    def test_accelerometer_only_has_no_gyroscope(self):
        found = RawImuColumns.find(['t', 'acc_x', 'acc_y', 'acc_z', 'Bx', 'By', 'Bz'])
        assert found is not None
        self.assertEqual((found.accelerometer, found.gyroscope), (('acc_x', 'acc_y', 'acc_z'), None))

    def test_no_accelerometer_triple_gives_none(self):
        self.assertIsNone(RawImuColumns.find(['t', 'gyro_x', 'gyro_y', 'gyro_z']))
        self.assertIsNone(RawImuColumns.find(['t', 'acc_x', 'gyro_z', 'Bx', 'By', 'Bz']))  # incomplete triple

    def test_magnetic_columns_are_not_imu(self):
        self.assertIsNone(RawImuColumns.find(['magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss']))


class UnitTest(unittest.TestCase):
    """Unit factors from the column names."""

    def test_acceleration_in_g_becomes_m_s2(self):
        self.assertAlmostEqual(acceleration_scale('acc_x [g]'), 9.80665, delta=1e-12)
        self.assertEqual(acceleration_scale('acceleration_x_m_s2'), 1.0)
        self.assertEqual(acceleration_scale('gyro_acc_x'), 1.0)  # the g in a word is not a unit

    def test_rate_in_degrees_becomes_rad_s(self):
        for name in ('gyro_x_deg_s', 'gyro_x [dps]', 'gyro_x [°/s]'):
            self.assertAlmostEqual(rate_scale(name), math.pi / 180, delta=1e-15, msg=name)
        self.assertEqual(rate_scale('angular_rate_x_rad_s'), 1.0)


if __name__ == '__main__':
    unittest.main()
