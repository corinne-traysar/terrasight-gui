"""Tests of dashboard/vn100_app.py: the VN-100 page files, sample snapshot, event stream and main."""
import json
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)
from dashboard import vn100_app
from dashboard.vn100_app import make_server
from sensors.vn100 import Measurements, decode_packet
from vn100_helpers import PACKET


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.state = Measurements()
        self.state.connection(True)
        self.state.add(decode_packet(PACKET))
        self.server = make_server('127.0.0.1', 0, self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%s' % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_display_delivery_preserves_measurements(self):
        with urlopen(self.url + '/api/samples?after=0') as response:
            data = json.load(response)
        self.assertEqual(data['samples'][0]['acceleration'], [2.985, 2.457, -8.997])
        self.assertEqual(data['latest'], data['samples'][0])
        self.assertEqual(data['status'], 'live')

    def test_multiple_browsers_do_not_consume_each_others_samples(self):
        for _ in range(2):
            with urlopen(self.url + '/api/samples?after=0') as response:
                self.assertEqual(len(json.load(response)['samples']), 1)
        self.assertEqual(self.state.snapshot()['received'], 1)

    def test_continuous_stream_delivers_new_samples_without_new_requests(self):
        with urlopen(self.url + '/api/events', timeout=2) as response:
            self.assertEqual(response.headers['Content-Type'], 'text/event-stream')

            def event():
                while True:
                    line = response.readline()
                    if not line:
                        self.fail('stream ended before the next update')
                    if line.startswith(b'data: '):
                        return json.loads(line[6:])

            first = event()
            self.assertEqual(first['latest']['acceleration'], [2.985, 2.457, -8.997])
            self.state.add(decode_packet(PACKET))
            second = event()
            self.assertEqual([sample['sequence'] for sample in second['samples']], [2])
            self.assertEqual(second['latest']['sequence'], 2)

    def test_invalid_cursor_and_unlisted_paths(self):
        for path in ('/api/samples?after=-1', '/api/samples?after=bad', '/../vn100.py'):
            with self.subTest(path=path), self.assertRaises(HTTPError):
                urlopen(self.url + path)

class MainTests(unittest.TestCase):
    """main: read the device, serve until Ctrl+C, then stop the reader and recording."""

    def test_serves_until_ctrl_c_and_shuts_everything_down(self):
        argv = ['vn100_app.py', '--device', '/dev/vn', '--port', '8124', '--recording-dir', 'captures']
        with patch.object(sys, 'argv', argv), patch('builtins.print'), \
                patch.object(vn100_app, 'make_server') as server, \
                patch.object(vn100_app, 'VN100Reader') as reader, \
                patch.object(vn100_app, 'Measurements') as measurements:
            server.return_value.serve_forever.side_effect = KeyboardInterrupt
            vn100_app.main()
        self.assertEqual(str(measurements.call_args.kwargs['recording_directory']), 'captures')
        self.assertEqual(server.call_args.args[:2], ('0.0.0.0', 8124))
        self.assertEqual(reader.call_args.args[0], '/dev/vn')
        reader.return_value.start.assert_called_once()
        reader.return_value.stop.assert_called_once()
        measurements.return_value.stop_recording.assert_called_once()
        server.return_value.server_close.assert_called_once()

    def test_device_is_required(self):
        with patch.object(sys, 'argv', ['vn100_app.py']), patch('sys.stderr'), self.assertRaises(SystemExit):
            vn100_app.main()


if __name__ == '__main__':
    unittest.main()
