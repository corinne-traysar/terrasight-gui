"""Tests of scans/scan_loader.py: file text to onyx scans, with angles derived from a raw IMU."""
import unittest

from calibration_model import MISSING

if MISSING:
    raise unittest.SkipTest(MISSING)

from scans import ElectromagneticScan, MagneticScan, ScanData  # noqa: E402

from analysis_helpers import em_json, mag_scan, vn100_scan  # noqa: E402
from imu_helpers import raw_magnetic_text  # noqa: E402
from offline_analysis.imu.imu_attitude import ANGLE_COLUMNS  # noqa: E402
from offline_analysis.scans.scan_loader import LOADER, ScanLoader  # noqa: E402


class DataTest(unittest.TestCase):
    """ScanLoader.data reads any file as generic onyx ScanData."""

    def test_csv_columns_and_time_axis(self):
        data = LOADER.data('scan.csv', mag_scan())
        self.assertIsInstance(data, ScanData)
        self.assertEqual((data.axis, data.rows), ('time [s]', 11))
        self.assertEqual(float(data.column('Bx [nT]')[2]), 200.0)

    def test_vn100_keeps_its_own_angles(self):
        data = LOADER.data('vn100.csv', vn100_scan())
        self.assertEqual(data.attitude_columns, ('yaw_deg', 'pitch_deg', 'roll_deg'))
        self.assertFalse(set(ANGLE_COLUMNS) & set(data.channels))

    def test_raw_imu_file_gets_derived_angles(self):
        data = LOADER.data('raw.csv', raw_magnetic_text())
        self.assertEqual(data.attitude_columns, ANGLE_COLUMNS)
        attitude = data.attitude_rad
        assert attitude is not None
        self.assertAlmostEqual(float(attitude[-1, 0]), 1.0, delta=1e-9)  # 0.1 rad/s for 10 s

    def test_bad_text_raises(self):
        with self.assertRaisesRegex(ValueError, 'header line'):
            ScanLoader().data('scan.csv', 'only_a_header\n')


class SensorScanTest(unittest.TestCase):
    """ScanLoader.sensor_scan builds the onyx class the view asks for."""

    def test_magnetic_and_electromagnetic_classes(self):
        self.assertIsInstance(LOADER.sensor_scan('magnetic', 'scan.csv', mag_scan()), MagneticScan)
        self.assertIsInstance(LOADER.sensor_scan('electromagnetic', 'em.json', em_json(3)), ElectromagneticScan)

    def test_unknown_sensor_or_missing_columns_raise(self):
        with self.assertRaisesRegex(ValueError, 'unknown sensor'):
            LOADER.sensor_scan('gravity', 'scan.csv', mag_scan())
        with self.assertRaisesRegex(ValueError, 'no electromagnetic phasor'):
            LOADER.sensor_scan('electromagnetic', 'scan.csv', mag_scan())

    def test_as_sensor_accepts_data(self):
        data = LOADER.data('scan.csv', mag_scan())
        self.assertEqual(ScanLoader.as_sensor('magnetic', data).sensor_columns, ('Bx [nT]', 'By [nT]', 'Bz [nT]'))


if __name__ == '__main__':
    unittest.main()
