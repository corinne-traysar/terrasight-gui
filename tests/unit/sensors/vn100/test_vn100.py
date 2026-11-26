"""Tests of sensors/vn100.py: packet decoding and the measurement store (the reader is in test_vn100_reader)."""
import time
import unittest

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)
from sensors.vn100 import Measurements, PacketStream, decode_packet
from vn100_helpers import PACKET


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


if __name__ == '__main__':
    unittest.main()
