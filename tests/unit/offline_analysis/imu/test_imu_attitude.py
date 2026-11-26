"""Tests of imu/imu_attitude.py: derived yaw/pitch/roll columns on onyx scan tables."""
import math
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from imu_helpers import RAW_HEADER, raw_rows, raw_table  # noqa: E402
from offline_analysis.imu.imu_attitude import ANGLE_COLUMNS, METADATA_KEY, ImuAttitude  # noqa: E402


class AugmentTest(unittest.TestCase):
    """ImuAttitude.augment adds angles only where a scan needs them."""

    def test_gyroscope_scan_gets_integrated_yaw(self):
        table = ImuAttitude().augment(raw_table())  # 0.1 rad/s for 10 s
        self.assertEqual(table.channels[-3:], list(ANGLE_COLUMNS))
        self.assertAlmostEqual(table.columns['imu_yaw_rad'][-1], 1.0, delta=1e-9)
        record = table.metadata[METADATA_KEY]
        self.assertEqual((record['source'], record['rows']), ('gyroscope', 11))
        self.assertEqual(record['columns'], RAW_HEADER[1:])

    def test_accelerometer_only_scan_gets_zero_yaw(self):
        rows = [row[:4] for row in raw_rows(3)]
        table = ImuAttitude().augment(raw_table(rows, RAW_HEADER[:4]))
        self.assertEqual(list(table.columns['imu_yaw_rad']), [0.0, 0.0, 0.0])
        self.assertEqual(table.metadata[METADATA_KEY]['source'], 'accelerometer')

    def test_scan_with_angles_or_without_imu_is_unchanged(self):
        with_angles = raw_table([[0, 0, 0, -9.8, 1, 2, 3]], ['t', 'acc_x', 'acc_y', 'acc_z', 'yaw', 'pitch', 'roll'])
        self.assertIs(ImuAttitude().augment(with_angles), with_angles)
        no_imu = raw_table([[0, 1, 2, 3]], ['t', 'Bx', 'By', 'Bz'])
        self.assertIs(ImuAttitude().augment(no_imu), no_imu)

    def test_rows_with_a_missing_reading_get_nan_angles(self):
        rows = raw_rows(5)
        rows[2][3] = math.nan  # acc_z of row 2
        table = ImuAttitude().augment(raw_table(rows))
        self.assertTrue(math.isnan(table.columns['imu_pitch_rad'][2]))
        self.assertEqual(table.metadata[METADATA_KEY]['rows'], 4)

    def test_no_complete_row_leaves_the_scan_unchanged(self):
        rows = [[i, math.nan, 0.0, -9.8, 0.0, 0.0, 0.1] for i in range(3)]
        table = raw_table(rows)
        self.assertIs(ImuAttitude().augment(table), table)

    def test_distance_axis_falls_back_to_the_accelerometer_with_a_note(self):
        header = ['distance_m'] + RAW_HEADER[1:]
        table = ImuAttitude().augment(raw_table(raw_rows(4), header))
        record = table.metadata[METADATA_KEY]
        self.assertEqual(record['source'], 'accelerometer')
        self.assertIn('not a time axis', record['note'])


if __name__ == '__main__':
    unittest.main()
