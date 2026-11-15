import json
import os
from pathlib import Path
import pty
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app import make_server
from vn100 import Measurements, PacketStream, VN100Reader, decode_packet


# Actual packet captured from the bench sensor; expected field order from UM001.
PACKET = b'$VNYMR,-083.439,+017.941,-014.121,-00.0699,+00.1379,+00.3359,+02.985,+02.457,-08.997,-00.013756,-00.019038,-00.007451*69\r\n'


def eventually(check, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        time.sleep(.02)
    raise AssertionError('condition not reached before timeout')


class DecoderTests(unittest.TestCase):
    def test_real_packet_has_documented_order(self):
        values = decode_packet(PACKET)
        self.assertEqual(values['attitude'], [-83.439, 17.941, -14.121])
        self.assertEqual(values['magnetic'], [-.0699, .1379, .3359])
        self.assertEqual(values['acceleration'], [2.985, 2.457, -8.997])
        self.assertEqual(values['angular_rate'], [-.013756, -.019038, -.007451])

    def test_corruption_is_rejected(self):
        for packet in (PACKET.replace(b'083', b'084'), PACKET[:-5], b'$VNYMR,1*GG', b'garbage'):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                decode_packet(packet)

    def test_nonfinite_values_are_rejected_even_with_valid_checksum(self):
        payload = b'VNYMR,' + b','.join([b'nan'] + [b'0'] * 11)
        checksum = 0
        for byte in payload:
            checksum ^= byte
        with self.assertRaises(ValueError):
            decode_packet(b'$' + payload + b'*' + ('%02X' % checksum).encode())

    def test_chunk_boundaries_and_initial_noise(self):
        stream = PacketStream()
        self.assertEqual(stream.feed(b'partial data\r\n' + PACKET[:12]), [])
        lines = stream.feed(PACKET[12:] + PACKET)
        self.assertEqual([decode_packet(line) for line in lines], [decode_packet(PACKET)] * 2)

    def test_resynchronizes_after_incomplete_packet(self):
        stream = PacketStream()
        stream.feed(PACKET[:30])
        self.assertEqual(decode_packet(stream.feed(PACKET)[0]), decode_packet(PACKET))

    def test_unterminated_noise_is_bounded(self):
        stream = PacketStream()
        stream.feed(b'x' * 100000)
        self.assertLessEqual(len(stream.pending), 1024)
        self.assertEqual(decode_packet(stream.feed(PACKET)[0]), decode_packet(PACKET))


class StateTests(unittest.TestCase):
    def test_bounded_history_and_browser_cursor(self):
        state = Measurements(capacity=3)
        for _ in range(5):
            state.add(decode_packet(PACKET))
        snapshot = state.snapshot(after=1)
        self.assertEqual([x['sequence'] for x in snapshot['samples']], [3, 4, 5])
        self.assertTrue(snapshot['history_truncated'])
        self.assertEqual([x['sequence'] for x in state.snapshot(after=4)['samples']], [5])

    def test_waiting_live_stale_and_disconnected(self):
        state = Measurements(stale_after=.03)
        self.assertEqual(state.snapshot()['status'], 'disconnected')
        state.connection(True)
        self.assertEqual(state.snapshot()['status'], 'waiting')
        state.add(decode_packet(PACKET))
        self.assertEqual(state.snapshot()['status'], 'live')
        time.sleep(.05)
        self.assertEqual(state.snapshot()['status'], 'stale')
        state.connection(False)
        self.assertEqual(state.snapshot()['status'], 'disconnected')
        state.connection(True)
        self.assertEqual(state.snapshot()['status'], 'waiting')
        self.assertIsNotNone(state.snapshot()['latest'])  # Historical data remains available.


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


class SerialTests(unittest.TestCase):
    def test_disconnect_and_reconnect_with_replaced_device(self):
        masters, slaves = [], []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sensor'

            def device():
                master, slave = pty.openpty()
                masters.append(master)
                slaves.append(slave)
                if path.is_symlink():
                    path.unlink()
                path.symlink_to(os.ttyname(slave))
                return master

            master = device()
            state = Measurements()
            reader = VN100Reader(str(path), state, retry_seconds=.05)
            reader.start()
            try:
                eventually(lambda: state.snapshot()['status'] == 'waiting')
                os.write(master, PACKET[:30])
                time.sleep(.02)
                os.write(master, PACKET[30:])
                eventually(lambda: state.snapshot()['received'] == 1)
                os.close(master)
                masters.remove(master)
                eventually(lambda: state.snapshot()['status'] == 'disconnected')
                master = device()
                eventually(lambda: state.snapshot()['status'] == 'waiting')
                os.write(master, PACKET)
                eventually(lambda: state.snapshot()['received'] == 2)
                self.assertEqual(state.snapshot()['latest']['attitude'], [-83.439, 17.941, -14.121])
            finally:
                reader.stop()
                for fd in masters + slaves:
                    os.close(fd)


if __name__ == '__main__':
    unittest.main()
