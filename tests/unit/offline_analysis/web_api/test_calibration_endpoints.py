"""Tests of web_api/calibration_endpoints.py: status, fitting and applying calibrations.

Fitting checks run only where numpy and the onyx calibration package import.
"""
import unittest

from api_helpers import FIT_AVAILABLE, calibration_text, post
from offline_analysis import web_api
from offline_analysis.web_api.calibration_endpoints import MISSING_CALIBRATION, CalibrationEndpoints
from analysis_helpers import mag_scan


class CalibrationEndpointsTest(unittest.TestCase):
    """Calibration status, fit, fit-file and apply without a server."""

    def test_status_reports_defaults(self):
        body = web_api.handle('GET', '/api/calibration/status').body
        self.assertEqual(body['available'], FIT_AVAILABLE)
        self.assertAlmostEqual(body['default_reference_nt'], 45201.52, delta=0.01)
        self.assertEqual((body['methods'], body['mountings']), (['auto', 'ellipsoid', 'imu'], ['enu', 'body']))

    @unittest.skipIf(FIT_AVAILABLE, 'onyx calibration is installed here')
    def test_fit_without_onyx_is_503_with_the_reason(self):
        reply = post('/api/calibration/fit', {})
        self.assertEqual(reply.status, 503)
        self.assertIn('onyx calibration package', reply.body['error'])

    @unittest.skipIf(FIT_AVAILABLE, 'onyx calibration is installed here')
    def test_fit_file_without_onyx_is_503(self):
        self.assertEqual(post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': mag_scan()}).status, 503)

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_fit_file_uses_imu_when_the_file_has_attitude(self):
        import numpy as np
        from calibration_model import model
        reply = post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': calibration_text(True),
                                                    'reference_nt': web_api.DEFAULT_REFERENCE_NT})
        self.assertEqual(reply.status, 200, reply.body)
        summary = reply.body['summary']
        self.assertEqual((summary['method'], summary['rows'], reply.body['file_rows']), ('imu', 80, 80))
        self.assertEqual(summary['attitude_columns'], ['yaw [deg]', 'pitch [deg]', 'roll [deg]'])
        np.testing.assert_allclose(summary['offset_nt'], model()[0], atol=0.01)
        self.assertTrue(reply.body['calibration_json'].startswith('{\n  "format": "onyx-vector-calibration/1"'))

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_fit_file_uses_ellipsoid_without_attitude_and_counts_skipped_rows(self):
        text = calibration_text(False)
        lines = text.splitlines()
        lines[5] = lines[5].split(',')[0] + ',,1,2'  # one row with a missing Bx
        reply = post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': '\n'.join(lines) + '\n',
                                                    'mounting': 'enu'})
        self.assertEqual(reply.status, 200, reply.body)
        summary = reply.body['summary']
        self.assertEqual((summary['method'], summary['attitude_columns']), ('ellipsoid', []))
        self.assertEqual((summary['rows'], reply.body['file_rows']), (79, 80))
        self.assertIsNone(summary['earth_field_enu_nt'])

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_fit_file_without_field_columns_is_400(self):
        reply = post('/api/calibration/fit-file', {'name': 'cal.csv', 'text': 't,temperature\n0,1\n1,2\n'})
        self.assertEqual(reply.status, 400)
        self.assertIn('no magnetic B-field', reply.body['error'])

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_fit_then_apply_round_trip(self):
        from calibration_model import model
        import numpy as np
        offset = model()[0]
        text = calibration_text(True)
        channels = ['Bx [nT]', 'By [nT]', 'Bz [nT]', 'yaw [deg]', 'pitch [deg]', 'roll [deg]']
        reply = post('/api/calibration/fit', {'name': 'cal.csv', 'text': text, 'start': 0, 'end': 79,
                                               'channels': channels, 'method': 'auto',
                                               'reference_nt': web_api.DEFAULT_REFERENCE_NT, 'mounting': 'enu'})
        self.assertEqual(reply.status, 200, reply.body)
        summary = reply.body['summary']
        self.assertEqual((summary['method'], summary['rows']), ('imu', 80))
        np.testing.assert_allclose(summary['offset_nt'], offset, atol=0.01)
        applied = post('/api/calibration/apply', {'name': 'cal.csv', 'text': text,
                                                  'calibration': reply.body['calibration_json']})
        self.assertEqual(applied.status, 200, applied.body)
        self.assertTrue(applied.body['csv'].startswith('time [s],B_east_nT,B_north_nT,B_up_nT,B_total_nT\n'))
        self.assertAlmostEqual(applied.body['summary']['b_total_mean_nt'], web_api.DEFAULT_REFERENCE_NT, delta=0.01)
        # Deselecting the attitude channels makes 'auto' fall back to the ellipsoid method.
        ellipsoid = post('/api/calibration/fit', {'name': 'cal.csv', 'text': text, 'start': 0, 'end': 79,
                                                   'channels': channels[:3], 'reference_nt': 45000})
        self.assertEqual(ellipsoid.body['summary']['method'], 'ellipsoid')

    @unittest.skipUnless(FIT_AVAILABLE, 'needs numpy and the onyx calibration package')
    def test_apply_rejects_a_foreign_calibration(self):
        reply = post('/api/calibration/apply', {'name': 'scan.csv', 'text': mag_scan(), 'calibration': '{"format":"x"}'})
        self.assertEqual(reply.status, 400)

class SupportTests(unittest.TestCase):
    """CalibrationEndpoints.support and status agree with each other."""

    def test_status_reports_the_support_check(self):
        available, reason = CalibrationEndpoints.support()
        body = CalibrationEndpoints.status().body
        self.assertEqual((body['available'], body['reason']), (available, reason))
        if not available:
            self.assertIn(MISSING_CALIBRATION, reason or '')


if __name__ == '__main__':
    unittest.main()
