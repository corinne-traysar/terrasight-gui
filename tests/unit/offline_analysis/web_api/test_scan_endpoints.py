"""Tests of web_api/scan_endpoints.py: loading, cropping and viewing scans through the API.
"""
import json
import unittest

from api_helpers import post
from offline_analysis.scans.scan import Scan
from offline_analysis.web_api.scan_endpoints import ScanEndpoints
from analysis_helpers import em_json, mag_scan, vn100_scan


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
        self.assertEqual(body['attitude'], {'columns': ['yaw_deg', 'pitch_deg', 'roll_deg'], 'to_degrees': [1.0, 1.0, 1.0]})

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
        self.assertEqual(body['real_nt'][2], [2e9, 4e9, 6e9])
        self.assertEqual(body['imag_nt'][2], [-2e9, 0.0, 0.0])

class AttitudeTests(unittest.TestCase):
    """ScanEndpoints.attitude: yaw/pitch/roll columns and their factors to degrees."""

    def test_radian_columns_get_180_over_pi_and_missing_angles_give_none(self):
        scan = Scan('t', {'t': (0.0, 1.0), 'yaw_rad': (0.1, 0.2), 'pitch_rad': (0.0, 0.1), 'roll_rad': (0.0, 0.0)})
        attitude = ScanEndpoints.attitude(scan) or {}
        self.assertEqual(attitude.get('columns'), ['yaw_rad', 'pitch_rad', 'roll_rad'])
        for factor in attitude.get('to_degrees', []):
            self.assertAlmostEqual(factor, 57.29577951308232, delta=1e-9)  # 180 / pi
        self.assertIsNone(ScanEndpoints.attitude(Scan('t', {'t': (0.0,), 'Bx': (1.0,)})))


if __name__ == '__main__':
    unittest.main()
