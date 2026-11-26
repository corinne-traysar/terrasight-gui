"""MC95A port RMS units and raw waveform gaps, with no invented field phase."""
import json
import unittest

try:
    from scans import ScanData
    from offline_analysis.scans.recorded_channels import RecordedChannels
except ImportError:
    RecordedChannels = None


@unittest.skipIf(RecordedChannels is None, 'onyx analysis dependencies unavailable')
class RecordedChannelsTest(unittest.TestCase):
    """Independent scalar exports are distinct from three-axis AC phasors."""

    def test_rms_field_and_voltage_units(self):
        """Keep nT RMS, and convert 0.002 V to 2000 microvolts exactly once."""
        data = ScanData({'time': [0, 1], 'mc95a_s1_field_rms_nT': [20, 30],
                         'mc95a_s1_ac_rms_V': [.002, .003]})
        result = RecordedChannels.viewer(data, 'recording.csv')
        self.assertEqual(result['scalar_traces'][0]['values'], [20, 30])
        self.assertAlmostEqual(result['scalar_traces'][1]['values'][0], 2000, delta=1e-9)
        self.assertNotIn('real_nt', result)
        self.assertIn('not synchronized', result['notice'])

    def test_other_scans_are_not_claimed(self):
        """Ordinary magnetic files continue through the normal vector loader."""
        self.assertIsNone(RecordedChannels.viewer(ScanData({'time': [0], 'Bx': [2]}), 'a.csv'))

    def test_raw_blocks_preserve_voltage_and_gaps(self):
        """Missing block 2 inserts a missing value between ADC blocks 1 and 3."""
        text = json.dumps({'metadata': {'instrument': 'mc95a'}, 'waveforms': [
            {'sequence': sequence, 'channels': [{'label': 'S1', 'adc_V': [.1, -.2]}]}
            for sequence in (1, 3)]})
        graph = RecordedChannels.waveforms(text)[0]
        self.assertEqual(graph['values'], [.1, -.2, None, .1, -.2])
        self.assertEqual(graph['unit'], 'V ADC')

    def test_empty_waveforms_are_allowed(self):
        """A CSV crop or a summary-only JSON still opens without raw blocks."""
        self.assertEqual(RecordedChannels.waveforms('{}'), [])
