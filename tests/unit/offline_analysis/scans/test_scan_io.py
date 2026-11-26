"""Tests of scans/scan_io.py: parsing text and JSON scans (including VN-100 recordings) and writing CSV.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path

from offline_analysis.scans.channels import (PROFILES)
from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_io import load_scan, parse_scan, save_scan, scan_csv
from analysis_helpers import em_json, text_scan, vn100_scan


class ParseTextTest(unittest.TestCase):
    """Delimited text scans."""

    def test_csv_with_units_uses_time_axis(self):
        scan = parse_scan('scan.csv', text_scan(['time [s]', 'Bx [nT]'], [['0', '1.5'], ['0.1', '-2']]))
        self.assertEqual((scan.axis, scan.columns['Bx [nT]']), ('time [s]', (1.5, -2.0)))

    def test_tab_and_semicolon_delimiters(self):
        for delimiter in ('\t', ';'):
            with self.subTest(delimiter=repr(delimiter)):
                scan = parse_scan('scan.tsv', text_scan(['t', 'Bx'], [['0', '1'], ['1', '2']], delimiter))
                self.assertEqual(scan.columns['Bx'], (1.0, 2.0))

    def test_hash_header_whitespace_and_byte_order_mark(self):
        scan = parse_scan('path.txt', '﻿# s x y z\n0.0 1 2 3\n1.0  4 5 6\n')
        self.assertEqual((scan.axis, scan.columns['z']), ('s', (3.0, 6.0)))

    def test_missing_cell_is_nan_and_text_column_dropped(self):
        scan = parse_scan('scan.csv', text_scan(['t', 'Bx', 'note'], [['0', '', 'start'], ['1', '2', 'end']]))
        self.assertTrue(math.isnan(scan.columns['Bx'][0]))
        self.assertNotIn('note', scan.columns)

    def test_iso_times_become_seconds_from_first(self):
        rows = [['2026-11-23T10:00:00Z', '1'], ['2026-11-23T10:00:00.5Z', '2'], ['2026-11-23T10:01:00Z', '3']]
        self.assertEqual(parse_scan('scan.csv', text_scan(['timestamp', 'Bx'], rows)).axis_values,
                         (0.0, 0.5, 60.0))

    def test_vn100_recording_uses_receipt_seconds(self):
        scan = parse_scan('vn100.csv', vn100_scan(4))
        self.assertEqual(scan.axis, 'received_utc')
        self.assertEqual(scan.axis_values, (0.0, 0.5, 1.0, 1.5))
        self.assertEqual(scan.columns['magnetic_z_gauss'], (0.4,) * 4)

    def test_no_axis_column_adds_row_axis(self):
        scan = parse_scan('scan.csv', text_scan(['Bx', 'By'], [['1', '2'], ['3', '4']]))
        self.assertEqual((scan.axis, scan.axis_values), ('row', (0.0, 1.0)))

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, 'at least one data row'):
            parse_scan('scan.csv', text_scan(['t', 'Bx'], []))
        with self.assertRaisesRegex(ValueError, 'no numeric columns'):
            parse_scan('scan.csv', text_scan(['name'], [['a'], ['b']]))


class ParseJsonTest(unittest.TestCase):
    """JSON scans: record lists, nested values and wrapping objects."""

    def test_nested_values_are_flattened(self):
        scan = parse_scan('scan.json', json.dumps([{'t': 0, 'field_T': {'real': [1, 2]}, 'ok': True}]))
        self.assertEqual(list(scan.columns), ['t', 'field_T_real_0', 'field_T_real_1'])

    def test_samples_key_is_preferred(self):
        scan = parse_scan('scan.JSON', json.dumps({'cables': [{'id': 1}], 'samples': [{'distance_m': 5, 'Bx': 1}]}))
        self.assertEqual((scan.axis, scan.columns['Bx']), ('distance_m', (1.0,)))

    def test_bunker_cable_output_is_an_electromagnetic_scan(self):
        scan = parse_scan('em.json', em_json())
        self.assertEqual(scan.axis, 'distance_m')
        self.assertEqual(PROFILES['electromagnetic'].select(scan.channels).b_axes[:2],
                         ('field_T_real_0', 'field_T_real_1'))

    def test_without_records_raises(self):
        with self.assertRaisesRegex(ValueError, 'list of records'):
            parse_scan('scan.json', json.dumps({'status': 'completed'}))


class WriteTest(unittest.TestCase):
    """scan_csv and save_scan."""

    scan = Scan('t', {'t': (0.0, 1.0), 'Bx': (math.nan, 2.5)})

    def test_csv_text_round_trips_values_and_nan(self):
        text = scan_csv(self.scan)
        self.assertEqual(text.splitlines(), ['t,Bx', '0.0,', '1.0,2.5'])
        self.assertEqual(parse_scan('out.csv', text).columns['Bx'][1], 2.5)

    def test_save_keeps_existing_file_unless_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'out.csv'
            path.write_text('keep')
            with self.assertRaises(FileExistsError):
                save_scan(self.scan, path)
            self.assertEqual(path.read_text(), 'keep')
            save_scan(self.scan, path, overwrite=True)
            self.assertEqual(load_scan(path).columns['Bx'][1], 2.5)

if __name__ == '__main__':
    unittest.main()
