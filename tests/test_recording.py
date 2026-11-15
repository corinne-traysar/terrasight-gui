import csv
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json

from app import make_server
from vn100 import Measurements

VALUES = dict(attitude=[1, 2, 3], magnetic=[.1, .2, .3],
              acceleration=[4, 5, 6], angular_rate=[.01, .02, .03])


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.m = Measurements(capacity=2, recording_directory=self.temp.name)
        self.m.connection(True)
        self.m.add(VALUES)

    def test_boundaries_full_rate_and_unique_files(self):
        first = self.m.start_recording()
        self.assertEqual(self.m.start_recording()['path'], first['path'])
        for _ in range(10):
            self.m.add(VALUES)
        result = self.m.stop_recording()
        self.m.add(VALUES)
        with open(result['path']) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 10)  # independent of the two-row GUI buffer
        self.assertEqual([int(r['sequence']) for r in rows], list(range(2, 12)))
        self.assertEqual(rows[0]['yaw_deg'], '1')
        self.assertTrue(rows[0]['received_utc'].endswith('+00:00'))
        self.assertFalse(result['active'])
        second = self.m.start_recording()
        self.assertNotEqual(first['path'], second['path'])
        self.m.stop_recording()
        self.assertEqual(len(list(Path(self.temp.name).glob('*.csv'))), 2)

    def test_disconnect_keeps_file_open_and_resumes(self):
        self.m.start_recording()
        self.m.add(VALUES)
        self.m.connection(False)
        self.assertTrue(self.m.snapshot()['recording']['active'])
        self.m.connection(True)
        self.m.add(VALUES)
        self.assertEqual(self.m.stop_recording()['rows'], 2)

    def test_start_requires_live_data(self):
        self.m.connection(False)
        with self.assertRaises(ValueError):
            self.m.start_recording()

    def test_write_failure_does_not_stop_acquisition(self):
        self.m.start_recording()
        self.m.recording.writer = Mock()
        self.m.recording.writer.writerow.side_effect = OSError('disk full')
        self.m.add(VALUES)
        state = self.m.snapshot()
        self.assertEqual(state['received'], 2)
        self.assertFalse(state['recording']['active'])
        self.assertIn('disk full', state['recording']['error'])

    def test_http_controls_and_origin_guard(self):
        server = make_server('127.0.0.1', 0, self.m)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:%d' % server.server_port
        def post(action, origin):
            return urlopen(Request(base + '/api/recording/' + action, data=b'',
                                   headers={'Origin': origin}), timeout=2)
        with self.assertRaises(HTTPError) as error:
            post('start', 'http://other-site')
        self.assertEqual(error.exception.code, 403)
        with post('start', base) as response:
            self.assertTrue(json.load(response)['active'])
        self.m.add(VALUES)
        with post('stop', base) as response:
            self.assertEqual(json.load(response)['rows'], 1)
