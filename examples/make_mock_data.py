"""Generate the mock magnetic scan and calibration file in this folder.

Run with the onyx ``calibration`` package and numpy/scipy importable, e.g.
``PYTHONPATH=../onyx-demo-sims python examples/make_mock_data.py``. Writes:

``mock_calibration_tumble.csv``  a sensor rotated through many attitudes (the fit input)
``mock_calibration.json``        the onyx IMU calibration fitted to that tumble
``mock_scan.csv``                a raw survey line with the same sensor distortion

Both files share one made-up sensor error (offset, scale, soft iron), so applying
the calibration to the scan removes it. Seeded: reruns give identical files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from calibration import save_parameters  # noqa: E402
from calibration.attitude import body_to_enu  # noqa: E402
from offline_analysis.magnetic_calibration.calibrated_output import calibration_json  # noqa: E402
from offline_analysis.magnetic_calibration.magnetic_calibrator import fit_recording  # noqa: E402
from offline_analysis.magnetic_calibration.magnetic_recording import read_recording  # noqa: E402
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT  # noqa: E402
from offline_analysis.scans.scan import Scan  # noqa: E402
from offline_analysis.scans.scan_io import save_scan  # noqa: E402

EARTH_ENU_NT = np.array(BAR_GYORA_ENU_NT)
OFFSET_NT = np.array([850.0, -1200.0, 600.0])
DISTORTION = np.array([[1.04, 0.03, -0.02], [0.03, 0.96, 0.04], [-0.02, 0.04, 1.02]])
NOISE_NT = 8.0


def raw_reading(field_enu_nt: np.ndarray, attitude_rad: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """What the distorted sensor reports (nT, body axes) for ENU fields and attitudes."""
    body = (np.swapaxes(body_to_enu(attitude_rad), 1, 2) @ field_enu_nt[:, :, None])[:, :, 0]
    return body @ DISTORTION.T + OFFSET_NT + rng.normal(0, NOISE_NT, body.shape)


def scan_of(time_s: np.ndarray, field_nt: np.ndarray, attitude_rad: np.ndarray) -> Scan:
    """A scan with time, Bx/By/Bz in nT and yaw/pitch/roll in degrees."""
    columns = {'time_s': tuple(time_s.tolist())}
    for k, axis in enumerate('xyz'):
        columns[f'B{axis}_nT'] = tuple(field_nt[:, k].tolist())
    for k, name in enumerate(('yaw', 'pitch', 'roll')):
        columns[f'{name}_deg'] = tuple(np.degrees(attitude_rad[:, k]).tolist())
    return Scan('time_s', columns)


def main() -> None:
    """Write the tumble, the fitted calibration and the survey scan."""
    rng = np.random.default_rng(7)
    n = 600
    tumble = np.column_stack([rng.uniform(-np.pi, np.pi, n), rng.uniform(-1.2, 1.2, n), rng.uniform(-np.pi, np.pi, n)])
    tumble_scan = scan_of(np.arange(n) * 0.1, raw_reading(np.tile(EARTH_ENU_NT, (n, 1)), tumble, rng), tumble)
    save_scan(tumble_scan, ROOT / 'mock_calibration_tumble.csv', overwrite=True)
    recording = read_recording(tumble_scan)
    (ROOT / 'mock_calibration.json').write_text(calibration_json(fit_recording(recording), recording))

    m = 1200
    time_s = np.arange(m) * 0.1
    along = np.linspace(-1, 1, m)
    anomaly = np.column_stack([400 * np.exp(-(along / 0.15) ** 2), -900 * np.exp(-(along / 0.1) ** 2),
                               1500 * np.exp(-((along - 0.1) / 0.12) ** 2)])
    walk = np.column_stack([np.radians(40) + 0.15 * np.sin(time_s / 7), 0.08 * np.sin(time_s / 3),
                            0.1 * np.sin(time_s / 5)])
    survey = scan_of(time_s, raw_reading(EARTH_ENU_NT + anomaly, walk, rng), walk)
    save_scan(survey, ROOT / 'mock_scan.csv', overwrite=True)


if __name__ == '__main__':
    main()
