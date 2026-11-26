"""Fit and apply onyx magnetic calibrations to magnetic recordings.

Needs numpy and the onyx ``calibration`` package. Methods: ``ellipsoid``
(field only: offset, scale and soft iron; components keep the sensor's
misalignment) and ``imu`` (field plus yaw/pitch/roll: also misalignment to the
IMU and the Earth field). ``auto`` picks ``imu`` when the recording has
attitude, else ``ellipsoid``. The fit is scaled to a reference |B|, by default
the WMM2025 Bar-Gyora total field. Mounting ``enu`` means sensor X/Y/Z =
east/north/up on a level, north-facing body (the synthetic-data convention);
``body`` means the sensor axes already are forward/right/down (as on the
VN-100). Mounting only matters for the ellipsoid method; the IMU method fits it.
"""
from __future__ import annotations

import numpy as np
from calibration import (SENSOR_ENU_TO_BODY, EllipsoidCalibration, ImuCalibration,
                         VectorCalibration, VectorCalibrationParameters)
from calibration.arrays import FloatArray

from offline_analysis.magnetic_calibration.magnetic_recording import NT_TO_T, MagneticRecording
from offline_analysis.magnetic_calibration.reference import DEFAULT_REFERENCE_NT, METHODS

MOUNTINGS = {'enu': SENSOR_ENU_TO_BODY, 'body': np.eye(3)}


def choose_method(recording: MagneticRecording, method: str = 'auto') -> str:
    """Resolve ``method`` for ``recording``: 'imu' or 'ellipsoid'.

    Raises:
        ValueError: on an unknown method, or 'imu' without attitude columns.
    """
    if method not in METHODS:
        raise ValueError(f'unknown method {method!r}; choose one of {", ".join(METHODS)}')
    if method == 'auto':
        return 'imu' if recording.has_attitude else 'ellipsoid'
    if method == 'imu' and not recording.has_attitude:
        raise ValueError('the imu method needs yaw, pitch and roll columns in the scan')
    return method


def build_calibration(method: str, reference_nt: float = DEFAULT_REFERENCE_NT,
                      mounting: str = 'enu') -> VectorCalibration:
    """An unfitted onyx calibration for 'ellipsoid' or 'imu' scaled to ``reference_nt``.

    Raises:
        ValueError: on an unknown method or mounting, or a non-positive reference.
    """
    if mounting not in MOUNTINGS:
        raise ValueError(f'unknown mounting {mounting!r}; choose enu or body')
    if method == 'ellipsoid':
        return EllipsoidCalibration(reference_nt * NT_TO_T, MOUNTINGS[mounting])
    if method == 'imu':
        return ImuCalibration(reference_nt * NT_TO_T)
    raise ValueError(f'unknown method {method!r}; choose ellipsoid or imu')


def fit_recording(recording: MagneticRecording, method: str = 'auto',
                  reference_nt: float = DEFAULT_REFERENCE_NT,
                  mounting: str = 'enu') -> VectorCalibrationParameters:
    """Fit a calibration to ``recording`` and return its parameters.

    Raises:
        ValueError: on bad options, too few rows, or readings that do not
            cover enough orientations for the chosen method.
    """
    calibration = build_calibration(choose_method(recording, method), reference_nt, mounting)
    return calibration.fit(recording.samples())


def calibrated_enu_nt(parameters: VectorCalibrationParameters,
                      recording: MagneticRecording) -> FloatArray:
    """(N, 3) calibrated B east/north/up in nT for every row of ``recording``.

    Uses the recording's attitude when present; without it the sensor is taken
    as level and facing north (onyx ``calibrated_enu``).
    """
    calibration = EllipsoidCalibration(parameters.reference_magnitude_t)
    calibration.restore(parameters)
    enu = calibration.calibrated_enu(recording.field_t, recording.attitude_rad)
    return np.column_stack(enu) / NT_TO_T
