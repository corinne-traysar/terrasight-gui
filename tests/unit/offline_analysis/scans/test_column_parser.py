"""Tests of scans/column_parser.py: string columns to floats or ISO-8601 seconds."""
import math
import unittest

from offline_analysis.scans.column_parser import ColumnParser


class ConvertTests(unittest.TestCase):
    """One column at a time: numbers first, then ISO times, else dropped."""

    def setUp(self):
        """A default parser."""
        self.parser = ColumnParser()

    def converted(self, cells):
        """``convert(cells)``, failing the test when the column was dropped."""
        values = self.parser.convert(cells)
        if values is None:
            self.fail(f'{cells} was dropped')
        return values

    def test_numbers_with_empty_cells_become_nan(self):
        values = self.converted(['1', '', '-2.5e3', 'null', 'None'])
        self.assertEqual(values[0::2][:2], (1.0, -2500.0))
        self.assertTrue(all(math.isnan(v) for v in (values[1], values[3], values[4])))

    def test_iso_times_become_seconds_from_the_first(self):
        # 12:00:00 -> 0 s, 12:00:01.5 -> 1.5 s, 12:01:00 -> 60 s; Z means UTC.
        values = self.converted(['2026-01-01T12:00:00Z', '2026-01-01T12:00:01.5Z', '', '2026-01-01T12:01:00Z'])
        self.assertEqual((values[0], values[1], values[3]), (0.0, 1.5, 60.0))
        self.assertTrue(math.isnan(values[2]))

    def test_text_mixed_zones_and_all_empty_are_dropped(self):
        self.assertIsNone(self.parser.convert(['north', 'south']))
        self.assertIsNone(self.parser.convert(['', 'null']))
        self.assertIsNone(self.parser.convert(['2026-01-01T12:00:00Z', '2026-01-01T12:00:01']), 'aware and naive')


class NumericColumnsTests(unittest.TestCase):
    """A whole table keeps only its numeric columns, in order."""

    def test_non_numeric_columns_are_skipped(self):
        table = {'t': ['0', '1'], 'label': ['a', 'b'], 'Bx': ['5', '6']}
        self.assertEqual(ColumnParser().numeric_columns(table), {'t': (0.0, 1.0), 'Bx': (5.0, 6.0)})

    def test_no_numeric_column_raises(self):
        with self.assertRaisesRegex(ValueError, 'no numeric columns'):
            ColumnParser().numeric_columns({'label': ['a', 'b']})


if __name__ == '__main__':
    unittest.main()
