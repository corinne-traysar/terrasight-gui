import unittest
import numpy as np
from mc95a_spectrum import spectrum, nominal_field_nT


class SpectrumTests(unittest.TestCase):
    def test_known_tone_frequency_power_and_field_units(self):
        rate = 10240
        t = np.arange(8192)/rate
        # 125 Hz is exactly on a bin. 2 mV peak plus a large DC offset.
        result = spectrum(.3 + .002*np.sin(2*np.pi*125*t), rate)
        self.assertEqual(result['peak_Hz'], 125)
        self.assertAlmostEqual(result['bin_Hz'], 1.25)
        self.assertAlmostEqual(result['band_rms_V'], .002/np.sqrt(2), places=8)
        self.assertAlmostEqual(nominal_field_nT(result['band_rms_V']), 200/np.sqrt(2), places=4)
        self.assertEqual(nominal_field_nT(.001, 2), 50)

    def test_boundary_tones_retain_full_rms(self):
        t = np.arange(8192)/10240
        for frequency in (50, 1000):
            result = spectrum(.002*np.sin(2*np.pi*frequency*t), 10240)
            self.assertAlmostEqual(result['band_rms_V'], .002/np.sqrt(2), places=8)

    def test_excludes_out_of_band_power(self):
        t = np.arange(8192)/10240
        result = spectrum(.01*np.sin(2*np.pi*2000*t) + .001*np.sin(2*np.pi*250*t), 10240)
        self.assertAlmostEqual(result['band_rms_V'], .001/np.sqrt(2), places=8)
        self.assertEqual(result['peak_Hz'], 2000)

    def test_zero_signal_and_invalid_inputs(self):
        result = spectrum(np.zeros(8192), 10240)
        self.assertIsNone(result['peak_Hz'])
        self.assertEqual(result['band_rms_V'], 0)
        for values, rate in (([], 10240), ([float('nan')]*8,10240), ([0]*8,0)):
            with self.assertRaises(ValueError):
                spectrum(values, rate)
        with self.assertRaises(ValueError):
            nominal_field_nT(.001, 0)
