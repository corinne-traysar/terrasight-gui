"""Unit tests for dashboard/bench_handler.py: route tables, status and page list.

The handler is built without a socket and given fake instruments, so only the
routing and status logic is exercised (HTTP delivery is in the integration test).
"""
import unittest

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)
from dashboard import bench_handler
from dashboard.bench_handler import PAGES, RESUME_PATHS, WEB, BenchHandler
from dashboard.web_assets import ASSETS


class FakeInstrument:
    """Answers ``snapshot`` with a fixed dict and records control calls."""

    def __init__(self, snapshot):
        self.state, self.calls = snapshot, []

    def snapshot(self, after=0):
        return dict(self.state)

    def set_paused(self, paused):
        self.calls.append(('paused', paused))
        return {'pause_requested': paused}

    def start(self):
        self.calls.append('start')
        return {'running': True}

    def stop(self):
        self.calls.append('stop')
        return {'running': False}


def handler():
    """A BenchHandler with fake MC95A, AP230, VN-100 control, measurements and Pi health."""
    built = object.__new__(BenchHandler)
    built.mc = FakeInstrument({'status': 'paused', 'channels': []})
    built.ap = FakeInstrument({'status': 'stopped', 'samples': [[1, 2, 3, 4, 5]], 'latest': [1, 2, 3, 4, 5], 'count': 1})
    built.vn = FakeInstrument({'running': False, 'device': '/dev/fake'})
    built.measurements = FakeInstrument({'status': 'stopped'})
    built.health = FakeInstrument({'temperature_C': 55.0})
    return built


class BenchStatusTests(unittest.TestCase):
    def test_status_names_every_instrument_and_the_pi(self):
        status = handler()._bench_status()
        self.assertEqual(sorted(status), ['ap230', 'health', 'mc95a', 'vn100'])
        self.assertEqual(status['health'], {'temperature_C': 55.0})
        self.assertEqual(status['mc95a'], {'status': 'paused'})

    def test_vn100_status_joins_control_state_and_measurement_status(self):
        self.assertEqual(handler()._bench_status()['vn100'],
                         {'running': False, 'device': '/dev/fake', 'status': 'stopped'})

    def test_ap230_status_leaves_out_sample_data(self):
        self.assertEqual(handler()._bench_status()['ap230'], {'status': 'stopped', 'count': 1})


class RouteTests(unittest.TestCase):
    def test_get_routes_cover_every_bench_api(self):
        self.assertEqual(sorted(handler()._get_routes()),
                         ['/api/ap230', '/api/bench', '/api/health', '/api/live', '/api/telemetry'])

    def test_pause_and_resume_drive_the_mc95a(self):
        built = handler()
        routes = built._control_routes()
        self.assertEqual(routes['/api/acquisition/pause'](), {'pause_requested': True})
        routes['/api/acquisition/resume']()
        self.assertEqual(built.mc.calls, [('paused', True), ('paused', False)])

    def test_start_and_stop_reach_the_right_instrument(self):
        built = handler()
        routes = built._control_routes()
        routes['/api/vn100/start']()
        routes['/api/ap230/stop']()
        self.assertEqual((built.vn.calls, built.ap.calls), (['start'], ['stop']))

    def test_every_resume_path_is_a_control_route(self):
        self.assertTrue(set(RESUME_PATHS) <= set(handler()._control_routes()))

    def test_stop_paths_are_never_blocked_by_the_thermal_guard(self):
        self.assertFalse({'/api/vn100/stop', '/api/ap230/stop', '/api/acquisition/pause'} & set(RESUME_PATHS))


class PageTests(unittest.TestCase):
    def test_every_page_file_exists_in_the_web_folder(self):
        for route, (name, mime) in PAGES.items():
            with self.subTest(route=route):
                self.assertIsNotNone(ASSETS.find(name), name)
                self.assertIn(mime, ('text/html', 'text/javascript'))

    def test_web_folder_is_the_repository_web_folder(self):
        self.assertEqual(WEB.name, 'web')
        self.assertTrue((WEB.parent / 'dashboard' / 'bench_handler.py').is_file())

    def test_handler_builds_on_the_vn100_handler(self):
        from dashboard.vn100_app import Handler
        self.assertTrue(issubclass(bench_handler.BenchHandler, Handler))


if __name__ == '__main__':
    unittest.main()
