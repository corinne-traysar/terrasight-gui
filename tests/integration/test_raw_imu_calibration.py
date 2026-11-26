"""Integration: a calibration recording with only raw IMU readings (accelerometer and
gyroscope, no angles) is calibrated end to end through the analysis API.

Path: CSV text -> onyx reader -> ImuAttitude (onyx StrapdownNavigator) -> onyx
MagneticScan -> onyx ImuCalibration -> calibration JSON -> onyx calibrate.
The tumble starts level and still, facing north, so the integrated yaw equals
the true yaw and the IMU fit must recover the injected offset and the Earth
field. Needs numpy, scipy and onyx.
"""
import json
import unittest

from api_helpers import FIT_AVAILABLE, post
from calibration_model import model, raw_field_nt
from imu_helpers import tumble, tumble_text
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT, DEFAULT_REFERENCE_NT

TOLERANCE_NT = 1.0
"""Strapdown angles are exact for this motion up to round-off; 1 nT on ~45,000 nT."""


@unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx scans, calibration and navigation packages')
class RawImuCalibrationTest(unittest.TestCase):
    """Fit a raw-IMU tumble, then apply the calibration to the same file."""

    @classmethod
    def setUpClass(cls):
        """Build the tumble CSV once: misaligned soft-iron sensor plus offset."""
        _, soft_iron, misalignment, _ = model()
        attitude, force, rates = tumble()
        cls.true_attitude = attitude
        cls.text = tumble_text(raw_field_nt(attitude, soft_iron @ misalignment), force, rates)

    def test_load_derives_the_true_angles_from_the_gyroscope(self):
        import numpy as np
        body = post('/api/scan/load', {'name': 'tumble.csv', 'text': self.text}).body
        self.assertEqual(body['attitude']['derived']['source'], 'gyroscope')
        derived = np.column_stack([body['columns'][n] for n in body['attitude']['columns']])
        rotation = _rotations(derived).inv() * _rotations(self.true_attitude)
        self.assertLess(float(np.degrees(rotation.magnitude()).max()), 1e-6)

    def test_fit_file_uses_the_imu_method_and_recovers_offset_and_earth_field(self):
        import numpy as np
        reply = post('/api/calibration/fit-file', {'name': 'tumble.csv', 'text': self.text})
        self.assertEqual(reply.status, 200, reply.body)
        summary = reply.body['summary']
        self.assertEqual(summary['method'], 'imu')
        self.assertEqual(summary['attitude_columns'], ['imu_yaw_rad', 'imu_pitch_rad', 'imu_roll_rad'])
        np.testing.assert_allclose(summary['offset_nt'], model()[0], atol=TOLERANCE_NT)
        np.testing.assert_allclose(summary['earth_field_enu_nt'], BAR_GYORA_ENU_NT, atol=TOLERANCE_NT)
        stored = json.loads(reply.body['calibration_json'])['calibration_attitude']
        self.assertEqual(len(stored['degrees']), 300)

    def test_applying_the_fit_gives_the_earth_field_on_every_row(self):
        import numpy as np
        calibration = post('/api/calibration/fit-file', {'name': 'tumble.csv', 'text': self.text}).body
        reply = post('/api/offline/calibrate', {'name': 'tumble.csv', 'text': self.text,
                                                'calibration': calibration['calibration_json']})
        self.assertEqual(reply.status, 200, reply.body)
        self.assertTrue(reply.body['summary']['attitude_used'])
        np.testing.assert_allclose(reply.body['field_nt'], np.tile(BAR_GYORA_ENU_NT, (300, 1)), atol=TOLERANCE_NT)
        self.assertAlmostEqual(reply.body['summary']['b_total_mean_nt'], DEFAULT_REFERENCE_NT, delta=TOLERANCE_NT)


def _rotations(yaw_pitch_roll_rad):
    """SciPy rotations of (N, 3) aerospace Z-Y-X angles (compared as rotations, not angles)."""
    from scipy.spatial.transform import Rotation
    return Rotation.from_euler('ZYX', yaw_pitch_roll_rad)


if __name__ == '__main__':
    unittest.main()
