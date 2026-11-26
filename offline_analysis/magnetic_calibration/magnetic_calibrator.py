"""Fit onyx magnetic calibrations to onyx ``MagneticScan`` objects with the dashboard's options.

Methods: ``ellipsoid`` (field only: offset, scale and soft iron; components
keep the sensor's misalignment) and ``imu`` (field plus yaw/pitch/roll: also
misalignment to the IMU and the Earth field). ``auto`` picks ``imu`` when the
scan has yaw/pitch/roll (its own or derived from a raw IMU), else
``ellipsoid``. The fit is scaled to a reference |B|, by default the WMM2025
Bar-Gyora total field. Mounting ``enu`` means sensor X/Y/Z = east/north/up on
a level, north-facing body (the synthetic-data convention); ``body`` means
the sensor axes already are forward/right/down (as on the VN-100). Mounting
only matters for the ellipsoid method; the IMU method fits it.
"""
from __future__ import annotations

import numpy as np
from calibration import SENSOR_ENU_TO_BODY, EllipsoidCalibration, ImuCalibration, VectorCalibration
from scans import MagneticScan

from offline_analysis.magnetic_calibration.reference import DEFAULT_REFERENCE_NT, METHODS

NANOTESLA = 1e-9
MOUNTINGS = {'enu': SENSOR_ENU_TO_BODY, 'body': np.eye(3)}


class MagneticCalibrator:
    """A fitting method, reference |B| (nT) and mounting, applied to magnetic scans."""

    def __init__(self, method: str = 'auto', reference_nt: float = DEFAULT_REFERENCE_NT, mounting: str = 'enu'):
        """Check and store the options.

        Raises:
            ValueError: on an unknown method or mounting, or a non-positive reference.
        """
        if method not in METHODS:
            raise ValueError(f'unknown method {method!r}; choose one of {", ".join(METHODS)}')
        if mounting not in MOUNTINGS:
            raise ValueError(f'unknown mounting {mounting!r}; choose enu or body')
        if not reference_nt > 0:
            raise ValueError('reference_nt must be a positive number of nT')
        self.method, self.reference_nt, self.mounting = method, reference_nt, mounting

    def method_for(self, scan: MagneticScan) -> str:
        """'imu' or 'ellipsoid' for ``scan``; ValueError for 'imu' without yaw/pitch/roll."""
        has_attitude = scan.attitude_columns is not None
        if self.method == 'auto':
            return 'imu' if has_attitude else 'ellipsoid'
        if self.method == 'imu' and not has_attitude:
            raise ValueError('the imu method needs yaw, pitch and roll columns (or a raw IMU) in the scan')
        return self.method

    def build(self, method: str) -> VectorCalibration:
        """An unfitted onyx calibration for 'ellipsoid' or 'imu'."""
        reference_t = self.reference_nt * NANOTESLA
        if method == 'ellipsoid':
            return EllipsoidCalibration(reference_t, MOUNTINGS[self.mounting])
        if method == 'imu':
            return ImuCalibration(reference_t)
        raise ValueError(f'unknown method {method!r}; choose ellipsoid or imu')

    def fit(self, scan: MagneticScan) -> VectorCalibration:
        """A calibration fitted to ``scan`` with onyx ``MagneticScan.fit_calibration``.

        Raises:
            ValueError: on too few rows, or readings that do not cover enough
                orientations for the chosen method.
        """
        calibration = self.build(self.method_for(scan))
        scan.fit_calibration(calibration)
        return calibration
