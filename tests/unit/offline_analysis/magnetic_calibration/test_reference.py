"""Tests of magnetic_calibration/reference.py: the WMM2025 Bar-Gyora reference field and option names."""
import math
import unittest

from offline_analysis.magnetic_calibration.reference import (BAR_GYORA_ENU_NT, DEFAULT_REFERENCE_NT, METHODS,
                                                             MOUNTING_NAMES)


class ReferenceTests(unittest.TestCase):
    """The reference |B| is the norm of the east/north/up field in nT."""

    def test_default_reference_is_the_field_magnitude(self):
        # sqrt(2608^2 + 30063^2 + 33654^2) = 45201.52 nT (hand-computed).
        self.assertAlmostEqual(DEFAULT_REFERENCE_NT, math.sqrt(2608.0**2 + 30063.0**2 + 33654.0**2), delta=1e-9)
        self.assertAlmostEqual(DEFAULT_REFERENCE_NT, 45201.52, delta=0.01)

    def test_field_points_north_and_down_in_israel(self):
        east, north, up = BAR_GYORA_ENU_NT
        self.assertGreater(north, abs(east), 'mostly northward horizontal field')
        self.assertLess(up, 0, 'northern hemisphere: the field dips downward')

    def test_option_names(self):
        self.assertEqual(METHODS, ('auto', 'ellipsoid', 'imu'))
        self.assertEqual(MOUNTING_NAMES, ('enu', 'body'))


if __name__ == '__main__':
    unittest.main()
