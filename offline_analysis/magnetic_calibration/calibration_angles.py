"""Angles of an onyx magnetic calibration, in degrees, for the Offline Data angle window.

The correction ``C`` is split into a rotation and a symmetric scale/soft-iron
part (polar decomposition ``C = R S``, from the SVD). ``R`` takes sensor axes
to the output frame (IMU body forward/right/down), and its aerospace Z-Y-X
yaw/pitch/roll (the onyx ``calibration.attitude`` convention) is the sensor
mounting the calibration holds: declared for the ellipsoid method, fitted
for the IMU method. The fitted Earth field of an IMU calibration (tesla,
east/north/up) gives declination (east of north) and inclination (positive
below horizontal). A document may carry ``calibration_attitude``: the
yaw/pitch/roll of every row it was fitted on.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

import numpy as np
from calibration.arrays import FloatArray
from scipy.spatial.transform import Rotation  # pyright: ignore[reportMissingTypeStubs]

from offline_analysis.magnetic_calibration.calibration_document import ATTITUDE_KEY

_DIGITS = 4


def calibration_angles(document: dict[str, Any]) -> dict[str, Any]:
    """Mounting yaw/pitch/roll, Earth-field angles and the stored calibration-scan attitude.

    ``document`` is a parsed ``onyx-vector-calibration/1`` JSON object.

    Raises:
        ValueError: when the correction is not a non-singular 3x3 matrix or the
            stored attitude is malformed.
    """
    rotation, reflected = polar_rotation(_array(document.get('correction'), (3, 3), 'correction'))
    earth = document.get('earth_field_enu_t')
    return dict(method=str(document.get('method', '')), output_frame=str(document.get('output_frame', '')),
                sample_count=document.get('sample_count'), mounting_deg=euler_zyx_deg(rotation),
                reflected=reflected, attitude=_stored_attitude(document.get(ATTITUDE_KEY)),
                earth=None if earth is None else earth_angles(_array(earth, (3,), 'earth_field_enu_t')))


def polar_rotation(matrix: FloatArray) -> tuple[FloatArray, bool]:
    """The rotation ``R`` of ``matrix = R S`` (S symmetric positive) and whether it mirrors.

    A matrix with a negative determinant has no proper rotation; its mirror
    image ``-matrix`` is decomposed instead and the flag is True.

    Raises:
        ValueError: when ``matrix`` is singular.
    """
    left, singular, right = np.linalg.svd(matrix)
    if singular.min() <= 1e-12 * max(singular.max(), 1e-300):
        raise ValueError('the calibration correction matrix is singular')
    sign = 1.0 if np.linalg.det(matrix) > 0 else -1.0
    return sign * (left @ right), sign < 0


def euler_zyx_deg(rotation: FloatArray) -> dict[str, float]:
    """Aerospace Z-Y-X yaw, pitch and roll (degrees, 4 decimals) of a rotation matrix."""
    yaw, pitch, roll = Rotation.from_matrix(rotation).as_euler('ZYX', degrees=True)
    return dict(yaw=round(float(yaw), _DIGITS), pitch=round(float(pitch), _DIGITS), roll=round(float(roll), _DIGITS))


def earth_angles(enu_t: Sequence[float] | FloatArray) -> dict[str, Any]:
    """Declination and inclination (degrees) and the field in nT of an east/north/up field in tesla."""
    east, north, up = (float(c) for c in enu_t)
    return dict(declination_deg=round(math.degrees(math.atan2(east, north)), _DIGITS),
                inclination_deg=round(math.degrees(math.atan2(-up, math.hypot(east, north))), _DIGITS),
                total_nt=round(math.sqrt(east * east + north * north + up * up) * 1e9, _DIGITS),
                enu_nt=[round(c * 1e9, _DIGITS) for c in (east, north, up)])


def _array(value: Any, shape: tuple[int, ...], name: str) -> FloatArray:
    """``value`` as a finite float array of ``shape``; ValueError naming ``name`` otherwise."""
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be numbers with shape {shape}') from error
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f'{name} must be numbers with shape {shape}')
    return array


def _stored_attitude(record: Any) -> Optional[dict[str, Any]]:
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


def _json_number(value: Any) -> Optional[float]:
    """A finite number from a JSON value, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)
