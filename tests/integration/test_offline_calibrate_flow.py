"""Integration: fit a calibration file through the API, then calibrate an Offline Data scan with it.

Runs only where numpy and the onyx calibration package import.
"""
import json
import unittest

from api_helpers import FIT_AVAILABLE, calibration_text, post
from offline_analysis import web_api
from analysis_helpers import mag_scan


class OfflineCalibrateTest(unittest.TestCase):
    """/api/offline/calibrate and the yaw/pitch/roll that fitted calibration files now carry."""

    def setUp(self):
        if not FIT_AVAILABLE:
            return
        self.text = calibration_text(True)
        fitted = post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': self.text,
                                                     'reference_nt': web_api.DEFAULT_REFERENCE_NT})
        self.assertEqual(fitted.status, 200, fitted.body)
        self.calibration = fitted.body['calibration_json']

    def calibrate(self, name, text, calibration):
        """POST /api/offline/calibrate."""
        return post('/api/offline/calibrate', {'name': name, 'text': text, 'calibration': calibration})

    def test_route_needs_the_calibration_package(self):
        self.assertTrue(web_api.handles('POST', '/api/offline/calibrate'))
        self.assertFalse(web_api.handles('GET', '/api/offline/calibrate'))
        self.assertIn('/api/offline/calibrate', web_api.NEEDS_CALIBRATION)

    @unittest.skipIf(FIT_AVAILABLE, 'onyx calibration is installed here')
    def test_without_onyx_is_503(self):
        self.assertEqual(post('/api/offline/calibrate', {'name': 'scan.csv', 'text': mag_scan()}).status, 503)

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_fitted_file_stores_the_calibration_scan_attitude(self):
        stored = json.loads(self.calibration)['calibration_attitude']
        self.assertEqual((stored['columns'], stored['axis'], len(stored['degrees'])),
                         (['yaw [deg]', 'pitch [deg]', 'roll [deg]'], 'time [s]', 80))
        without = post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': calibration_text(False),
                                                      'reference_nt': web_api.DEFAULT_REFERENCE_NT})
        self.assertNotIn('calibration_attitude', json.loads(without.body['calibration_json']))

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_calibrated_field_is_the_earth_field_in_enu(self):
        import numpy as np
        from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT
        reply = self.calibrate('cal.csv', self.text, self.calibration)
        self.assertEqual(reply.status, 200, reply.body)
        body = reply.body
        self.assertEqual((body['source'], body['count'], body['labels']), ('cal.csv', 80, ['E', 'N', 'U']))
        np.testing.assert_allclose(body['field_nt'], np.tile(BAR_GYORA_ENU_NT, (80, 1)), atol=0.01)
        self.assertTrue(body['summary']['attitude_used'])
        self.assertEqual(body['b_columns'], ['Bx [nT]', 'By [nT]', 'Bz [nT]'])
        json.dumps(body, allow_nan=False)

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_reply_carries_the_calibration_angles(self):
        from offline_analysis.magnetic_calibration.rotation_math import euler_zyx_deg
        from calibration_model import model
        _, _, misalignment, ned_to_enu = model()
        angles = self.calibrate('cal.csv', self.text, self.calibration).body['calibration']
        expected = euler_zyx_deg((ned_to_enu @ misalignment.T).tolist())
        for key in ('yaw', 'pitch', 'roll'):
            self.assertAlmostEqual(abs(angles['mounting_deg'][key]), abs(expected[key]), delta=0.01, msg=key)
        self.assertEqual((angles['method'], angles['reflected']), ('imu', False))
        self.assertAlmostEqual(angles['earth']['total_nt'], web_api.DEFAULT_REFERENCE_NT, delta=0.01)
        self.assertEqual(len(angles['attitude']['degrees']), 80)

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_scan_without_attitude_is_taken_as_level(self):
        reply = self.calibrate('scan.csv', mag_scan(), self.calibration)
        self.assertEqual(reply.status, 200, reply.body)
        self.assertFalse(reply.body['summary']['attitude_used'])
        self.assertEqual(reply.body['count'], 11)

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_bad_requests_are_400(self):
        for body in ({'name': 'scan.csv', 'text': mag_scan(), 'calibration': '{"format":"x"}'},
                     {'name': 'scan.csv', 'text': 't,temp\n0,1\n', 'calibration': self.calibration},
                     {'name': 'scan.csv', 'text': mag_scan()}):
            with self.subTest(body=body):
                self.assertEqual(post('/api/offline/calibrate', body).status, 400)

if __name__ == '__main__':
    unittest.main()
