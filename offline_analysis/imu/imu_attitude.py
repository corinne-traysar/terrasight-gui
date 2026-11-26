"""Add yaw/pitch/roll columns computed from raw IMU readings to an onyx scan table.

A scan that already has yaw, pitch and roll columns (the VN-100 recordings)
is returned unchanged: the sensor's own attitude is better than one computed
here. A scan with a raw accelerometer triple (and usually a gyroscope) gets
``imu_yaw_rad``, ``imu_pitch_rad`` and ``imu_roll_rad`` (see
``attitude_sources``), which onyx scans then read as the IMU attitude. Rows
with a missing reading get NaN angles. The metadata key ``imu_attitude``
records how the angles were made.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
from calibration.arrays import FloatArray
from scans import ScanTable
from scans.columns.attitude_columns import attitude_columns

from offline_analysis.imu.attitude_sources import AttitudeSource, ImuReadings
from offline_analysis.imu.imu_columns import RawImuColumns
from offline_analysis.imu.sample_times import SampleTimes

ANGLE_COLUMNS = ('imu_yaw_rad', 'imu_pitch_rad', 'imu_roll_rad')
METADATA_KEY = 'imu_attitude'


class ImuAttitude:
    """Derives the attitude of scans whose IMU reports only raw readings."""

    def augment(self, table: ScanTable) -> ScanTable:
        """``table`` plus derived angle columns when it has raw IMU readings and no angles."""
        columns = RawImuColumns.find(table.channels)
        if attitude_columns(table.channels) is not None or columns is None:
            return table
        readings, rows, note = self.readings(table, columns)
        if readings is None:
            return table
        source = AttitudeSource.best_for(readings)
        angles = np.full((table.rows, 3), np.nan)
        angles[rows] = source.angles_rad(readings)
        record = dict(source=source.name, columns=list(columns.names), rows=readings.count,
                      yaw=source.yaw, note=note)
        new = {name: angles[:, k] for k, name in enumerate(ANGLE_COLUMNS)}
        return ScanTable(table.axis, {**table.columns, **new},
                         {**table.metadata, METADATA_KEY: record}, table.sensor)

    @staticmethod
    def readings(table: ScanTable, columns: RawImuColumns) -> tuple[Optional[ImuReadings], Any, str]:
        """The complete rows' readings, their row mask and a note (readings None when no row is complete)."""
        force = _stack(table, columns.accelerometer, columns.to_m_s2)
        rate = None if columns.gyroscope is None else _stack(table, columns.gyroscope, columns.to_rad_s)
        rows = np.isfinite(force).all(axis=1)
        if rate is not None:
            rows &= np.isfinite(rate).all(axis=1) & np.isfinite(table.columns[table.axis])
        if not rows.any():
            return None, rows, 'no row has every raw IMU value'
        times, note = _times(table, rows) if rate is not None else (None, 'no gyroscope columns')
        readings = ImuReadings(force[rows], None if rate is None else rate[rows], times)
        return readings, rows, note


def _stack(table: ScanTable, names: tuple[str, str, str], scale: float) -> FloatArray:
    """The three columns ``names`` times ``scale``, as an (N, 3) array."""
    return np.column_stack([table.columns[name] * scale for name in names])


def _times(table: ScanTable, rows: Any) -> tuple[Optional[FloatArray], str]:
    """Seconds of the ``rows`` for the gyroscope, or None and why they cannot be used."""
    try:
        return SampleTimes.of_axis(table.axis, table.columns[table.axis][rows]), ''
    except ValueError as error:
        return None, f'gyroscope not used: {error}'
