import math
import time
import unittest
from mc95a import MC95AReader, summarize


class MC95ATests(unittest.TestCase):
    def test_ac_rms_removes_offset_but_retains_sine_amplitude(self):
        values = [.003 + .002*math.sin(2*math.pi*50*i/10240) for i in range(1024)]
        stats = summarize(values)
        self.assertAlmostEqual(stats['mean_V'], .003)
        self.assertAlmostEqual(stats['ac_rms_V'], .002/math.sqrt(2))
        self.assertAlmostEqual(stats['rms_V'], math.sqrt(.003**2+.002**2/2))
        self.assertFalse(stats['clipping'])

    def test_invalid_data_and_clipping(self):
        for values in ([], [float('nan')], [float('inf')]):
            with self.assertRaises(ValueError):
                summarize(values)
        self.assertTrue(summarize([0, 4.995])['clipping'])

    def test_bounded_history_and_stale_state(self):
        reader = MC95AReader()
        self.assertEqual(reader.snapshot()['status'], 'waiting')
        for _ in range(605):
            reader.publish(([.001, -.001], [.002, -.002]), 10240)
        snapshot = reader.snapshot()
        self.assertEqual(snapshot['status'], 'live')
        self.assertEqual(snapshot['samples_per_channel'], 1210)
        self.assertEqual(len(snapshot['channels'][0]['history']), 600)
        self.assertEqual(len(snapshot['channels'][1]['history']), 600)
        self.assertAlmostEqual(snapshot['channels'][1]['latest']['ac_rms_V'], .002)
        self.assertEqual(snapshot['channels'][0]['latest']['sequence'], snapshot['channels'][1]['latest']['sequence'])
        reader.last_received = time.monotonic()-2
        self.assertEqual(reader.snapshot()['status'], 'stale')
        reader.error = 'ADC overrun'
        self.assertEqual(reader.snapshot()['status'], 'error')


if __name__ == '__main__':
    unittest.main()


class ChannelSeparationTests(unittest.TestCase):
    def test_simultaneous_channels_retain_independent_spectra(self):
        reader = MC95AReader()
        for block in range(8):
            offset = block*1024
            first = [.001*math.sin(2*math.pi*125*(i+offset)/10240) for i in range(1024)]
            second = [.002*math.sin(2*math.pi*250*(i+offset)/10240) for i in range(1024)]
            reader.publish((first,second),10240)
        channels = reader.snapshot()['channels']
        self.assertEqual(channels[0]['spectrum']['peak_Hz'],125)
        self.assertEqual(channels[1]['spectrum']['peak_Hz'],250)
        self.assertAlmostEqual(channels[1]['spectrum']['band_rms_V']/channels[0]['spectrum']['band_rms_V'],2,places=6)

    def test_channel_length_mismatch_is_not_published(self):
        reader = MC95AReader()
        with self.assertRaises(ValueError):
            reader.publish(([1,2],[1]),10240)
        self.assertEqual(reader.snapshot()['sequence'],0)
