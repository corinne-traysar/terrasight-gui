"""Ways to turn raw IMU readings into yaw/pitch/roll with onyx ``navigation``.

``GyroscopeAttitude`` integrates the gyroscope with onyx ``StrapdownNavigator``:
roll and pitch are levelled from the first rows (the IMU must start at rest)
and yaw starts at 0, so yaw is relative to the starting heading and drifts
with gyro bias. ``AccelerometerAttitude`` has no gyroscope: each row's roll and
pitch come from the direction of gravity (onyx ``level_attitude``), which is
right only while the IMU is not accelerating, and yaw cannot be observed, so
it is 0 (facing north). Angles are radians, aerospace Z-Y-X, body
forward/right/down (onyx ``calibration.attitude``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Optional

import numpy as np
from calibration.arrays import FloatArray
from navigation import ImuSamples, StrapdownNavigator, level_attitude

LEVEL_SAMPLES = 10
"""Rows averaged to level roll and pitch before integrating the gyroscope."""


@dataclass(frozen=True, eq=False)
class ImuReadings:
    """Row-aligned raw IMU readings of the complete rows of a scan.

    Attributes:
        force_m_s2: (N, 3) accelerometer specific force, body axes, m/s².
        rate_rad_s: (N, 3) gyroscope angular rate, body axes, rad/s, or None.
        time_s: (N,) strictly increasing seconds, or None without a usable time axis.
    """

    force_m_s2: FloatArray
    rate_rad_s: Optional[FloatArray] = None
    time_s: Optional[FloatArray] = None

    @property
    def count(self) -> int:
        """Number of rows."""
        return int(self.force_m_s2.shape[0])


class AttitudeSource(ABC):
    """One way of computing (N, 3) yaw/pitch/roll in radians from ``ImuReadings``."""

    name: ClassVar[str] = ''
    """Short name recorded with the angles ("gyroscope" or "accelerometer")."""
    yaw: ClassVar[str] = ''
    """What the yaw angle means for this source, shown to the user."""

    @staticmethod
    def best_for(readings: ImuReadings) -> AttitudeSource:
        """The gyroscope source when rates and two or more timed rows exist, else accelerometer."""
        usable = readings.rate_rad_s is not None and readings.time_s is not None and readings.count >= 2
        return GyroscopeAttitude() if usable else AccelerometerAttitude()

    @abstractmethod
    def angles_rad(self, readings: ImuReadings) -> FloatArray:
        """(N, 3) yaw, pitch, roll in radians, one row per reading."""


class GyroscopeAttitude(AttitudeSource):
    """Strapdown integration of the gyroscope from a levelled start."""

    name = 'gyroscope'
    yaw = 'relative to the heading at the first row (integrated gyroscope; drifts with gyro bias)'

    def angles_rad(self, readings: ImuReadings) -> FloatArray:
        """Integrate with onyx ``StrapdownNavigator``; ValueError without rates or times."""
        if readings.rate_rad_s is None or readings.time_s is None:
            raise ValueError('integrating the gyroscope needs angular rates and a time axis')
        navigator = StrapdownNavigator(level_samples=min(LEVEL_SAMPLES, readings.count))
        samples = ImuSamples(readings.time_s, readings.force_m_s2, readings.rate_rad_s)
        return navigator.navigate(samples).yaw_pitch_roll_rad


class AccelerometerAttitude(AttitudeSource):
    """Roll and pitch of every row from gravity alone; yaw is 0."""

    name = 'accelerometer'
    yaw = 'not observable from an accelerometer; set to 0 (facing north)'

    def angles_rad(self, readings: ImuReadings) -> FloatArray:
        """onyx ``level_attitude`` of each row on its own."""
        return np.array([level_attitude(row[None, :]) for row in readings.force_m_s2])
