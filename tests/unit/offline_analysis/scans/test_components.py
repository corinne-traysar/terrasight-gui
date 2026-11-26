"""Tests of scans/components.py: B-vector column triples and their units in nT.

Ported from Simulation-Examples (sensor_viewer components tests), plus gauss columns.
"""
import unittest

from offline_analysis.scans.components import axis_split, magnetic_triple, phasor_triples, triples, unit_scale_nt
from analysis_helpers import VN100_HEADER

FIELD = ['field_T_0', 'field_T_1', 'field_T_2']
COMBINED = ['combined_field_T_0', 'combined_field_T_1', 'combined_field_T_2']


class AxisSplitTest(unittest.TestCase):
    """axis_split finds the last axis token."""

    def test_separated_and_attached_tokens(self):
        cases = {'Bx [nT]': ('b*', 0), 'b_y_nt': ('b_*_nt', 1), 'field_T_real_2': ('field_t_real_*', 2),
                 'B_east': ('b_*', 0), 'bz_re': ('b*_re', 2), 'acc_up': ('acc_*', 2),
                 'magnetic_y_gauss': ('magnetic_*_gauss', 1)}
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(axis_split(name), expected)

    def test_last_token_wins(self):
        # 'cable-1' holds an axis-like '1', but the trailing '0' is the axis.
        self.assertEqual(axis_split('cable_fields_T_cable-1_real_0'), ('cable_fields_t_cable-1_real_*', 0))

    def test_no_axis_token(self):
        self.assertIsNone(axis_split('temperature'))


class TriplesTest(unittest.TestCase):
    """Grouping into complete triples and choosing the sensor's B vector."""

    def test_only_complete_triples(self):
        self.assertEqual(triples(['Bx', 'By', 'Bz', 'acc_x', 'acc_y', 't']), {'b*': ('Bx', 'By', 'Bz')})

    def test_magnetic_prefers_combined_field(self):
        names = ['earth_field_T_0', 'earth_field_T_1', 'earth_field_T_2'] + FIELD + COMBINED
        self.assertEqual(magnetic_triple(names), tuple(COMBINED))

    def test_magnetic_accepts_scan_and_vn100_names(self):
        self.assertEqual(magnetic_triple(['t', 'Bx [nT]', 'By [nT]', 'Bz [nT]']),
                         ('Bx [nT]', 'By [nT]', 'Bz [nT]'))
        self.assertEqual(magnetic_triple(VN100_HEADER),
                         ('magnetic_x_gauss', 'magnetic_y_gauss', 'magnetic_z_gauss'))

    def test_calibrated_output_names(self):
        names = ['received_utc', 'B_east_nT', 'B_north_nT', 'B_up_nT', 'B_total_nT']
        self.assertEqual(magnetic_triple(names), ('B_east_nT', 'B_north_nT', 'B_up_nT'))

    def test_magnetic_missing_raises(self):
        with self.assertRaisesRegex(ValueError, 'no magnetic B-field'):
            magnetic_triple(['position_m_0', 'position_m_1', 'position_m_2'])

    def test_phasor_pairs_real_and_imaginary(self):
        real = ['field_T_real_0', 'field_T_real_1', 'field_T_real_2']
        imag = ['field_T_imag_0', 'field_T_imag_1', 'field_T_imag_2']
        self.assertEqual(phasor_triples(imag + real), (tuple(real), tuple(imag)))
        self.assertEqual(phasor_triples(['Bx_re', 'By_re', 'Bz_re', 'Bx_im', 'By_im', 'Bz_im']),
                         (('Bx_re', 'By_re', 'Bz_re'), ('Bx_im', 'By_im', 'Bz_im')))

    def test_phasor_without_imaginary_raises(self):
        with self.assertRaisesRegex(ValueError, 'no electromagnetic phasor'):
            phasor_triples(['Bx_re', 'By_re', 'Bz_re'])


class UnitTest(unittest.TestCase):
    """unit_scale_nt converts named units to nT."""

    def test_units(self):
        cases = {'Bx [nT]': 1.0, 'b_x_nt': 1.0, 'field_T_0': 1e9, 'B_uT_x': 1e3, 'Bx (µT)': 1e3, 'Bx': 1.0,
                 'magnetic_x_gauss': 1e5}
        for name, scale in cases.items():
            with self.subTest(name=name):
                self.assertEqual(unit_scale_nt(name), scale)

if __name__ == '__main__':
    unittest.main()
