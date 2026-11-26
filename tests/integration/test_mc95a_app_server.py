"""Integration tests for dashboard/mc95a_app.py: a real MC95AReader behind the real HTTP Handler.

Also runs the script by path from outside the repository to check it can import its packages.
"""
from functools import partial
import gzip
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dashboard.mc95a_app import Handler
from dashboard.web_assets import ASSETS
from sensors.mc95a import MC95AReader

ROOT = Path(__file__).resolve().parents[2]
RATE_HZ = 10240.0


class MC95AServerTests(unittest.TestCase):
    def setUp(self):
        # Two published blocks without hardware: CH0 at +1 mV DC, CH1 at -2 mV DC.
        self.reader = MC95AReader()
        for _ in range(2):
            self.reader.publish([[.001] * 1024, [-.002] * 1024], RATE_HZ)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, reader=self.reader))
        self.base = 'http://127.0.0.1:%d' % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, method='GET', headers=None):
        """(status, headers, body bytes); HTTP errors are returned, not raised."""
        try:
            with urlopen(Request(self.base + path, method=method, headers=headers or {}), timeout=5) as reply:
                return reply.status, reply.headers, reply.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def same_origin(self):
        return {'Origin': self.base}

    def test_live_reports_published_blocks_in_volts(self):
        status, headers, body = self.request('/api/live')
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual((data['status'], data['sequence'], data['samples_per_channel']), ('live', 2, 2048))
        means = [channel['latest']['mean_V'] for channel in data['channels']]
        self.assertAlmostEqual(means[0], .001, delta=1e-12)
        self.assertAlmostEqual(means[1], -.002, delta=1e-12)

    def test_cursor_returns_only_newer_history(self):
        data = json.loads(self.request('/api/live?after=1')[2])
        for channel in data['channels']:
            self.assertEqual([point['sequence'] for point in channel['history']], [2])

    def test_gzip_is_used_when_the_browser_accepts_it(self):
        status, headers, body = self.request('/api/live', headers={'Accept-Encoding': 'gzip'})
        self.assertEqual((status, headers['Content-Encoding']), (200, 'gzip'))
        self.assertEqual(json.loads(gzip.decompress(body))['sequence'], 2)

    def test_invalid_query_is_a_400(self):
        self.assertEqual(self.request('/api/live?after=-1')[0], 400)

    def test_page_is_served_from_the_web_folder(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertTrue(headers['Content-Type'].startswith('text/html'))
        self.assertEqual(body, ASSETS.read('mc95a.html'))

    def test_unknown_path_is_a_404(self):
        self.assertEqual(self.request('/../sensors/mc95a.py')[0], 404)

    def test_pause_then_resume_from_the_same_origin(self):
        status, _, body = self.request('/api/acquisition/pause', 'POST', self.same_origin())
        self.assertEqual((status, json.loads(body)['pause_requested']), (200, True))
        self.assertTrue(self.reader.pause_requested.is_set())
        body = self.request('/api/acquisition/resume', 'POST', self.same_origin())[2]
        self.assertFalse(json.loads(body)['pause_requested'])

    def test_control_without_origin_is_refused_and_changes_nothing(self):
        self.assertEqual(self.request('/api/acquisition/pause', 'POST')[0], 403)
        self.assertFalse(self.reader.pause_requested.is_set())

    def test_unknown_control_is_a_404(self):
        self.assertEqual(self.request('/api/acquisition/reboot', 'POST', self.same_origin())[0], 404)


class RunByPathTests(unittest.TestCase):
    def test_help_runs_from_outside_the_repository(self):
        # -I drops the working directory from sys.path, so only the script's own bootstrap can find packages.
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'dashboard' / 'mc95a_app.py'), '--help'],
                                    cwd=folder, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--start-paused', result.stdout)


if __name__ == '__main__':
    unittest.main()
