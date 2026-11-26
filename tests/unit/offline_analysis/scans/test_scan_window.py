"""Tests of scans/scan_window.py: cropping to a window and the chosen channels, and CSV output."""
import math
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from scans import ScanData  # noqa: E402

from analysis_helpers import mag_scan  # noqa: E402
from offline_analysis.scans.scan_loader import LOADER  # noqa: E402
from offline_analysis.scans.scan_window import ScanWindow, csv_text  # noqa: E402


class ApplyTest(unittest.TestCase):
    """ScanWindow.apply keeps the window's rows and exactly the chosen channels."""

    def setUp(self):
        self.data = LOADER.data('scan.csv', mag_scan())  # time 0..10 s, Bx = 100 t

    def test_window_edges_are_included_in_either_order(self):
        for start, end in ((2, 4), (4, 2)):
            cropped = ScanWindow(start, end, ['Bx [nT]']).apply(self.data)
            self.assertEqual(list(cropped.axis_values), [2.0, 3.0, 4.0])
            self.assertEqual(cropped.channels, ['Bx [nT]'])

    def test_angles_are_dropped_unless_chosen(self):
        data = ScanData({'t': [0, 1], 'Bx': [1, 2], 'yaw': [0, 1], 'pitch': [0, 0], 'roll': [0, 0]}, 't')
        self.assertIsNone(ScanWindow(0, 1, ['Bx']).apply(data).attitude_columns)
        self.assertIsNotNone(ScanWindow(0, 1, ['Bx', 'yaw', 'pitch', 'roll']).apply(data).attitude_columns)

    def test_bad_windows_raise(self):
        with self.assertRaisesRegex(ValueError, 'at least one channel'):
            ScanWindow(0, 1, [])
        with self.assertRaisesRegex(ValueError, 'no sample'):
            ScanWindow(1.2, 1.8, ['Bx [nT]']).apply(self.data)
        with self.assertRaisesRegex(ValueError, 'unknown channels: nope'):
            ScanWindow(0, 1, ['nope']).apply(self.data)


class CsvTextTest(unittest.TestCase):
    """csv_text writes the axis first and NaN as an empty cell."""

    def test_csv(self):
        data = ScanData({'t': [0.0, 1.0], 'Bx': [1.5, math.nan]}, 't')
        self.assertEqual(csv_text(data), 't,Bx\n0.0,1.5\n1.0,\n')


if __name__ == '__main__':
    unittest.main()
