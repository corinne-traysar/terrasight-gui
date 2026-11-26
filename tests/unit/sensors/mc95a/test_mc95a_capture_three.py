"""Unit tests for sensors/mc95a_capture_three.py: CaptureReader's five-second sample window.

Blocks are published directly, without hardware or the acquisition thread. The full
capture (``main``) is covered in tests/integration/test_mc95a_three_sensor_capture.py.
"""
import unittest

try:
    import numpy  # noqa: F401  (required by the capture module)
except ImportError as error:
    raise unittest.SkipTest('capture module needs numpy: %s' % error)

from sensors.mc95a_capture_three import CaptureReader

RATE_HZ = 10.0  # A low rate keeps the window small: 5 s * 10 Hz = 50 samples per channel.


def block(start, size=20):
    """One block for S1/S2/S3: S1 counts samples from ``start``, S2 = S1 + 1000, S3 = S1 + 2000 (volts)."""
    first = [float(n) / 1000 for n in range(start, start + size)]
    return [first, [v + 1 for v in first], [v + 2 for v in first]]


class CaptureReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = CaptureReader()

    def test_three_inputs_are_hat0_ch0_ch1_and_hat1_ch0(self):
        self.assertEqual(self.reader.inputs, [(0, 0), (0, 1), (1, 0)])

    def test_target_is_five_seconds_of_samples_at_the_first_block_rate(self):
        self.reader.publish(block(0), RATE_HZ)
        self.assertEqual(self.reader.target, 50)  # round(5 s * 10 Hz)

    def test_target_at_the_mcc172_rate(self):
        self.reader.publish(block(0), 10240.0)
        self.assertEqual(self.reader.target, 51200)  # 5 s * 10240 Hz

    def test_capture_is_not_done_before_the_target(self):
        for start in (0, 20):
            self.reader.publish(block(start), RATE_HZ)
        self.assertEqual(len(self.reader.raw[0]), 40)
        self.assertFalse(self.reader.done.is_set())
        self.assertFalse(self.reader.quit.is_set())

    def test_last_block_is_trimmed_to_exactly_the_target(self):
        for start in (0, 20, 40):
            self.reader.publish(block(start), RATE_HZ)
        # 60 samples arrived; only the first 50 (indices 0..49) belong to the capture.
        self.assertEqual([len(channel) for channel in self.reader.raw], [50, 50, 50])
        self.assertAlmostEqual(self.reader.raw[0][-1], .049, delta=1e-12)

    def test_reaching_the_target_ends_acquisition(self):
        for start in (0, 20, 40):
            self.reader.publish(block(start), RATE_HZ)
        self.assertTrue(self.reader.done.is_set())
        self.assertTrue(self.reader.quit.is_set())

    def test_samples_stay_on_their_own_channel_in_order(self):
        for start in (0, 20):
            self.reader.publish(block(start), RATE_HZ)
        for channel, offset in enumerate((0, 1, 2)):
            expected = [n / 1000 + offset for n in range(40)]
            for got, want in zip(self.reader.raw[channel], expected):
                self.assertAlmostEqual(got, want, delta=1e-12)

    def test_every_block_still_reaches_the_live_snapshot(self):
        for start in (0, 20, 40):
            self.reader.publish(block(start), RATE_HZ)
        state = self.reader.snapshot()
        self.assertEqual(state['samples_per_channel'], 60)  # untrimmed: 3 blocks * 20
        self.assertEqual(state['sample_rate_Hz'], RATE_HZ)


if __name__ == '__main__':
    unittest.main()
