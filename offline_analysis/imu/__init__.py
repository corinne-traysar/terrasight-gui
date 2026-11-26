"""Raw IMU readings to yaw/pitch/roll, so onyx scans and calibrations can use them.

An IMU that reports only specific force (accelerometer) and angular rate
(gyroscope) gives no angles; onyx ``scans`` and ``calibration`` need
yaw/pitch/roll. ``imu_columns`` finds the raw columns, ``sample_times`` makes a
usable time axis, ``attitude_sources`` turns readings into angles with onyx
``navigation`` and ``imu_attitude`` adds the angle columns to a scan table.
Needs numpy and onyx (Python 3.12+).
"""
