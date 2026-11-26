"""Integration tests for sensors/mc95a_capture_three.py main(): fake HATs -> raw.csv + metadata.json.

Real MC95AReader acquisition thread, real spectrum, fake ``daqhats``; the home folder
is redirected to a temporary directory so nothing is written to the real one.
Inputs: S1 (HAT 0 CH0) = 2 mV peak at 150 Hz, S2 (HAT 0 CH1) = 2 mV DC, S3 (HAT 1 CH0) = 5 V DC.
"""
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mc95a_helpers import RATE_HZ, SignalHat, constant, fake_daqhats, tone

try:
    import numpy  # noqa: F401  (required by the capture module)
except ImportError as error:
    raise unittest.SkipTest('capture module needs numpy: %s' % error)

from sensors import mc95a_capture_three

AMPLITUDE_V, TONE_HZ = .002, 150
SAMPLES = 51200  # 5 s * 10240 Hz
# After the first second is discarded, 40960 samples = 4 s = 600 whole 150 Hz cycles,
# so the tone's mean is 0 and its RMS is A / sqrt(2) = 1414.2136 uV.
TONE_RMS_UV = AMPLITUDE_V / math.sqrt(2) * 1e6


class ThreeSensorCaptureTests(unittest.TestCase):
    def capture(self, hat1_overrun=False):
        """Run main() against fake HATs; return the folder used as the home directory."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        hats = [SignalHat({0: tone(AMPLITUDE_V, TONE_HZ), 1: constant(.002)}),
                SignalHat({0: constant(5.0)}, overrun=hat1_overrun)]
        with patch.dict(sys.modules, {'daqhats': fake_daqhats(hats)}), \
                patch.object(Path, 'home', return_value=Path(folder.name)), \
                contextlib.redirect_stdout(io.StringIO()):
            mc95a_capture_three.main()
        return Path(folder.name)

    def output(self):
        """(capture folder, metadata dict, csv rows) from one successful capture."""
        folders = list((self.capture() / 'bench-data' / 'mc95a').iterdir())
        self.assertEqual(len(folders), 1)
        with (folders[0] / 'raw.csv').open(newline='') as stream:
            rows = list(csv.reader(stream))
        return folders[0], json.loads((folders[0] / 'metadata.json').read_text()), rows

    def test_raw_csv_holds_five_seconds_with_time_in_seconds(self):
        folder, _, rows = self.output()
        self.assertTrue(folder.name.startswith('three_sensor_'))
        self.assertEqual(rows[0], ['sample_index', 'time_from_own_scan_start_s', 'S1_H0_CH0_V', 'S2_H0_CH1_V', 'S3_H1_CH0_V'])
        self.assertEqual(len(rows) - 1, SAMPLES)
        self.assertAlmostEqual(float(rows[1 + 10240][1]), 1.0, delta=1e-12)  # sample 10240 at 10240 Hz

    def test_raw_csv_columns_follow_the_physical_ports(self):
        _, _, rows = self.output()
        expected_s1 = AMPLITUDE_V * math.sin(2 * math.pi * TONE_HZ * 1 / RATE_HZ)
        self.assertAlmostEqual(float(rows[2][2]), expected_s1, delta=1e-15)
        self.assertEqual({row[3] for row in rows[1:]}, {'0.002'})
        self.assertEqual({row[4] for row in rows[1:]}, {'5.0'})

    def test_metadata_labels_rate_iepe_and_timing(self):
        folder, metadata, _ = self.output()
        self.assertEqual(metadata['csv'], str(folder / 'raw.csv'))
        self.assertEqual((metadata['samples_per_channel'], metadata['sample_rate_Hz_per_channel']), (SAMPLES, RATE_HZ))
        self.assertEqual(metadata['iepe'], 0)
        self.assertIn('cross-board phase alignment unverified', metadata['timing'])
        self.assertIn('No field calibration applied', metadata['analysis_note'])
        ports = [(c['sensor'], c['board_address'], c['channel']) for c in metadata['channels']]
        self.assertEqual(ports, [('S1', 0, 0), ('S2', 0, 1), ('S3', 1, 0)])

    def test_tone_channel_rms_band_and_peak_in_microvolts(self):
        s1 = self.output()[1]['channels'][0]
        self.assertAlmostEqual(s1['ac_rms_uV'], TONE_RMS_UV, delta=.01)
        self.assertAlmostEqual(s1['band_50_1000_rms_uV'], TONE_RMS_UV, delta=.5)  # Hann, on-bin tone
        self.assertAlmostEqual(s1['tone_rms_uV']['150'], TONE_RMS_UV, delta=.5)
        self.assertAlmostEqual(s1['tone_rms_uV']['50'], 0, delta=1)
        self.assertEqual(s1['peak_Hz'], TONE_HZ)
        self.assertFalse(s1['clipping'])

    def test_dc_channels_have_no_ac_and_only_5_v_clips(self):
        s2, s3 = self.output()[1]['channels'][1:]
        for channel in (s2, s3):
            self.assertAlmostEqual(channel['ac_rms_uV'], 0, delta=1e-6)
            self.assertAlmostEqual(channel['band_50_1000_rms_uV'], 0, delta=1e-6)
        self.assertEqual((s2['clipping'], s3['clipping']), (False, True))  # clip at |v| >= 4.99 V

    def test_adc_overrun_aborts_without_writing_files(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        hats = [SignalHat({0: constant(0), 1: constant(0)}), SignalHat({0: constant(0)}, overrun=True)]
        with patch.dict(sys.modules, {'daqhats': fake_daqhats(hats)}), \
                patch.object(Path, 'home', return_value=Path(folder.name)), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(RuntimeError, 'ADC overrun on HAT 1'):
            mc95a_capture_three.main()
        self.assertFalse((Path(folder.name) / 'bench-data').exists())
        self.assertEqual(hats[1].actions[-2:], ['stop', 'cleanup'])


if __name__ == '__main__':
    unittest.main()
