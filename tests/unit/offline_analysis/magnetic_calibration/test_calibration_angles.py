"""Calibration angles and scan yaw/pitch/roll for the Offline Data angle window.

Pure Python: runs without numpy or onyx. Documents are hand-built
``onyx-vector-calibration/1`` objects.
"""
import json
import math
import unittest

from offline_analysis.magnetic_calibration.calibration_angles import (ATTITUDE_KEY, calibration_angles, earth_angles, recording_attitude,
                                         scan_attitude)
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT
from offline_analysis.scans.scan_io import parse_scan
from analysis_helpers import mag_scan, vn100_scan

ENU_MOUNTING = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]


def document(**changes):
    """An ellipsoid calibration with the ENU mounting and a 1.02 scale, plus ``changes``."""
    base = {'format': 'onyx-vector-calibration/1', 'method': 'ellipsoid', 'offset_t': [0.0, 0.0, 0.0],
            'correction': [[1.02 * v for v in row] for row in ENU_MOUNTING], 'reference_magnitude_t': 4.5e-5,
            'residual_rms_t': 1e-9, 'sample_count': 80, 'output_frame': 'sensor', 'earth_field_enu_t': None}
    return {**base, **changes}


class ScanAttitudeTest(unittest.TestCase):
    """scan_attitude reads the yaw/pitch/roll columns in degrees."""

    def attitude(self, name, text):
        """The attitude record of the file, failing when it has none."""
        record = scan_attitude(parse_scan(name, text))
        assert record is not None
        return record

    def test_vn100_degrees_pass_through(self):
        record = self.attitude('vn100.csv', vn100_scan(3))
        self.assertEqual(record['columns'], ['yaw_deg', 'pitch_deg', 'roll_deg'])
        self.assertEqual(record['degrees'], [[0.0, 1.0, -2.0], [10.0, 1.0, -2.0], [20.0, 1.0, -2.0]])
        self.assertEqual(record['axis'], 'received_utc')

    def test_radians_become_degrees_and_missing_values_are_none(self):
        record = scan_attitude(parse_scan('s.csv', 't,yaw_rad,pitch_rad,roll_rad\n0,0.5,,0\n1,1,0,-0.25\n'))
        self.assertAlmostEqual(record['degrees'][1][0], math.degrees(1.0), places=3)
        self.assertIsNone(record['degrees'][0][1])
        self.assertEqual(record['axis_values'], [0.0, 1.0])
        json.dumps(record, allow_nan=False)

    def test_scan_without_all_three_angles_has_none(self):
        self.assertIsNone(scan_attitude(parse_scan('scan.csv', mag_scan())))

    def test_recording_attitude_converts_radians(self):
        record = recording_attitude('t', [0.0, 1.0], [[math.pi / 2, 0.0, -math.pi], [0.1, 0.2, 0.3]], ('y', 'p', 'r'))
        self.assertEqual(record['degrees'][0], [90.0, 0.0, -180.0])
        self.assertEqual((record['axis'], record['columns']), ('t', ['y', 'p', 'r']))


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
