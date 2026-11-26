"""Integration tests for dashboard/bench_handler.py behind a real bench server.

Real MC95A and AP230 readers (never started), Pi health with injected readings
and the VN-100 control with a fake serial reader, served by ``make_bench_server``.
Covers page routing (including the live-calibration scripts that fall through
to the VN-100 handler), status APIs, origin checks and the thermal guard.
"""
import json
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from dashboard import vn100_control
from dashboard.bench_app import make_bench_server
from dashboard.web_assets import ASSETS
from dashboard.pi_health import PiHealth
from dashboard.vn100_control import BenchMeasurements, VNControl
from sensors.mc95a import MC95AReader

LIVE_CALIBRATION_SCRIPTS = ('/live-calibration.js', '/live-calibration-sensors.js', '/live-calibration-panel.js')


class BenchServerTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(vn100_control, 'VN100Reader')
        self.reader_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.temperature = [60.0]
        self.health = PiHealth(temperature_reader=lambda: self.temperature[0], throttle_reader=lambda: 0)
        self.health.sample()
        measurements = BenchMeasurements()
        self.mc = MC95AReader(third=True)
        self.mc.set_paused(True)
        self.vn = VNControl('/dev/fake-vn100', measurements)
        self.server = make_bench_server('127.0.0.1', 0, measurements, self.mc, self.health, self.vn)
        self.base = 'http://127.0.0.1:%d' % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method='GET', origin=False):
        """(status, headers, body bytes); HTTP errors are returned, not raised."""
        headers = {'Origin': self.base} if origin else {}
        try:
            with urlopen(Request(self.base + path, method=method, headers=headers), timeout=5) as reply:
                return reply.status, reply.headers, reply.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def test_dashboard_pages_are_served(self):
        for path, marker in (('/', b'Terrasight Bench'), ('/vn100', b'IMU - VN100'), ('/ap230', b'Mag - AP230'),
                             ('/offline', b'Offline Data')):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(marker, body)

    def test_live_views_load_the_live_calibration_panel(self):
        for path in ('/vn100', '/ap230'):
            body = self.request(path)[2]
            self.assertIn(b'id="live-calibration"', body)
            for script in LIVE_CALIBRATION_SCRIPTS:
                self.assertIn(b'src="' + script.encode() + b'"', body)

    def test_live_calibration_scripts_are_served_as_javascript(self):
        for script in LIVE_CALIBRATION_SCRIPTS:
            status, headers, body = self.request(script)
            self.assertEqual(status, 200, script)
            self.assertTrue(headers['Content-Type'].startswith('text/javascript'))
            self.assertEqual(body, ASSETS.read(script.lstrip('/')))

    def test_bench_status_reports_stopped_instruments(self):
        data = json.loads(self.request('/api/bench')[2])
        self.assertEqual(data['vn100'], {'running': False, 'device': '/dev/fake-vn100', 'status': 'stopped'})
        self.assertEqual(data['health']['temperature_C'], 60.0)

    def test_negative_ap230_cursor_is_a_400(self):
        self.assertEqual(self.request('/api/telemetry?ap_after=-1')[0], 400)

    def test_vn100_samples_fall_through_to_the_vn100_handler(self):
        status, _, body = self.request('/api/samples?after=0')
        self.assertEqual((status, json.loads(body)['status']), (200, 'stopped'))

    def test_controls_need_the_same_origin(self):
        self.assertEqual(self.request('/api/vn100/start', 'POST')[0], 403)
        self.reader_class.assert_not_called()

    def test_vn100_start_from_the_same_origin_starts_the_reader(self):
        status, _, body = self.request('/api/vn100/start', 'POST', origin=True)
        self.assertEqual((status, json.loads(body)['running']), (200, True))
        self.reader_class.return_value.start.assert_called_once_with()
        self.request('/api/vn100/stop', 'POST', origin=True)
        self.reader_class.return_value.stop.assert_called_once_with()

    def test_thermal_guard_refuses_resume_but_allows_stop(self):
        self.temperature[0] = 76.0
        self.health.sample()
        self.assertEqual(self.request('/api/vn100/start', 'POST', origin=True)[0], 409)
        self.assertEqual(self.request('/api/acquisition/resume', 'POST', origin=True)[0], 409)
        self.assertEqual(self.request('/api/vn100/stop', 'POST', origin=True)[0], 200)
        self.reader_class.assert_not_called()

    def test_unknown_page_is_a_404(self):
        self.assertEqual(self.request('/../dashboard/bench_app.py')[0], 404)


if __name__ == '__main__':
    unittest.main()
