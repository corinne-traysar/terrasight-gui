"""Tests of web_api/router.py: which requests the API answers and how mistakes are reported.
"""
import unittest

from api_helpers import post
from offline_analysis import web_api
from offline_analysis.web_api.router import NEEDS_CALIBRATION, POST_ROUTES, WebApiRouter
from analysis_helpers import mag_scan


class RouterTest(unittest.TestCase):
    """web_api.handle and web_api.handles without a server."""

    def test_client_mistakes_are_400_with_a_message(self):
        cases = [('/api/scan/crop', {'name': 'scan.csv', 'text': mag_scan(), 'start': 1.2, 'end': 1.8,
                                     'channels': ['Bx [nT]']}, 'no samples'),
                 ('/api/scan/crop', {'name': 'scan.csv', 'text': mag_scan(), 'start': 0, 'end': 1,
                                     'channels': 'Bx'}, 'channels must be a list'),
                 ('/api/scan/crop', {'name': 'scan.csv', 'text': mag_scan(), 'start': 'a', 'end': 1,
                                     'channels': []}, 'start must be a finite number'),
                 ('/api/scan/load', {'name': 'scan.csv'}, 'text must be text'),
                 ('/api/offline/load', {'sensor': 'electromagnetic', 'name': 'scan.csv', 'text': mag_scan()},
                  'no electromagnetic phasor')]
        for path, body, message in cases:
            with self.subTest(message=message):
                reply = post(path, body)
                self.assertEqual(reply.status, 400)
                self.assertIn(message, reply.body['error'])
        self.assertEqual(web_api.handle('POST', '/api/scan/load', b'not json').status, 400)
        self.assertEqual(web_api.handle('POST', '/api/scan/load', b'[1]').status, 400)

    def test_routes(self):
        self.assertTrue(web_api.handles('GET', '/api/calibration/status?x=1'))
        self.assertTrue(web_api.handles('POST', '/api/offline/load'))
        self.assertFalse(web_api.handles('GET', '/api/scan/load'))
        self.assertFalse(web_api.handles('POST', '/api/acquisition/pause'))
        self.assertEqual(web_api.handle('GET', '/api/scan/load').status, 404)

class WebApiRouterTests(unittest.TestCase):
    """A fresh router instance: GET/POST matching and unknown paths."""

    def test_handles_matches_method_and_path(self):
        router = WebApiRouter()
        self.assertTrue(router.handles('GET', '/api/calibration/status?cache=no'))
        self.assertFalse(router.handles('PUT', '/api/scan/load'))
        self.assertTrue(NEEDS_CALIBRATION <= set(POST_ROUTES), 'every onyx route is a POST route')
        self.assertEqual(router.handle('POST', '/api/unknown', b'{}').status, 404)


if __name__ == '__main__':
    unittest.main()
