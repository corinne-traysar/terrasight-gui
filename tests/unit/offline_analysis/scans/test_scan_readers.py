"""Tests of scans/scan_readers.py: choosing a reader and splitting text or JSON into columns."""
import json
import unittest

from offline_analysis.scans.scan_readers import JsonScanReader, ScanReader, TextScanReader


class ForNameTests(unittest.TestCase):
    """The file extension picks the reader."""

    def test_json_extension_in_any_case_picks_json(self):
        self.assertIsInstance(ScanReader.for_name('scan.JSON'), JsonScanReader)
        self.assertIsInstance(ScanReader.for_name('scan.csv'), TextScanReader)
        self.assertIsInstance(ScanReader.for_name('scan'), TextScanReader)


class TextTableTests(unittest.TestCase):
    """Header line, delimiter detection and short rows."""

    def test_delimiters_and_whitespace(self):
        for text in ('t,Bx\n0,1\n', 't\tBx\n0\t1\n', 't;Bx\n0;1\n', '# t  Bx\n0   1\n'):
            with self.subTest(text=text):
                self.assertEqual(TextScanReader().table(text), {'t': ['0'], 'Bx': ['1']})

    def test_short_rows_are_padded_and_blank_lines_skipped(self):
        self.assertEqual(TextScanReader().table('t,Bx,By\n\n0,1\n'), {'t': ['0'], 'Bx': ['1'], 'By': ['']})

    def test_header_only_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'header line and at least one data row'):
            TextScanReader().table('t,Bx\n')


class JsonTableTests(unittest.TestCase):
    """Records, the samples key and flattening."""

    def test_nested_values_are_flattened_and_booleans_dropped(self):
        record = {'t': 0, 'field': {'real': [1, 2]}, 'ok': True}
        self.assertEqual(JsonScanReader().flatten(record), {'t': 0, 'field_real_0': 1, 'field_real_1': 2})

    def test_samples_key_is_preferred(self):
        document = {'meta': [{'x': 9}], 'samples': [{'t': 0, 'Bx': 1}, {'t': 1, 'Bx': 2}]}
        self.assertEqual(JsonScanReader().table(json.dumps(document)), {'t': ['0', '1'], 'Bx': ['1', '2']})

    def test_documents_without_records_are_refused(self):
        for document in ([], {'a': 1}, [1, 2]):
            with self.subTest(document=document), self.assertRaisesRegex(ValueError, 'list of records'):
                JsonScanReader.records(document)


class ReadTests(unittest.TestCase):
    """The template method: byte-order mark, numeric columns and the sample axis."""

    def test_bom_is_ignored_and_time_becomes_the_axis(self):
        scan = TextScanReader().read('﻿time,Bx\n0,5\n1,6\n')
        self.assertEqual((scan.axis, scan.channels, scan.columns['Bx']), ('time', ['Bx'], (5.0, 6.0)))

    def test_without_an_axis_column_the_row_number_is_used(self):
        scan = TextScanReader().read('Bx,By\n5,1\n6,2\n')
        self.assertEqual(scan.channels, ['Bx', 'By'])
        self.assertEqual(scan.axis_values, (0.0, 1.0))


if __name__ == '__main__':
    unittest.main()
