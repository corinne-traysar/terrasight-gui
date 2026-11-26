"""Tests of magnetic_calibration/calibration_document.py: calibration JSON text out and back in.

Needs numpy, scipy and onyx (Python 3.12+). Synthetic data: tests/calibration_model.py.
"""
import json
import unittest

from calibration_model import MISSING, model, recording

if MISSING:
    raise unittest.SkipTest(MISSING)

import numpy as np  # noqa: E402
from calibration import EllipsoidCalibration, ImuCalibration, VectorCalibration  # noqa: E402

from offline_analysis.magnetic_calibration.calibration_document import ATTITUDE_KEY, CalibrationDocument  # noqa: E402
from offline_analysis.magnetic_calibration.magnetic_calibrator import MagneticCalibrator  # noqa: E402


class TextTest(unittest.TestCase):
    """CalibrationDocument.text writes onyx's format plus the fitted rows' attitude."""

    def setUp(self):
        _, soft_iron, misalignment, _ = model()
        self.scan = recording(True, soft_iron @ misalignment, count=80)
        self.calibration = MagneticCalibrator().fit(self.scan)

    def test_attitude_is_embedded_in_degrees(self):
        stored = json.loads(CalibrationDocument.text(self.calibration, self.scan))[ATTITUDE_KEY]
        self.assertEqual((stored['columns'], stored['axis'], len(stored['degrees'])),
                         (['yaw_rad', 'pitch_rad', 'roll_rad'], 't', 80))
        attitude = self.scan.attitude_rad
        assert attitude is not None
        np.testing.assert_allclose(stored['degrees'][3], np.degrees(attitude[3]), atol=1e-3)

    def test_no_attitude_without_a_scan_or_its_angles(self):
        self.assertNotIn(ATTITUDE_KEY, json.loads(CalibrationDocument.text(self.calibration)))
        self.assertNotIn(ATTITUDE_KEY, json.loads(CalibrationDocument.text(self.calibration, recording(False))))

    def test_onyx_loads_the_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cal.json'
            path.write_text(CalibrationDocument.text(self.calibration, self.scan))
            loaded = VectorCalibration.load(path)
        self.assertIsInstance(loaded, ImuCalibration)
        self.assertEqual(loaded.parameters.sample_count, 80)


class ParseTest(unittest.TestCase):
    """CalibrationDocument.parse restores the onyx class named by the method."""

    def test_round_trip_keeps_method_and_correction(self):
        calibration = MagneticCalibrator().fit(recording(False))
        parsed = CalibrationDocument.parse(CalibrationDocument.text(calibration))
        self.assertIsInstance(parsed, EllipsoidCalibration)
        np.testing.assert_allclose(parsed.parameters.correction, calibration.parameters.correction, atol=1e-15)

    def test_bad_documents_raise(self):
        good = json.loads(CalibrationDocument.text(MagneticCalibrator().fit(recording(False))))
        cases = (('{"format": "x"}', 'not a onyx-vector-calibration/1'), ('[1]', 'not a onyx'),
                 (json.dumps({**good, 'method': 'magic'}), 'unknown calibration method'),
                 (json.dumps({k: v for k, v in good.items() if k != 'offset_t'}), 'incomplete'))
        for text, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                CalibrationDocument.parse(text)


if __name__ == '__main__':
    unittest.main()
