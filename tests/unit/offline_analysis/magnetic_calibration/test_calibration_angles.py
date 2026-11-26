"""Tests of magnetic_calibration/calibration_angles.py: mounting, Earth-field and stored angles.

Needs numpy and scipy (skipped without onyx, like the module). Documents are
hand-built ``onyx-vector-calibration/1`` objects; the scan yaw/pitch/roll
records are tested in scans/test_attitude_record.py.
"""
import math
import unittest

from calibration_model import MISSING
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

from offline_analysis.magnetic_calibration.calibration_angles import (  # noqa: E402
    ATTITUDE_KEY, calibration_angles, earth_angles, euler_zyx_deg, polar_rotation)

ENU_MOUNTING = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]


def zyx(yaw, pitch, roll):
    """The rotation matrix of aerospace Z-Y-X angles in degrees."""
    return Rotation.from_euler('ZYX', [yaw, pitch, roll], degrees=True).as_matrix()


def document(**changes):
    """An ellipsoid calibration with the ENU mounting and a 1.02 scale, plus ``changes``."""
    base = {'format': 'onyx-vector-calibration/1', 'method': 'ellipsoid', 'offset_t': [0.0, 0.0, 0.0],
            'correction': [[1.02 * v for v in row] for row in ENU_MOUNTING], 'reference_magnitude_t': 4.5e-5,
            'residual_rms_t': 1e-9, 'sample_count': 80, 'output_frame': 'sensor', 'earth_field_enu_t': None}
    return {**base, **changes}


class EulerTest(unittest.TestCase):
    """Z-Y-X yaw, pitch and roll of rotation matrices."""

    def test_identity_is_zero(self):
        self.assertEqual(euler_zyx_deg(np.eye(3)), {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0})

    def test_round_trip_of_known_angles(self):
        for angles in ((30.0, 10.0, -20.0), (-150.0, 45.0, 170.0), (90.0, -60.0, 5.0)):
            with self.subTest(angles=angles):
                result = euler_zyx_deg(zyx(*angles))
                for key, want in zip(('yaw', 'pitch', 'roll'), angles):
                    self.assertAlmostEqual(result[key], want, delta=1e-9)

    def test_enu_sensor_mounting_is_yaw_90_roll_180(self):
        result = euler_zyx_deg(np.array(ENU_MOUNTING))  # onyx SENSOR_ENU_TO_BODY
        self.assertEqual((result['yaw'], result['pitch'], abs(result['roll'])), (90.0, 0.0, 180.0))


class PolarRotationTest(unittest.TestCase):
    """The rotation of C = R S survives any symmetric positive scale S."""

    def test_rotation_is_recovered_from_scaled_matrix(self):
        rotation = zyx(12.0, -7.0, 3.0)
        scale = np.array([[1.05, 0.02, -0.01], [0.02, 0.97, 0.015], [-0.01, 0.015, 1.02]])
        recovered, reflected = polar_rotation(rotation @ scale)
        self.assertFalse(reflected)
        np.testing.assert_allclose(recovered, rotation, atol=1e-12)

    def test_negative_determinant_is_flagged_and_mirrored(self):
        rotation = zyx(40.0, 0.0, 0.0)
        recovered, reflected = polar_rotation(-(rotation @ np.diag([2.0, 1.0, 3.0])))
        self.assertTrue(reflected)
        np.testing.assert_allclose(recovered, rotation, atol=1e-12)

    def test_singular_matrix_raises(self):
        with self.assertRaisesRegex(ValueError, 'singular'):
            polar_rotation(np.diag([1.0, 1.0, 0.0]))


class CalibrationAnglesTest(unittest.TestCase):
    """calibration_angles: mounting, Earth field and stored calibration-scan attitude."""

    def test_ellipsoid_enu_mounting(self):
        angles = calibration_angles(document())
        mounting = angles['mounting_deg']
        self.assertEqual((mounting['yaw'], mounting['pitch'], abs(mounting['roll'])), (90.0, 0.0, 180.0))
        self.assertFalse(angles['reflected'])
        self.assertIsNone(angles['earth'])
        self.assertIsNone(angles['attitude'])
        self.assertEqual((angles['method'], angles['sample_count']), ('ellipsoid', 80))

    def test_earth_field_angles_of_bar_gyora(self):
        earth = earth_angles([c * 1e-9 for c in BAR_GYORA_ENU_NT])
        self.assertAlmostEqual(earth['declination_deg'], math.degrees(math.atan2(2608, 30063)), places=3)
        self.assertAlmostEqual(earth['inclination_deg'], 48.0, delta=0.2)  # dips down in Israel
        self.assertAlmostEqual(earth['total_nt'], 45201.52, delta=0.01)
        angles = calibration_angles(document(method='imu', earth_field_enu_t=[c * 1e-9 for c in BAR_GYORA_ENU_NT]))
        self.assertEqual(angles['earth']['enu_nt'], [2608.0, 30063.0, -33654.0])

    def test_stored_attitude_is_returned(self):
        stored = {'columns': ['yaw', 'pitch', 'roll'], 'axis': 't', 'axis_values': [0, 1],
                  'degrees': [[1, 2, 3], [4, None, 6]]}
        angles = calibration_angles(document(**{ATTITUDE_KEY: stored}))
        self.assertEqual(angles['attitude']['degrees'], [[1.0, 2.0, 3.0], [4.0, None, 6.0]])
        self.assertEqual(angles['attitude']['axis_values'], [0.0, 1.0])

    def test_stored_attitude_without_matching_axis_uses_row_numbers(self):
        stored = {'columns': ['y', 'p', 'r'], 'degrees': [[1, 2, 3]] * 3}
        self.assertEqual(calibration_angles(document(**{ATTITUDE_KEY: stored}))['attitude']['axis_values'], [0, 1, 2])

    def test_malformed_documents_raise(self):
        for changes in ({'correction': [[1, 0], [0, 1]]}, {'correction': [[0] * 3] * 3},
                        {'earth_field_enu_t': [1.0]}, {ATTITUDE_KEY: {'columns': ['y'], 'degrees': []}},
                        {ATTITUDE_KEY: [1, 2, 3]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calibration_angles(document(**changes))


if __name__ == '__main__':
    unittest.main()
