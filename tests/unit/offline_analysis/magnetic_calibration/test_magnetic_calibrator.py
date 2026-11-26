"""Tests of magnetic_calibration/magnetic_calibrator.py: choosing the method and fitting.

Needs numpy, scipy and onyx ``calibration`` (Python 3.12+); skipped where they are
missing, as on the Pi. The synthetic model is described in tests/calibration_model.py.
"""
import unittest

from calibration_model import MISSING, TOLERANCE_NT, model, recording
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT, DEFAULT_REFERENCE_NT

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402  (after the skip: numpy and onyx may be missing, as on the Pi)
from calibration import EllipsoidCalibration, ImuCalibration  # noqa: E402
from offline_analysis.magnetic_calibration.magnetic_calibrator import (  # noqa: E402
    build_calibration, calibrated_enu_nt, choose_method, fit_recording)


class FitTest(unittest.TestCase):
    """Method choice and fits that recover the injected offset and Earth field."""

    def test_default_reference_is_the_bar_gyora_total_field(self):
        self.assertAlmostEqual(DEFAULT_REFERENCE_NT, 45201.52, delta=0.01)

    def test_choose_method(self):
        self.assertEqual(choose_method(recording(True)), 'imu')
        self.assertEqual(choose_method(recording(False)), 'ellipsoid')
        self.assertEqual(choose_method(recording(True), 'ellipsoid'), 'ellipsoid')
        with self.assertRaisesRegex(ValueError, 'yaw, pitch and roll'):
            choose_method(recording(False), 'imu')
        with self.assertRaisesRegex(ValueError, 'unknown method'):
            choose_method(recording(), 'magic')

    def test_build_calibration(self):
        ellipsoid = build_calibration('ellipsoid', 50000.0)
        self.assertIsInstance(ellipsoid, EllipsoidCalibration)
        self.assertAlmostEqual(ellipsoid.reference_magnitude_t, 5e-5, delta=1e-17)
        self.assertIsInstance(build_calibration('imu'), ImuCalibration)
        with self.assertRaisesRegex(ValueError, 'mounting'):
            build_calibration('ellipsoid', mounting='sideways')
        with self.assertRaises(ValueError):
            build_calibration('imu', 0.0)

    def test_imu_fit_recovers_offset_and_earth_field_despite_misalignment(self):
        offset, soft_iron, misalignment, _ = model()
        data = recording(True, soft_iron @ misalignment)
        parameters = fit_recording(data)
        self.assertEqual(parameters.method, 'imu')
        np.testing.assert_allclose(parameters.offset_t * 1e9, offset, atol=TOLERANCE_NT)
        np.testing.assert_allclose(parameters.earth_field_enu_t * 1e9, BAR_GYORA_ENU_NT, atol=TOLERANCE_NT)
        np.testing.assert_allclose(calibrated_enu_nt(parameters, data),
                                   np.tile(BAR_GYORA_ENU_NT, (data.count, 1)), atol=TOLERANCE_NT)

    def test_ellipsoid_fit_without_attitude_restores_the_magnitude(self):
        data = recording(False)
        parameters = fit_recording(data)
        self.assertEqual(parameters.method, 'ellipsoid')
        np.testing.assert_allclose(parameters.offset_t * 1e9, model()[0], atol=TOLERANCE_NT)
        magnitude = np.linalg.norm(calibrated_enu_nt(parameters, data), axis=1)
        np.testing.assert_allclose(magnitude, DEFAULT_REFERENCE_NT, atol=TOLERANCE_NT)

    def test_too_few_rows_raises(self):
        with self.assertRaisesRegex(ValueError, 'at least'):
            fit_recording(recording(False, count=5))

if __name__ == '__main__':
    unittest.main()
