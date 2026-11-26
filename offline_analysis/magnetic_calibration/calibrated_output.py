"""A magnetic scan calibrated by onyx, as the dashboard's east/north/up nT output and summaries.

onyx ``Scan.calibrate`` corrects every complete row as ``C (B_raw - b)`` and
rotates it to east/north/up with the scan's yaw/pitch/roll (its own or
derived from a raw IMU), or as a level, north-facing sensor without them.
Rows with a missing value are dropped here. The calibrated scan holds the
sample axis plus ``B_east_nT``, ``B_north_nT``, ``B_up_nT`` and ``B_total_nT``;
``offline_calibration`` gives the Offline Data view the same rows as vectors.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
from calibration import VectorCalibration
from scans import MagneticScan, ScanData

from offline_analysis.magnetic_calibration.calibration_angles import calibration_angles
from offline_analysis.magnetic_calibration.calibration_document import CalibrationDocument
from offline_analysis.scans.scan_window import csv_text

NANOTESLA = 1e-9
ENU_COLUMNS = ('B_east_nT', 'B_north_nT', 'B_up_nT')
TOTAL_COLUMN = 'B_total_nT'


class CalibratedOutput:
    """The rows of ``scan`` that onyx could calibrate, in nT east/north/up."""

    def __init__(self, scan: MagneticScan, calibration: VectorCalibration):
        """Calibrate ``scan``; ValueError when no row has every field (and angle) value."""
        calibrated = scan.calibrate(calibration)
        field = calibrated.field_t
        self.kept = np.isfinite(field).all(axis=1)
        self.source = scan
        self.attitude_used = bool(calibrated.metadata['calibration']['attitude_used'])
        self.enu_nt = field[self.kept] / NANOTESLA
        self.total_nt = np.linalg.norm(self.enu_nt, axis=1)

    @property
    def rows(self) -> int:
        """Number of calibrated rows."""
        return int(self.enu_nt.shape[0])

    def data(self) -> ScanData:
        """The sample axis of the kept rows plus the ENU and total columns."""
        columns = {self.source.axis: self.source.axis_values[self.kept]}
        columns.update({name: self.enu_nt[:, k] for k, name in enumerate(ENU_COLUMNS)})
        columns[TOTAL_COLUMN] = self.total_nt
        return ScanData(columns, self.source.axis)

    def csv(self) -> str:
        """The calibrated scan as CSV text."""
        return csv_text(self.data())

    def summary(self) -> dict[str, Any]:
        """Rows, whether attitude was used, and the mean and spread of calibrated |B| (nT)."""
        return dict(rows=self.rows, attitude_used=self.attitude_used,
                    b_total_mean_nt=float(self.total_nt.mean()), b_total_std_nt=float(self.total_nt.std()))


def fit_summary(calibration: VectorCalibration, scan: MagneticScan) -> dict[str, Any]:
    """Method, rows, columns used, offset, residual and Earth field (nT) of a fit."""
    parameters = calibration.parameters
    earth = parameters.earth_field_enu_t
    return dict(method=parameters.method, rows=parameters.sample_count, b_columns=list(scan.sensor_columns),
                attitude_columns=list(scan.attitude_columns or []),
                reference_nt=parameters.reference_magnitude_t / NANOTESLA,
                offset_nt=_nt(parameters.offset_t), residual_rms_nt=parameters.residual_rms_t / NANOTESLA,
                earth_field_enu_nt=None if earth is None else _nt(earth))


def offline_calibration(text: str, scan: MagneticScan) -> dict[str, Any]:
    """Calibrate ``scan`` with the calibration JSON ``text`` for the Offline Data view.

    Returns the kept rows' calibrated east/north/up vectors (nT), the apply
    summary, the field columns read and the calibration's angles.

    Raises:
        ValueError: on a bad calibration or a scan without a complete row.
    """
    output = CalibratedOutput(scan, CalibrationDocument.parse(text))
    return dict(count=output.rows, labels=['E', 'N', 'U'], field_nt=output.enu_nt.tolist(),
                b_columns=list(scan.sensor_columns), summary=output.summary(),
                calibration=calibration_angles(_document(text)))


def _nt(vector_t: Any) -> list[float]:
    """A tesla vector as a list of nT values."""
    return [float(v) / NANOTESLA for v in vector_t]


def _document(text: str) -> dict[str, Any]:
    """The parsed calibration JSON object (already validated by ``CalibrationDocument.parse``)."""
    return json.loads(text)
