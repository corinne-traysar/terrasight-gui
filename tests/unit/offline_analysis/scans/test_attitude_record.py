"""Tests of scans/attitude_record.py: yaw/pitch/roll records in degrees for the browser plots."""
import math
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402
from scans import ScanData  # noqa: E402

from analysis_helpers import mag_scan, vn100_scan  # noqa: E402
from imu_helpers import raw_magnetic_text  # noqa: E402
from offline_analysis.scans.attitude_record import AttitudeRecord, finite_list  # noqa: E402
from offline_analysis.scans.scan_loader import LOADER  # noqa: E402

RADIANS = ScanData({'t': [0.0, 1.0], 'yaw_rad': [math.pi / 2, 0.0], 'pitch_rad': [math.nan, 0.0],
                    'roll_rad': [0.0, -math.pi]}, 't')


class FactorsTest(unittest.TestCase):
    """AttitudeRecord.factors: columns and their factors to degrees."""

    def test_degree_columns_have_factor_one(self):
        record = AttitudeRecord.factors(LOADER.data('vn100.csv', vn100_scan()))
        assert record is not None
        self.assertEqual(record['columns'], ['yaw_deg', 'pitch_deg', 'roll_deg'])
        self.assertEqual((record['to_degrees'], record['derived']), ([1.0, 1.0, 1.0], None))

    def test_radian_columns_get_180_over_pi(self):
        record = AttitudeRecord.factors(RADIANS) or {}
        for factor in record.get('to_degrees', []):
            self.assertAlmostEqual(factor, 180 / math.pi, delta=1e-12)

    def test_derived_angles_say_how_they_were_made(self):
        record = AttitudeRecord.factors(LOADER.data('raw.csv', raw_magnetic_text())) or {}
        self.assertEqual(record['derived']['source'], 'gyroscope')

    def test_no_angles_gives_none(self):
        self.assertIsNone(AttitudeRecord.factors(LOADER.data('scan.csv', mag_scan())))  # yaw only


class OfScanTest(unittest.TestCase):
    """AttitudeRecord.of_scan: every row in degrees, missing values as None."""

    def test_radians_become_degrees(self):
        record = AttitudeRecord.of_scan(RADIANS) or {}
        self.assertEqual(record['degrees'], [[90.0, None, 0.0], [0.0, 0.0, -180.0]])
        self.assertEqual((record['axis'], record['axis_values']), ('t', [0.0, 1.0]))

    def test_rows_mask_keeps_only_those_rows(self):
        record = AttitudeRecord.of_scan(RADIANS, np.array([False, True])) or {}
        self.assertEqual((record['axis_values'], record['degrees']), ([1.0], [[0.0, 0.0, -180.0]]))

    def test_no_angles_gives_none_and_finite_list_drops_nan(self):
        self.assertIsNone(AttitudeRecord.of_scan(ScanData({'t': [0.0], 'Bx': [1.0]}, 't')))
        self.assertEqual(finite_list([1.0, math.nan, math.inf]), [1.0, None, None])


if __name__ == '__main__':
    unittest.main()
