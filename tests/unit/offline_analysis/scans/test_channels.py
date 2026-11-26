"""Tests of scans/channels.py: column-name normalizing and the sensor channel picks.

Ported from Simulation-Examples (calibration_crop tests).
"""
import unittest

from offline_analysis.scans.channels import (PROFILES, ChannelSet, ElectromagneticProfile, MagneticProfile,
                                             find_axis, is_imu, normalize)
from analysis_helpers import VN100_HEADER


class NameTest(unittest.TestCase):
    """normalize, find_axis and is_imu."""

    def test_normalize_drops_unit_and_case(self):
        self.assertEqual(normalize('Bx [nT]'), 'bx')
        self.assertEqual(normalize(' Time (s) '), 'time')

    def test_find_axis_prefers_time_over_distance(self):
        self.assertEqual(find_axis(['distance_m', 'Bx', 'Time (s)']), 'Time (s)')

    def test_find_axis_falls_back_to_distance_then_index(self):
        self.assertEqual(find_axis(['source_index', 'distance_m']), 'distance_m')
        self.assertEqual(find_axis(['Bx', 'sample']), 'sample')

    def test_find_axis_takes_vn100_receipt_time(self):
        self.assertEqual(find_axis(VN100_HEADER), 'received_utc')

    def test_find_axis_none_without_candidate(self):
        self.assertIsNone(find_axis(['Bx', 'By']))

    def test_is_imu_accepts_imu_names(self):
        for name in ('acc_x', 'accelX', 'gyro_z [deg/s]', 'roll', 'yaw_rate', 'qw', 'imu_mag_x', 'ax',
                     'yaw_deg', 'acceleration_x_m_s2', 'angular_rate_z_rad_s'):
            with self.subTest(name=name):
                self.assertTrue(is_imu(name))

    def test_is_imu_rejects_other_names(self):
        for name in ('Bx', 'temperature', 'axis', 'max_x', 'gps_lat', 'distance_m', 'sequence'):
            with self.subTest(name=name):
                self.assertFalse(is_imu(name))


class MagneticProfileTest(unittest.TestCase):
    """The magnetic profile matches one static value per axis."""

    profile = MagneticProfile()

    def test_matches_static_axes(self):
        for name in ('Bx [nT]', 'b_y', 'mag_z', 'field_T_2', 'B_east', 'magnetometer_up', 'bz_nt',
                     'magnetic_x_gauss'):
            with self.subTest(name=name):
                self.assertTrue(self.profile.is_b_axis(name))

    def test_rejects_phasor_parts_and_positions(self):
        for name in ('field_T_real_0', 'Bx_re', 'position_m_0', 'temperature', 'imu_mag_x'):
            with self.subTest(name=name):
                self.assertFalse(self.profile.is_b_axis(name))

    def test_select_splits_b_and_imu_in_file_order(self):
        chosen = self.profile.select(['t', 'gyro_x', 'Bz', 'Bx', 'roll', 'temp'])
        self.assertEqual(chosen, ChannelSet(('Bz', 'Bx'), ('gyro_x', 'roll')))
        self.assertEqual(chosen.all, ('Bz', 'Bx', 'gyro_x', 'roll'))

    def test_vn100_recording_picks_field_and_imu(self):
        chosen = self.profile.select(VN100_HEADER)
        self.assertEqual(chosen.b_axes, ('magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss'))
        self.assertEqual(chosen.imu[:3], ('yaw_deg', 'pitch_deg', 'roll_deg'))
        self.assertNotIn('sequence', chosen.all)


class ElectromagneticProfileTest(unittest.TestCase):
    """The electromagnetic profile matches per-axis phasor parts, amplitude and phase."""

    profile = ElectromagneticProfile()

    def test_matches_phasor_amplitude_and_phase(self):
        for name in ('Bx_re', 'by_im', 'field_T_real_0', 'field_T_imag_2', 'strength_T_1',
                     'theta_rad_2', 'amp_z', 'phase_x_deg', 'H_x'):
            with self.subTest(name=name):
                self.assertTrue(self.profile.is_b_axis(name))

    def test_rejects_per_cable_and_along_earth(self):
        for name in ('cable_fields_T_cable-1_real_0', 'along_earth_T_real', 'position_m_1', 'qx'):
            with self.subTest(name=name):
                self.assertFalse(self.profile.is_b_axis(name))

    def test_profiles_registry_has_both_sensors(self):
        self.assertEqual(sorted(PROFILES), ['electromagnetic', 'magnetic'])
        self.assertEqual(PROFILES['electromagnetic'].label, 'Electromagnetic')

if __name__ == '__main__':
    unittest.main()
