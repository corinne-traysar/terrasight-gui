"""A scan's yaw/pitch/roll in degrees, as the browser's attitude plots and angle window draw them.

The angles are onyx's: ``ScanData.attitude_columns`` finds the columns and
``attitude_rad`` converts them (unit from the name, else values beyond 2π
are degrees). Angles derived from a raw IMU (``offline_analysis.imu``) carry
how they were made under ``derived``. Values are rounded to 4 decimals and a
missing value is None (JSON has no NaN).
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray
from scans import ScanData
from scans.columns.attitude_columns import angle_scale

from offline_analysis.imu.imu_attitude import METADATA_KEY

_DIGITS = 4


class AttitudeRecord:
    """Builders of the JSON attitude records the views read."""

    @staticmethod
    def factors(data: ScanData) -> Optional[dict[str, Any]]:
        """The yaw/pitch/roll columns, each column's factor to degrees and how they were made, or None."""
        names = data.attitude_columns
        if names is None:
            return None
        return dict(columns=list(names),
                    to_degrees=[angle_scale(n, data.column(n)) * 180 / math.pi for n in names],
                    derived=data.metadata.get(METADATA_KEY))

    @staticmethod
    def of_scan(data: ScanData, rows: Optional[NDArray[np.bool_]] = None) -> Optional[dict[str, Any]]:
        """Columns, axis, axis values and yaw/pitch/roll degrees of every row (or of ``rows``), or None."""
        names, attitude = data.attitude_columns, data.attitude_rad
        if names is None or attitude is None:
            return None
        axis_values = data.axis_values
        if rows is not None:
            axis_values, attitude = axis_values[rows], attitude[rows]
        return dict(columns=list(names), axis=data.axis, axis_values=finite_list(axis_values),
                    degrees=[finite_list(np.round(np.degrees(row), _DIGITS)) for row in attitude])


def finite_list(values: Any) -> list[Optional[float]]:
    """``values`` as floats for JSON; NaN and infinities become None."""
    return [float(v) if math.isfinite(v) else None for v in values]
