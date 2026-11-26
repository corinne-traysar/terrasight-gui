"""Tests of scans/attitude_columns.py: finding yaw/pitch/roll columns and their angle unit.
"""
import math
import unittest

from offline_analysis.scans.attitude_columns import angle_scale, attitude_columns
from analysis_helpers import VN100_HEADER

FIELD = ['field_T_0', 'field_T_1', 'field_T_2']
COMBINED = ['combined_field_T_0', 'combined_field_T_1', 'combined_field_T_2']


class AttitudeColumnsTest(unittest.TestCase):
    """attitude_columns picks angle channels in yaw, pitch, roll order."""

    def test_columns_are_returned_in_yaw_pitch_roll_order(self):
        names = ['time', 'roll_deg', 'Bx', 'pitch_deg', 'yaw_deg']
        self.assertEqual(attitude_columns(names), ('yaw_deg', 'pitch_deg', 'roll_deg'))

    def test_vn100_recording(self):
        self.assertEqual(attitude_columns(VN100_HEADER), ('yaw_deg', 'pitch_deg', 'roll_deg'))

    def test_heading_counts_as_yaw_and_units_in_brackets_are_ignored(self):
        names = ['heading [deg]', 'imu_pitch', 'imu_roll']
        self.assertEqual(attitude_columns(names), ('heading [deg]', 'imu_pitch', 'imu_roll'))

    def test_missing_rate_and_embedded_words_are_not_angles(self):
        self.assertIsNone(attitude_columns(['yaw', 'pitch', 'Bx']))
        self.assertIsNone(attitude_columns(['gyro_yaw', 'yaw_rate', 'pitch', 'roll']))
        # 'controller' contains 'roll' but not as a token.
        self.assertIsNone(attitude_columns(['yaw', 'pitch', 'controller']))

    def test_angle_scale_from_name_then_value_range(self):
        self.assertEqual(angle_scale('yaw_rad', [100.0]), 1.0)
        self.assertAlmostEqual(angle_scale('yaw [deg]', [0.1]), math.pi / 180, delta=1e-15)
        self.assertAlmostEqual(angle_scale('roll (°)', [0.1]), math.pi / 180, delta=1e-15)
        self.assertAlmostEqual(angle_scale('yaw', [10.0, -170.0]), math.pi / 180, delta=1e-15)
        # Exactly 2π is not beyond it, and NaN is ignored.
        self.assertEqual(angle_scale('yaw', [2 * math.pi, math.nan]), 1.0)
        self.assertEqual(angle_scale('yaw', [math.nan]), 1.0)

if __name__ == '__main__':
    unittest.main()
