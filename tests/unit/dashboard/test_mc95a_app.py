"""Unit tests for dashboard/mc95a_app.py: query validation, static routes and startup checks.

The HTTP round trip is covered in tests/integration/test_mc95a_app_server.py.
"""
import sys
import unittest
from unittest.mock import patch

from dashboard import mc95a_app
from dashboard.web_assets import ASSETS


class RecordingReader:
    """Stands in for MC95AReader and records the snapshot arguments it receives."""

    def __init__(self):
        self.calls = []

    def snapshot(self, after=None, spectrum_max_hz=None):
        self.calls.append((after, spectrum_max_hz))
        return {'after': after, 'spectrum_max_hz': spectrum_max_hz}


def snapshot_args(path):
    """The (after, spectrum_max_hz) pair display_snapshot passes on for ``path``."""
    reader = RecordingReader()
    mc95a_app.display_snapshot(reader, path)
    return reader.calls[0]


class DisplaySnapshotTests(unittest.TestCase):
    def test_no_query_requests_full_history_and_spectrum(self):
        self.assertEqual(snapshot_args('/api/live'), (None, None))

    def test_query_values_are_parsed_to_int_cursor_and_float_hz(self):
        after, maximum = snapshot_args('/api/live?after=7&spectrum_max_hz=250.5')
        self.assertEqual(after, 7)
        self.assertIsInstance(after, int)
        self.assertAlmostEqual(maximum, 250.5, delta=1e-12)

    def test_cursor_zero_is_accepted_on_the_boundary(self):
        self.assertEqual(snapshot_args('/api/live?after=0')[0], 0)

    def test_negative_cursor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid history cursor'):
            snapshot_args('/api/live?after=-1')

    def test_non_integer_cursor_is_rejected(self):
        with self.assertRaises(ValueError):
            snapshot_args('/api/live?after=bad')

    def test_spectrum_range_limits_zero_and_100_khz_are_accepted(self):
        for value, expected in (('0', 0.0), ('100000', 100000.0)):
            with self.subTest(value=value):
                self.assertAlmostEqual(snapshot_args('/api/live?spectrum_max_hz=' + value)[1], expected, delta=1e-9)

    def test_spectrum_range_outside_limits_or_not_finite_is_rejected(self):
        for value in ('-0.1', '100000.1', 'nan', 'inf', '-inf'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Invalid spectrum range'):
                snapshot_args('/api/live?spectrum_max_hz=' + value)

    def test_rejected_query_never_reaches_the_reader(self):
        reader = RecordingReader()
        with self.assertRaises(ValueError):
            mc95a_app.display_snapshot(reader, '/api/live?after=-5')
        self.assertEqual(reader.calls, [])


class StaticFilesTests(unittest.TestCase):
    def test_every_route_points_to_an_existing_web_file(self):
        for route, (filename, mime) in mc95a_app.FILES.items():
            with self.subTest(route=route):
                self.assertIsNotNone(ASSETS.find(filename), filename)
                self.assertIn(mime, ('text/html', 'text/javascript', 'text/css'))

    def test_web_folder_is_the_repository_web_folder(self):
        self.assertEqual(mc95a_app.WEB.name, 'web')
        self.assertTrue((mc95a_app.WEB.parent / 'dashboard' / 'mc95a_app.py').is_file())


class MainTests(unittest.TestCase):
    def test_missing_daqhats_fails_before_any_server_starts(self):
        with patch.object(sys, 'argv', ['mc95a_app.py']), \
                patch.dict(sys.modules, {'daqhats': None}), \
                patch.object(mc95a_app, 'ThreadingHTTPServer') as server, \
                patch.object(mc95a_app, 'MC95AReader') as reader:
            with self.assertRaises(ImportError):
                mc95a_app.main()
        server.assert_not_called()
        reader.assert_not_called()

    def test_invalid_hat_address_is_rejected_by_the_parser(self):
        with patch.object(sys, 'argv', ['mc95a_app.py', '--address', '8']), \
                patch('sys.stderr'), self.assertRaises(SystemExit):
            mc95a_app.main()


if __name__ == '__main__':
    unittest.main()
