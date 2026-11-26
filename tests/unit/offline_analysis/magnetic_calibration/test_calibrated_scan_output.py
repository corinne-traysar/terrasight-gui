"""Tests of magnetic_calibration/calibrated_output.py: calibrated scans, summaries in nT and the JSON document.

Needs numpy, scipy and onyx ``calibration`` (Python 3.12+); skipped where they are
missing, as on the Pi.
"""
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402  (after the skip: numpy and onyx may be missing, as on the Pi)
from calibration import VectorCalibrationParameters  # noqa: E402
from offline_analysis.magnetic_calibration.calibrated_output import (  # noqa: E402
    ENU_COLUMNS, TOTAL_COLUMN, apply_summary, calibrated_scan, calibration_json, fit_summary, parse_calibration)
from offline_analysis.magnetic_calibration.magnetic_recording import MagneticRecording  # noqa: E402


def _parameters(earth=None):
    """Offset (100, 0, 0) nT, identity correction, reference 50,000 nT."""
    return VectorCalibrationParameters(
        method='imu' if earth is not None else 'ellipsoid', offset_t=np.array([1e-7, 0.0, 0.0]),
        correction=np.eye(3), reference_magnitude_t=5e-5, residual_rms_t=2e-9,
        sample_count=2, output_frame='test', earth_field_enu_t=earth)


def _two_rows():
    """Two rows at axis 10 and 20 s; raw (forward, right, down) = (100, 3, 4) and (100, 0, 0) nT."""
    field = np.array([[100.0, 3.0, 4.0], [100.0, 0.0, 0.0]]) * 1e-9
    return MagneticRecording('time', np.array([10.0, 20.0]), field, None, ('Bx', 'By', 'Bz'), None)



class OutputTest(unittest.TestCase):
    """Calibrated scans, summaries and the calibration JSON document."""

    def test_calibrated_scan_columns_and_level_north_frame(self):
        # Row 0: corrected body (0, 3, 4) -> east 3, north 0, up -4; |B| = 5 nT.
        out = calibrated_scan(_parameters(), _two_rows())
        self.assertEqual((out.axis, out.channels, out.axis_values), ('time', [*ENU_COLUMNS, TOTAL_COLUMN], (10.0, 20.0)))
        np.testing.assert_allclose([out.columns[n][0] for n in (*ENU_COLUMNS, TOTAL_COLUMN)], [3.0, 0.0, -4.0, 5.0], atol=1e-9)

    def test_summaries_in_nt(self):
        summary = fit_summary(_parameters(np.array([0.0, 2e-5, -3e-5])), _two_rows())
        self.assertEqual((summary['method'], summary['rows'], summary['attitude_columns']), ('imu', 2, []))
        np.testing.assert_allclose(summary['offset_nt'], [100.0, 0.0, 0.0])
        self.assertAlmostEqual(summary['residual_rms_nt'], 2.0, delta=1e-9)
        np.testing.assert_allclose(summary['earth_field_enu_nt'], [0.0, 20000.0, -30000.0])
        self.assertIsNone(fit_summary(_parameters(), _two_rows())['earth_field_enu_nt'])
        # |B| per row: 5 and 0 nT -> mean 2.5, population standard deviation 2.5.
        applied = apply_summary(calibrated_scan(_parameters(), _two_rows()), _two_rows())
        self.assertEqual((applied['rows'], applied['attitude_used']), (2, False))
        self.assertAlmostEqual(applied['b_total_mean_nt'], 2.5, delta=1e-9)
        self.assertAlmostEqual(applied['b_total_std_nt'], 2.5, delta=1e-9)

    def test_calibration_json_round_trips_like_onyx_files(self):
        text = calibration_json(_parameters(np.array([0.0, 2e-5, -3e-5])))
        self.assertTrue(text.startswith('{\n  "format": "onyx-vector-calibration/1"'))
        restored = parse_calibration(text)
        np.testing.assert_allclose(restored.offset_t, [1e-7, 0.0, 0.0])
        np.testing.assert_allclose(restored.earth_field_enu_t, [0.0, 2e-5, -3e-5])

    def test_parse_calibration_rejects_other_documents(self):
        with self.assertRaisesRegex(ValueError, 'not a onyx-vector-calibration/1'):
            parse_calibration('{"format": "something-else"}')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            parse_calibration('{"format": "onyx-vector-calibration/1", "method": "imu"}')


if __name__ == '__main__':
    unittest.main()
