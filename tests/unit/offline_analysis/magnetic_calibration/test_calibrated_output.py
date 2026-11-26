"""Calibration files that carry their scan's attitude, and Offline Data's Apply Calibration.

Needs numpy, scipy and the onyx ``calibration`` package (Python 3.12+); the
fitting checks are skipped where they are missing, as on the Pi. The synthetic
model is the one in tests/calibration_model.py: raw = A (M^T R^T h) + b with
A = soft iron x misalignment and M the ENU sensor mounting. An IMU fit gives
C = A_total^-1, whose rotation is M misalignment^T.
"""
import json
import unittest

from calibration_model import MISSING, model, recording
from offline_analysis import web_api
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402  (after the skip: numpy and onyx may be missing, as on the Pi)
from offline_analysis.magnetic_calibration.calibrated_output import (  # noqa: E402
    calibration_json, parse_calibration)


class CalibrationJsonAttitudeTest(unittest.TestCase):
    """calibration_json stores the fitted rows' yaw/pitch/roll; onyx still reads the file."""

    def setUp(self):
        from offline_analysis.magnetic_calibration.magnetic_calibrator import fit_recording
        _, soft_iron, misalignment, _ = model()
        self.recording = recording(True, soft_iron @ misalignment, count=80)
        self.parameters = fit_recording(self.recording)

    def test_attitude_is_embedded_in_degrees(self):
        from offline_analysis.magnetic_calibration.calibrated_output import calibration_json
        document = json.loads(calibration_json(self.parameters, self.recording))
        stored = document['calibration_attitude']
        self.assertEqual((stored['columns'], stored['axis'], len(stored['degrees'])), (['yaw', 'pitch', 'roll'], 't', 80))
        attitude = self.recording.attitude_rad
        assert attitude is not None
        np.testing.assert_allclose(stored['degrees'][3], np.degrees(attitude[3]), atol=1e-3)

    def test_onyx_reads_a_file_with_attitude(self):
        parsed = parse_calibration(calibration_json(self.parameters, self.recording))
        self.assertEqual((parsed.method, parsed.sample_count), ('imu', 80))

    def test_no_attitude_without_a_recording_or_its_angles(self):
        self.assertNotIn('calibration_attitude', json.loads(calibration_json(self.parameters)))
        self.assertNotIn('calibration_attitude', json.loads(calibration_json(self.parameters, recording(False))))


class OfflineCalibrationTest(unittest.TestCase):
    """offline_calibration: calibrated E/N/U vectors, summary and angles for one scan.

    The /api/offline/calibrate endpoint around it is covered in integration/test_offline_calibrate_flow.py.
    """

    def setUp(self):
        from offline_analysis.magnetic_calibration.magnetic_calibrator import fit_recording
        _, soft_iron, misalignment, _ = model()
        self.recording = recording(True, soft_iron @ misalignment, count=80)
        self.text = calibration_json(fit_recording(self.recording), self.recording)

    def scan(self, with_attitude=True):
        """The synthetic recording back as a scan in nT and degrees."""
        from offline_analysis.scans.scan import Scan
        columns = {'t': tuple(self.recording.axis_values.tolist())}
        columns.update({name: tuple((self.recording.field_t[:, k] * 1e9).tolist()) for k, name in enumerate(('Bx', 'By', 'Bz'))})
        if with_attitude:
            attitude = self.recording.attitude_rad
            assert attitude is not None
            columns.update({name: tuple(np.degrees(attitude[:, k]).tolist())
                            for k, name in enumerate(('yaw_deg', 'pitch_deg', 'roll_deg'))})
        return Scan('t', columns)

    def test_vectors_are_the_earth_field_and_labels_enu(self):
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        result = offline_calibration(self.text, self.scan())
        self.assertEqual((result['count'], result['labels'], result['b_columns']), (80, ['E', 'N', 'U'], ['Bx', 'By', 'Bz']))
        np.testing.assert_allclose(result['field_nt'], np.tile(BAR_GYORA_ENU_NT, (80, 1)), atol=0.01)
        self.assertTrue(result['summary']['attitude_used'])

    def test_angles_come_from_the_same_document(self):
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        angles = offline_calibration(self.text, self.scan())['calibration']
        self.assertEqual((angles['method'], angles['sample_count']), ('imu', 80))
        self.assertEqual(angles['attitude']['columns'], ['yaw', 'pitch', 'roll'])
        self.assertAlmostEqual(angles['earth']['total_nt'], web_api.DEFAULT_REFERENCE_NT, delta=0.01)

    def test_scan_without_attitude_is_taken_as_level(self):
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        self.assertFalse(offline_calibration(self.text, self.scan(False))['summary']['attitude_used'])

    def test_errors(self):
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        from offline_analysis.scans.scan import Scan
        with self.assertRaisesRegex(ValueError, 'not a onyx-vector-calibration/1'):
            offline_calibration('{"format": "x"}', self.scan())
        with self.assertRaisesRegex(ValueError, 'no magnetic B-field'):
            offline_calibration(self.text, Scan('t', {'t': (0.0,), 'temp': (1.0,)}))


if __name__ == '__main__':
    unittest.main()
