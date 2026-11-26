"""Tests of web_api/scan_endpoints.py: loading, cropping and viewing scans through the API.

Needs onyx (the endpoints answer 503 without it; see test_router.py).
"""
import json
import unittest

from api_helpers import FIT_AVAILABLE, post
from analysis_helpers import em_json, mag_scan, vn100_scan
from imu_helpers import raw_magnetic_text
from offline_analysis.web_api.request_fields import RequestFields
from offline_analysis.web_api.scan_endpoints import ScanEndpoints

if not FIT_AVAILABLE:
    raise unittest.SkipTest('needs numpy and the onyx scans package')


class ScanEndpointsTest(unittest.TestCase):
    """POST /api/scan/load, /api/scan/crop and /api/offline/load without a server."""

    def test_load_reports_columns_and_sensor_picks(self):
        reply = post('/api/scan/load', {'name': 'scan.csv', 'text': mag_scan()})
        self.assertEqual(reply.status, 200)
        body = reply.body
        self.assertEqual((body['axis'], body['rows']), ('time [s]', 11))
        self.assertEqual(body['profiles']['magnetic'], {'b_axes': ['Bx [nT]', 'By [nT]', 'Bz [nT]'],
                                                        'imu': ['acc_x', 'gyro_z', 'yaw']})
        self.assertEqual(body['columns']['Bx [nT]'][2], 200.0)

    def test_load_sends_missing_values_as_null(self):
        reply = post('/api/scan/load', {'name': 'scan.csv', 'text': 't,Bx\n0,\n1,2\n'})
        self.assertEqual(reply.body['columns']['Bx'], [None, 2.0])
        json.dumps(reply.body, allow_nan=False)

    def test_load_vn100_recording(self):
        body = post('/api/scan/load', {'name': 'vn100.csv', 'text': vn100_scan()}).body
        self.assertEqual(body['axis'], 'received_utc')
        self.assertEqual(body['profiles']['magnetic']['b_axes'],
                         ['magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss'])
        self.assertEqual(body['attitude'], {'columns': ['yaw_deg', 'pitch_deg', 'roll_deg'], 'to_degrees': [1.0, 1.0, 1.0],
                                            'derived': None})

    def test_load_raw_imu_scan_reports_derived_angles(self):
        body = post('/api/scan/load', {'name': 'raw.csv', 'text': raw_magnetic_text()}).body
        attitude = body['attitude']
        self.assertEqual(attitude['columns'], ['imu_yaw_rad', 'imu_pitch_rad', 'imu_roll_rad'])
        self.assertEqual(attitude['derived']['source'], 'gyroscope')
        self.assertIn('imu_yaw_rad', body['profiles']['magnetic']['imu'])
        self.assertAlmostEqual(body['columns']['imu_yaw_rad'][-1], 1.0, delta=1e-9)  # 0.1 rad/s for 10 s

    def test_load_reports_attitude_in_degrees_or_none(self):
        text = 't,Bx,By,Bz,yaw_rad,pitch,roll\n0,1,2,3,0.1,0.2,0.3\n1,1,2,3,0.2,0.3,0.4\n'
        attitude = post('/api/scan/load', {'name': 'scan.csv', 'text': text}).body['attitude']
        self.assertEqual(attitude['columns'], ['yaw_rad', 'pitch', 'roll'])
        for factor in attitude['to_degrees']:  # radians by name, or by values within ±2π
            self.assertAlmostEqual(factor, 180 / 3.141592653589793, delta=1e-9)
        self.assertIsNone(post('/api/scan/load', {'name': 'scan.csv', 'text': mag_scan()}).body['attitude'])

    def test_crop_returns_csv_of_window_and_channels(self):
        reply = post('/api/scan/crop', {'name': 'scan.csv', 'text': mag_scan(), 'start': 2, 'end': 4,
                                        'channels': ['Bx [nT]', 'yaw']})
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.body['csv'].splitlines(),
                         ['time [s],Bx [nT],yaw', '2.0,200.0,4.0', '3.0,300.0,6.0', '4.0,400.0,8.0'])
        self.assertEqual((reply.body['rows'], reply.body['channels']), (3, 2))

    def test_offline_load_electromagnetic(self):
        body = post('/api/offline/load', {'sensor': 'electromagnetic', 'name': 'em.json', 'text': em_json(3)}).body
        self.assertEqual(body['count'], 3)
        # field_T real = [2, 4, 6] T and imag = [-2, 0, 0] T at row 2, sent in nT (1 nT = 1e-9 T).
        for got, want in zip(body['real_nt'][2] + body['imag_nt'][2], [2e9, 4e9, 6e9, -2e9, 0.0, 0.0]):
            self.assertAlmostEqual(got, want, delta=1e-3)


class DirectCallTest(unittest.TestCase):
    """ScanEndpoints methods called with RequestFields, without the router."""

    def test_load_reply_fields(self):
        reply = ScanEndpoints.load(RequestFields({'name': 'scan.csv', 'text': mag_scan()}))
        self.assertEqual(reply.status, 200)
        self.assertEqual(sorted(reply.body), ['attitude', 'axis', 'axis_values', 'channels', 'columns', 'name',
                                              'profiles', 'rows'])
        self.assertEqual(reply.body['axis_values'][:3], [0.0, 1.0, 2.0])

    def test_crop_counts_rows_and_channels(self):
        # Window [0, 10] keeps all 11 rows (time 0..10 s); two channels are kept.
        fields = RequestFields({'name': 'scan.csv', 'text': mag_scan(), 'start': 0, 'end': 10,
                                'channels': ['Bx [nT]', 'By [nT]']})
        body = ScanEndpoints.crop(fields).body
        self.assertEqual((body['rows'], body['channels']), (11, 2))
        self.assertEqual(body['csv'].splitlines()[0], 'time [s],Bx [nT],By [nT]')

    def test_offline_magnetic_vectors_in_nt(self):
        fields = RequestFields({'sensor': 'magnetic', 'name': 'scan.csv', 'text': mag_scan()})
        body = ScanEndpoints.offline(fields).body
        self.assertEqual((body['sensor'], body['count'], body['field_nt'][2]), ('magnetic', 11, [200.0, -2.0, 5.0]))

    def test_unknown_sensor_raises_for_the_router_to_answer_400(self):
        with self.assertRaisesRegex(ValueError, 'unknown sensor'):
            ScanEndpoints.offline(RequestFields({'sensor': 'gravity', 'name': 'scan.csv', 'text': mag_scan()}))


if __name__ == '__main__':
    unittest.main()
