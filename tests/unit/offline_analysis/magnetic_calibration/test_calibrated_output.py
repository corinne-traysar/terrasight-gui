"""Tests of magnetic_calibration/calibrated_output.py: onyx-calibrated scans in nT, summaries
and Offline Data's Apply Calibration.

Needs numpy, scipy and onyx (Python 3.12+). The synthetic model is the one in
tests/calibration_model.py: raw = A (M^T R^T h) + b; a correct IMU calibration
returns the Earth field h (east/north/up) on every row.
"""
import math
import unittest

from calibration_model import MISSING, model, recording
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT, DEFAULT_REFERENCE_NT

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402
from scans import MagneticScan  # noqa: E402

from offline_analysis.magnetic_calibration.calibrated_output import (  # noqa: E402
    ENU_COLUMNS, TOTAL_COLUMN, CalibratedOutput, fit_summary, offline_calibration)
from offline_analysis.magnetic_calibration.calibration_document import CalibrationDocument  # noqa: E402
from offline_analysis.magnetic_calibration.magnetic_calibrator import MagneticCalibrator  # noqa: E402


def fitted(count=80):
    """A misaligned synthetic scan with attitude and the IMU calibration fitted to it."""
    _, soft_iron, misalignment, _ = model()
    scan = recording(True, soft_iron @ misalignment, count=count)
    return scan, MagneticCalibrator().fit(scan)


class CalibratedOutputTest(unittest.TestCase):
    """CalibratedOutput: east/north/up nT rows, CSV and summary."""

    def test_every_row_is_the_earth_field(self):
        scan, calibration = fitted()
        output = CalibratedOutput(scan, calibration)
        np.testing.assert_allclose(output.enu_nt, np.tile(BAR_GYORA_ENU_NT, (80, 1)), atol=0.01)
        summary = output.summary()
        self.assertEqual((summary['rows'], summary['attitude_used']), (80, True))
        self.assertAlmostEqual(summary['b_total_mean_nt'], DEFAULT_REFERENCE_NT, delta=0.01)

    def test_rows_with_a_missing_value_are_dropped(self):
        scan, calibration = fitted()
        columns = {name: np.array(scan.column(name)) for name in scan.columns}
        columns['Bx_nT'][4] = math.nan
        output = CalibratedOutput(MagneticScan(columns, 't'), calibration)
        self.assertEqual(output.rows, 79)
        self.assertNotIn(4.0, list(output.data().axis_values))

    def test_csv_header(self):
        scan, calibration = fitted()
        header = CalibratedOutput(scan, calibration).csv().splitlines()[0]
        self.assertEqual(header, ','.join(('t', *ENU_COLUMNS, TOTAL_COLUMN)))


class FitSummaryTest(unittest.TestCase):
    """fit_summary reports the fit in nT."""

    def test_summary_of_an_imu_fit(self):
        scan, calibration = fitted()
        summary = fit_summary(calibration, scan)
        self.assertEqual((summary['method'], summary['rows']), ('imu', 80))
        self.assertEqual(summary['b_columns'], ['Bx_nT', 'By_nT', 'Bz_nT'])
        self.assertEqual(summary['attitude_columns'], ['yaw_rad', 'pitch_rad', 'roll_rad'])
        np.testing.assert_allclose(summary['offset_nt'], model()[0], atol=0.01)
        np.testing.assert_allclose(summary['earth_field_enu_nt'], BAR_GYORA_ENU_NT, atol=0.01)


class OfflineCalibrationTest(unittest.TestCase):
    """offline_calibration: vectors, summary and angles for the Offline Data view."""

    def setUp(self):
        self.scan, calibration = fitted()
        self.text = CalibrationDocument.text(calibration, self.scan)

    def test_vectors_labels_and_angles(self):
        result = offline_calibration(self.text, self.scan)
        self.assertEqual((result['count'], result['labels'], result['b_columns']),
                         (80, ['E', 'N', 'U'], ['Bx_nT', 'By_nT', 'Bz_nT']))
        np.testing.assert_allclose(result['field_nt'], np.tile(BAR_GYORA_ENU_NT, (80, 1)), atol=0.01)
        self.assertEqual((result['calibration']['method'], result['calibration']['sample_count']), ('imu', 80))

    def test_scan_without_attitude_is_taken_as_level(self):
        level = recording(False)
        self.assertFalse(offline_calibration(self.text, level)['summary']['attitude_used'])

    def test_bad_calibration_raises(self):
        with self.assertRaisesRegex(ValueError, 'not a onyx-vector-calibration/1'):
            offline_calibration('{"format": "x"}', self.scan)


if __name__ == '__main__':
    unittest.main()
