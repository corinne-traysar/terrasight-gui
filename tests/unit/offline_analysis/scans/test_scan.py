"""Tests of scans/scan.py: the Scan table, its sample axis and cropping."""
import math
import unittest

from offline_analysis.scans.scan import ROW_AXIS, Scan, window_rows, with_row_axis


def _scan():
    """Five rows at t = 0..4 s with Bx = 10 t and yaw = -t."""
    return Scan('t', {'t': (0.0, 1.0, 2.0, 3.0, 4.0), 'Bx': (0.0, 10.0, 20.0, 30.0, 40.0),
                      'yaw': (0.0, -1.0, -2.0, -3.0, -4.0)})

class ScanTest(unittest.TestCase):
    """Scan construction, properties and cropping."""

    def test_properties_report_rows_axis_and_channels(self):
        scan = _scan()
        self.assertEqual(scan.rows, 5)
        self.assertEqual(scan.axis_values, (0.0, 1.0, 2.0, 3.0, 4.0))
        self.assertEqual(scan.channels, ['Bx', 'yaw'])

    def test_missing_axis_and_ragged_columns_raise(self):
        with self.assertRaisesRegex(ValueError, "axis column 'time'"):
            Scan('time', {'t': (0.0,)})
        with self.assertRaisesRegex(ValueError, 'same length'):
            Scan('t', {'t': (0.0, 1.0), 'Bx': (1.0,)})

    def test_axis_range_ignores_nan(self):
        self.assertEqual(Scan('t', {'t': (math.nan, 2.0, -1.0, math.nan)}).axis_range(), (-1.0, 2.0))
        with self.assertRaisesRegex(ValueError, 'no finite'):
            Scan('t', {'t': (math.nan,)}).axis_range()

    def test_crop_keeps_closed_window_in_either_order(self):
        # [1, 3] includes both edges: t = 1, 2, 3.
        cropped = _scan().crop(1.0, 3.0, ['Bx'])
        self.assertEqual(cropped.columns, {'t': (1.0, 2.0, 3.0), 'Bx': (10.0, 20.0, 30.0)})
        self.assertEqual(_scan().crop(3.0, 1.0, ['Bx']), cropped)

    def test_crop_keeps_axis_first_once(self):
        self.assertEqual(list(_scan().crop(0.0, 4.0, ['yaw', 't', 'Bx']).columns), ['t', 'yaw', 'Bx'])

    def test_crop_errors(self):
        with self.assertRaisesRegex(ValueError, 'unknown channels: Bz'):
            _scan().crop(0.0, 4.0, ['Bz'])
        with self.assertRaisesRegex(ValueError, 'at least one channel'):
            _scan().crop(0.0, 4.0, [])
        with self.assertRaisesRegex(ValueError, 'no samples'):
            _scan().crop(1.2, 1.8, ['Bx'])

    def test_window_rows_skips_nan(self):
        self.assertEqual(window_rows([0.0, math.nan, 2.0, 5.0], 0.0, 2.0), [0, 2])

    def test_with_row_axis(self):
        scan = with_row_axis({'Bx': (7.0, 8.0, 9.0)})
        self.assertEqual((scan.axis, scan.axis_values, scan.channels), (ROW_AXIS, (0.0, 1.0, 2.0), ['Bx']))
        with self.assertRaisesRegex(ValueError, 'no numeric'):
            with_row_axis({})
        with self.assertRaisesRegex(ValueError, 'already exists'):
            with_row_axis({ROW_AXIS: (1.0,)})

if __name__ == '__main__':
    unittest.main()
