"""A magnetic scan as calibration input: B in tesla plus optional IMU attitude.

Needs numpy and the onyx ``calibration`` package. The B vector is found like
the Offline Data view does (``combined_field_T`` preferred, else
``Bx/By/Bz``-style or ``magnetic_x_gauss``-style columns) and converted from the
unit in its column names to tesla. Yaw/pitch/roll, when the scan has all three,
become radians. Rows with any missing value in these columns are dropped; the
sample axis of the kept rows is kept so calibrated output lines up with the scan.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from calibration import VectorSamples
from calibration.arrays import FloatArray

from offline_analysis.scans.attitude_columns import AttitudeColumns, angle_scale, attitude_columns
from offline_analysis.scans.components import Triple, magnetic_triple, unit_scale_nt
from offline_analysis.scans.scan import Scan

NT_TO_T = 1e-9


@dataclass(frozen=True, eq=False)
class MagneticRecording:
    """Row-aligned B readings (tesla) and optional attitude (radians) from one scan.

    Attributes:
        axis: name of the scan's sample-axis column.
        axis_values: (N,) sample-axis values of the kept rows, source unit.
        field_t: (N, 3) raw B along the sensor axes, tesla.
        attitude_rad: (N, 3) yaw, pitch, roll in radians, or None.
        field_columns: the scan columns B was read from.
        attitude_columns: the yaw, pitch, roll columns, or None.
    """

    axis: str
    axis_values: FloatArray
    field_t: FloatArray
    attitude_rad: FloatArray | None
    field_columns: Triple
    attitude_columns: AttitudeColumns | None

    @property
    def count(self) -> int:
        """Number of kept rows."""
        return int(self.field_t.shape[0])

    @property
    def has_attitude(self) -> bool:
        """True when the scan has yaw, pitch and roll columns."""
        return self.attitude_rad is not None

    def samples(self) -> VectorSamples:
        """The readings as onyx ``VectorSamples`` (with attitude when present)."""
        return VectorSamples(self.field_t, self.attitude_rad)


def read_recording(scan: Scan) -> MagneticRecording:
    """Extract B (tesla) and, when present, yaw/pitch/roll (radians) from ``scan``.

    Raises:
        ValueError: if the scan has no B triple or no row with every value present.
    """
    field_columns = magnetic_triple(scan.channels)
    angles = attitude_columns(scan.channels)
    field = _stack(scan, field_columns, [unit_scale_nt(n) * NT_TO_T for n in field_columns])
    attitude = None if angles is None else _stack(
        scan, angles, [angle_scale(n, scan.columns[n]) for n in angles])
    keep = np.isfinite(field).all(axis=1)
    if attitude is not None:
        keep &= np.isfinite(attitude).all(axis=1)
    if not keep.any():
        raise ValueError('the scan has no row with every B (and attitude) value present')
    axis_values = np.asarray(scan.axis_values, dtype=np.float64)[keep]
    return MagneticRecording(scan.axis, axis_values, field[keep],
                             None if attitude is None else attitude[keep], field_columns, angles)


def _stack(scan: Scan, names: tuple[str, str, str], scales: list[float]) -> FloatArray:
    """The three columns ``names`` multiplied by ``scales``, as an (N, 3) array."""
    return np.column_stack([np.asarray(scan.columns[n], dtype=np.float64) * s
                            for n, s in zip(names, scales)])
