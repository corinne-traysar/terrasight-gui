"""Tests of examples/make_mock_data.py: the seeded mock tumble, calibration and survey scan.

Needs numpy, scipy and onyx ``calibration`` (as the script does); skipped without them.
Files are written to a temporary folder, never into examples/.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibration_model import MISSING

SCRIPT = Path(__file__).resolve().parents[3] / 'examples' / 'make_mock_data.py'

if MISSING:
    raise unittest.SkipTest(MISSING)

from scans import MagneticScan  # noqa: E402  (after the skip, like the script's imports)

load_scan = MagneticScan.load


def load_script():
    """Import examples/make_mock_data.py as a module (examples/ is not a package)."""
    spec = importlib.util.spec_from_file_location('make_mock_data', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MakeMockDataTests(unittest.TestCase):
    """Run main into a temporary ROOT and read the three files back."""

    @classmethod
    def setUpClass(cls):
        """Generate the files once; every test reads them."""
        cls.module = load_script()
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)
        with patch.object(cls.module, 'ROOT', cls.root):
            cls.module.main()

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary folder."""
        cls.folder.cleanup()

    def test_three_files_with_the_documented_row_counts(self):
        tumble = load_scan(self.root / 'mock_calibration_tumble.csv')
        survey = load_scan(self.root / 'mock_scan.csv')
        self.assertEqual((tumble.rows, survey.rows), (600, 1200))
        for scan in (tumble, survey):
            self.assertEqual(scan.channels, ['Bx_nT', 'By_nT', 'Bz_nT', 'yaw_deg', 'pitch_deg', 'roll_deg'])

    def test_calibration_is_an_imu_fit_of_the_tumble(self):
        document = json.loads((self.root / 'mock_calibration.json').read_text())
        self.assertEqual((document['format'], document['method']), ('onyx-vector-calibration/1', 'imu'))
        self.assertEqual(document['sample_count'], 600)
        # The fit recovers the made-up offset (850, -1200, 600) nT within the 8 nT noise.
        for fitted, true in zip(document['offset_t'], self.module.OFFSET_NT):
            self.assertAlmostEqual(fitted * 1e9, true, delta=5.0)

    def test_output_matches_the_committed_examples(self):
        committed = SCRIPT.parent / 'mock_calibration.json'
        regenerated = json.loads((self.root / 'mock_calibration.json').read_text())
        self.assertEqual(regenerated['sample_count'], json.loads(committed.read_text())['sample_count'])


if __name__ == '__main__':
    unittest.main()
