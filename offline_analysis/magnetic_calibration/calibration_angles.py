"""Angles of a magnetic calibration and the yaw/pitch/roll of scans, in degrees.

Pure Python, no numpy, so the Offline Data view can show a scan's attitude
on the Pi too. A calibration's correction ``C`` is split into a rotation and
a symmetric scale/soft-iron part (polar decomposition ``C = R S``); ``R``
takes sensor axes to the output frame (IMU body forward/right/down), and its
aerospace Z-Y-X yaw/pitch/roll is the sensor mounting the calibration holds:
declared for the ellipsoid method, fitted for the IMU method. The fitted
Earth field of an IMU calibration (tesla, east/north/up) gives declination
(east of north) and inclination (positive below horizontal).

A calibration document written here may carry ``calibration_attitude``: the
yaw/pitch/roll of every row it was fitted on. onyx ignores the extra key.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

from offline_analysis.scans.attitude_columns import angle_scale, attitude_columns
from offline_analysis.magnetic_calibration.rotation_math import euler_zyx_deg, polar_rotation
from offline_analysis.scans.scan import Scan

ATTITUDE_KEY = 'calibration_attitude'
_DIGITS = 4


def scan_attitude(scan: Scan) -> dict[str, Any] | None:
    """The scan's yaw/pitch/roll columns and every row in degrees (None when missing), or None."""
    names = attitude_columns(scan.channels)
    if names is None:
        return None
    factors = [angle_scale(n, scan.columns[n]) * 180 / math.pi for n in names]
    rows = [[_scaled(scan.columns[n][i], f) for n, f in zip(names, factors)] for i in range(scan.rows)]
    return dict(columns=list(names), axis=scan.axis, axis_values=[_number(v) for v in scan.axis_values],
                degrees=rows)


def recording_attitude(axis: str, axis_values: Sequence[float], attitude_rad: Sequence[Sequence[float]],
                       columns: Sequence[str]) -> dict[str, Any]:
    """The ``calibration_attitude`` record of a fit's rows: yaw/pitch/roll radians in, degrees out."""
    return dict(columns=list(columns), axis=axis, axis_values=[_number(float(v)) for v in axis_values],
                degrees=[[_scaled(float(a), 180 / math.pi) for a in row] for row in attitude_rad])


def calibration_angles(document: dict[str, Any]) -> dict[str, Any]:
    """Mounting yaw/pitch/roll, Earth-field angles and the stored calibration-scan attitude.

    ``document`` is a parsed ``onyx-vector-calibration/1`` JSON object.

    Raises:
        ValueError: when the correction is not a non-singular 3x3 matrix or the
            stored attitude is malformed.
    """
    rotation, reflected = polar_rotation(_matrix(document.get('correction')))
    earth = document.get('earth_field_enu_t')
    return dict(method=str(document.get('method', '')), output_frame=str(document.get('output_frame', '')),
                sample_count=document.get('sample_count'), mounting_deg=euler_zyx_deg(rotation),
                reflected=reflected, earth=None if earth is None else earth_angles(_vector(earth)),
                attitude=_stored_attitude(document.get(ATTITUDE_KEY)))


def earth_angles(enu_t: Sequence[float]) -> dict[str, Any]:
    """Declination and inclination (degrees) and the field in nT of an east/north/up field in tesla."""
    east, north, up = enu_t
    return dict(declination_deg=round(math.degrees(math.atan2(east, north)), _DIGITS),
                inclination_deg=round(math.degrees(math.atan2(-up, math.hypot(east, north))), _DIGITS),
                total_nt=round(math.sqrt(east * east + north * north + up * up) * 1e9, _DIGITS),
                enu_nt=[round(c * 1e9, _DIGITS) for c in enu_t])


def _stored_attitude(record: Any) -> dict[str, Any] | None:
    """A validated ``calibration_attitude`` record, or None when the document has none."""
    if record is None:
        return None
    columns, rows = (record.get('columns'), record.get('degrees')) if isinstance(record, dict) else (None, None)
    if not (isinstance(columns, list) and len(columns) == 3 and isinstance(rows, list)
            and all(isinstance(r, list) and len(r) == 3 for r in rows)):
        raise ValueError(f'{ATTITUDE_KEY} needs three columns and rows of yaw, pitch, roll')
    axis_values = record.get('axis_values')
    if not isinstance(axis_values, list) or len(axis_values) != len(rows):
        axis_values = list(range(len(rows)))
    return dict(columns=[str(c) for c in columns], axis=str(record.get('axis') or 'row'),
                axis_values=[_json_number(v) for v in axis_values],
                degrees=[[_json_number(v) for v in r] for r in rows])


def _matrix(value: Any) -> list[list[float]]:
    """``value`` as a 3x3 list of floats."""
    if not (isinstance(value, list) and len(value) == 3 and all(isinstance(r, list) and len(r) == 3 for r in value)):
        raise ValueError('the calibration correction must be a 3x3 matrix')
    return [[float(v) for v in row] for row in value]


def _vector(value: Any) -> list[float]:
    """``value`` as a list of three floats."""
    if not (isinstance(value, list) and len(value) == 3):
        raise ValueError('earth_field_enu_t must hold three numbers')
    return [float(v) for v in value]


def _scaled(value: float, factor: float) -> Optional[float]:
    """``value * factor`` rounded, or None when it is not finite."""
    return round(value * factor, _DIGITS) if math.isfinite(value) else None


def _number(value: float) -> Optional[float]:
    """``value``, or None when it is NaN or infinite."""
    return value if math.isfinite(value) else None


def _json_number(value: Any) -> Optional[float]:
    """A finite number from a JSON value, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)
