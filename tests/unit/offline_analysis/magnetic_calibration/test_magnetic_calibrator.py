"""Tests of magnetic_calibration/magnetic_calibrator.py: options, method choice and onyx fits.

Needs numpy, scipy and onyx (Python 3.12+); skipped where they are missing.
The synthetic model is described in tests/calibration_model.py.
"""
import unittest

from calibration_model import MISSING, TOLERANCE_NT, model, recording
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT, DEFAULT_REFERENCE_NT

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402  (after the skip: numpy and onyx may be missing)
from calibration import EllipsoidCalibration, ImuCalibration  # noqa: E402

from offline_analysis.magnetic_calibration.magnetic_calibrator import MagneticCalibrator  # noqa: E402


class OptionsTest(unittest.TestCase):
    """The constructor checks the options; build makes the onyx class."""

    def test_default_reference_is_the_bar_gyora_total_field(self):
        self.assertAlmostEqual(MagneticCalibrator().reference_nt, 45201.52, delta=0.01)

    def test_bad_options_raise(self):
        with self.assertRaisesRegex(ValueError, 'unknown method'):
            MagneticCalibrator(method='magic')
        with self.assertRaisesRegex(ValueError, 'mounting'):
            MagneticCalibrator(mounting='sideways')
        with self.assertRaisesRegex(ValueError, 'positive'):
            MagneticCalibrator(reference_nt=0.0)

    def test_build_scales_the_reference_to_tesla(self):
        ellipsoid = MagneticCalibrator(reference_nt=50000.0).build('ellipsoid')
        self.assertIsInstance(ellipsoid, EllipsoidCalibration)
        self.assertAlmostEqual(ellipsoid.reference_magnitude_t, 5e-5, delta=1e-17)
        self.assertIsInstance(MagneticCalibrator().build('imu'), ImuCalibration)
        with self.assertRaisesRegex(ValueError, 'unknown method'):
            MagneticCalibrator().build('auto')


class MethodForTest(unittest.TestCase):
    """auto follows the scan's attitude; imu needs it."""

    def test_choice(self):
        self.assertEqual(MagneticCalibrator().method_for(recording(True)), 'imu')
        self.assertEqual(MagneticCalibrator().method_for(recording(False)), 'ellipsoid')
        self.assertEqual(MagneticCalibrator('ellipsoid').method_for(recording(True)), 'ellipsoid')
        with self.assertRaisesRegex(ValueError, 'yaw, pitch and roll'):
            MagneticCalibrator('imu').method_for(recording(False))


class FitTest(unittest.TestCase):
    """Fits that recover the injected offset and Earth field."""

    def test_imu_fit_recovers_offset_and_earth_field_despite_misalignment(self):
        offset, soft_iron, misalignment, _ = model()
        parameters = MagneticCalibrator().fit(recording(True, soft_iron @ misalignment)).parameters
        self.assertEqual(parameters.method, 'imu')
        np.testing.assert_allclose(parameters.offset_t * 1e9, offset, atol=TOLERANCE_NT)
        assert parameters.earth_field_enu_t is not None
        np.testing.assert_allclose(parameters.earth_field_enu_t * 1e9, BAR_GYORA_ENU_NT, atol=TOLERANCE_NT)

    def test_ellipsoid_fit_without_attitude_restores_the_magnitude(self):
        scan = recording(False)
        calibration = MagneticCalibrator().fit(scan)
        self.assertEqual(calibration.parameters.method, 'ellipsoid')
        np.testing.assert_allclose(calibration.parameters.offset_t * 1e9, model()[0], atol=TOLERANCE_NT)
        magnitude = np.linalg.norm(calibration.correct(scan.field_t), axis=1) * 1e9
        np.testing.assert_allclose(magnitude, DEFAULT_REFERENCE_NT, atol=TOLERANCE_NT)

    def test_too_few_rows_raises(self):
        with self.assertRaisesRegex(ValueError, 'at least'):
            MagneticCalibrator().fit(recording(False, count=5))


if __name__ == '__main__':
    unittest.main()
