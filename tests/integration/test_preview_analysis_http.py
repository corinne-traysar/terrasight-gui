"""Integration: the local preview answers the analysis endpoints itself over HTTP and stays read-only.
"""
import gzip
import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from api_helpers import preview
from offline_analysis import web_api
from analysis_helpers import mag_scan


class PreviewHTTPTest(unittest.TestCase):
    """The local preview answers the analysis endpoints itself and stays read-only for controls."""

    def setUp(self):
        self.upstream_reads = []
        reads = self.upstream_reads

        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                reads.append(self.path)
                self.send_error(500)

            do_POST = do_GET

            def log_message(self, *_):
                pass

        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.server = preview.PreviewServer(('127.0.0.1', 0), preview.Preview,
                                            f'http://127.0.0.1:{self.upstream.server_port}')
        self.threads = []
        for server in (self.upstream, self.server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        for server in (self.server, self.upstream):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = (response.status, response.read(), response.getheader('Content-Encoding'))
        connection.close()
        return result

    def test_pages_are_served(self):
        for path, marker in (('/calibration', b'Fit Magnetic Calibration'), ('/offline', b'Offline Data'),
                             ('/calibration.js', b'/api/scan/load'), ('/offline.js', b'/api/offline/load'),
                             ('/scan-plot.js', b'envelope'), ('/', b'data-src="/calibration"'),
                             ('/angles', b'Calibration and Scan Angles'), ('/angles.js', b'terrasight-angles'),
                             ('/offline-calibration.js', b'/api/offline/calibrate')):
            with self.subTest(path=path):
                status, body, _ = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(marker, body)

    def test_analysis_runs_locally_with_same_origin_and_gzip(self):
        body = json.dumps({'name': 'scan.csv', 'text': mag_scan()}).encode()
        headers = {'Origin': self.origin, 'Content-Type': 'application/json', 'Accept-Encoding': 'gzip'}
        status, content, encoding = self.request('/api/scan/load', 'POST', body, headers)
        self.assertEqual((status, encoding), (200, 'gzip'))
        self.assertEqual(json.loads(gzip.decompress(content))['rows'], 11)
        status, content, _ = self.request('/api/calibration/status')
        self.assertEqual(status, 200)
        self.assertIn('default_reference_nt', json.loads(content))
        self.assertEqual(self.upstream_reads, [])

    def test_analysis_needs_the_preview_origin(self):
        body = json.dumps({'name': 'scan.csv', 'text': mag_scan()}).encode()
        self.assertEqual(self.request('/api/scan/load', 'POST', body)[0], 403)
        self.assertEqual(self.request('/api/scan/load', 'POST', body, {'Origin': 'http://evil.example'})[0], 403)

    def test_oversized_body_is_refused(self):
        headers = {'Origin': self.origin, 'Content-Length': str(web_api.MAX_BODY_BYTES + 1)}
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.putrequest('POST', '/api/scan/load')
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 413)
        connection.close()

    def test_acquisition_controls_stay_read_only(self):
        self.assertEqual(self.request('/api/acquisition/pause', 'POST', b'', {'Origin': self.origin})[0], 403)
        self.assertEqual(self.upstream_reads, [])

if __name__ == '__main__':
    unittest.main()
