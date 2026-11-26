"""Tests of scans/viewer_data.py: the Offline Data vectors in nT for both sensor types.
"""
import math
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from analysis_helpers import mag_json, mag_scan, phasor_json, text_scan, vn100_scan  # noqa: E402
from imu_helpers import raw_magnetic_text  # noqa: E402
from offline_analysis.scans.viewer_data import viewer_data  # noqa: E402

FIELD = ['field_T_0', 'field_T_1', 'field_T_2']
COMBINED = ['combined_field_T_0', 'combined_field_T_1', 'combined_field_T_2']


class ViewerDataTest(unittest.TestCase):
    """viewer_data gives nT vectors and axis labels for the Offline Data view."""

    def test_magnetic_json_uses_combined_field_in_nt(self):
        # Earth (0, 3e-5, -4e-5) T plus anomaly (1e-9, 0, 0) T -> (1, 30000, -40000) nT.
        data = viewer_data('magnetic', 'mag.json', mag_json([[1e-9, 0.0, 0.0]]))
        self.assertEqual((data['labels'], data['count'], data['source']), (['E', 'N', 'U'], 1, 'mag.json'))
        for got, want in zip(data['field_nt'][0], (1.0, 30000.0, -40000.0)):
            self.assertAlmostEqual(got, want, delta=1e-6)

    def test_magnetic_csv_in_nt_uses_xyz(self):
        data = viewer_data('magnetic', 'scan.csv', mag_scan())
        self.assertEqual(data['labels'], ['x', 'y', 'z'])
        self.assertEqual(data['field_nt'][2], [200.0, -2.0, 5.0])  # helper row t = 2

    def test_vn100_recording_gauss_becomes_nt(self):
        data = viewer_data('magnetic', 'vn100.csv', vn100_scan(2))
        for got, want in zip(data['field_nt'][0], (20000.0, -10000.0, 40000.0)):
            self.assertAlmostEqual(got, want, delta=1e-6)

    def test_east_named_columns_use_enu(self):
        text = text_scan(['t', 'B_east', 'B_north', 'B_up'], [[0, 1, 2, 3]])
        self.assertEqual(viewer_data('magnetic', 'scan.csv', text)['labels'], ['E', 'N', 'U'])

    def test_missing_value_is_none(self):
        text = text_scan(['t', 'Bx', 'By', 'Bz'], [[0, '', 2, 3], [1, 1, 2, 3]])
        self.assertEqual(viewer_data('magnetic', 'scan.csv', text)['field_nt'][0], [None, 2.0, 3.0])

    def test_electromagnetic_json_phasor_in_nt(self):
        data = viewer_data('electromagnetic', 'em.json', phasor_json([([1e-9, 0, 0], [0, 2e-9, 0])]))
        self.assertAlmostEqual(data['real_nt'][0][0], 1.0, delta=1e-12)
        self.assertAlmostEqual(data['imag_nt'][0][1], 2.0, delta=1e-12)
        self.assertEqual(data['labels'], ['E', 'N', 'U'])

    def test_attitude_is_sent_in_degrees_with_the_vectors(self):
        attitude = viewer_data('magnetic', 'vn100.csv', vn100_scan(3))['attitude']
        self.assertEqual(attitude['columns'], ['yaw_deg', 'pitch_deg', 'roll_deg'])
        self.assertEqual(attitude['degrees'], [[0.0, 1.0, -2.0], [10.0, 1.0, -2.0], [20.0, 1.0, -2.0]])
        self.assertEqual(attitude['axis'], 'received_utc')

    def test_attitude_in_radians_becomes_degrees_and_missing_angles_are_none(self):
        text = text_scan(['t', 'Bx', 'By', 'Bz', 'yaw_rad', 'pitch_rad', 'roll_rad'],
                         [[0, 1, 2, 3, math.pi / 2, '', 0], [1, 1, 2, 3, 0, 0, -math.pi]])
        attitude = viewer_data('magnetic', 'scan.csv', text)['attitude']
        self.assertEqual(attitude['degrees'], [[90.0, None, 0.0], [0.0, 0.0, -180.0]])
        self.assertEqual(attitude['axis_values'], [0.0, 1.0])

    def test_attitude_is_none_without_all_three_angles(self):
        self.assertIsNone(viewer_data('magnetic', 'scan.csv', mag_scan())['attitude'])  # yaw only
        self.assertIsNone(viewer_data('electromagnetic', 'em.json', phasor_json([([1e-9, 0, 0], [0, 0, 0])]))['attitude'])

    def test_raw_imu_scan_sends_derived_attitude(self):
        attitude = viewer_data('magnetic', 'raw.csv', raw_magnetic_text())['attitude']
        self.assertEqual(attitude['columns'], ['imu_yaw_rad', 'imu_pitch_rad', 'imu_roll_rad'])
        self.assertAlmostEqual(attitude['degrees'][-1][0], math.degrees(1.0), delta=1e-3)  # 0.1 rad/s, 10 s

    def test_onyx_calibrated_scan_is_labelled_enu(self):
        import json
        document = dict(format='onyx-scan/1', sensor='magnetic', axis='t', metadata={'calibration': {}},
                        samples=[dict(t=0.0, field_t_x=1e-9, field_t_y=0.0, field_t_z=0.0)])
        self.assertEqual(viewer_data('magnetic', 'cal.json', json.dumps(document))['labels'], ['E', 'N', 'U'])

    def test_wrong_sensor_file_and_unknown_sensor_raise(self):
        with self.assertRaisesRegex(ValueError, 'no electromagnetic phasor'):
            viewer_data('electromagnetic', 'scan.csv', mag_scan())
        with self.assertRaisesRegex(ValueError, 'unknown sensor'):
            viewer_data('gravity', 'scan.csv', mag_scan())

if __name__ == '__main__':
    unittest.main()
