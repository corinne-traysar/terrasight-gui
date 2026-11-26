"""Raw IMU scans (accelerometer and gyroscope only, no angles) shared by the IMU tests.

Body axes forward/right/down, the onyx convention: a level IMU at rest reads
specific force (0, 0, -g). A turn about the down axis at ``yaw_rate`` rad/s
leaves the force unchanged and gives yaw = ``yaw_rate`` * t.
"""
G = 9.80665
RAW_HEADER = ['time_s', 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z']


def tilted_force(pitch, roll):
    """Specific force (m/s², forward/right/down) of an IMU at rest with this pitch and roll.

    f = -g_body = (g sin(pitch), -g sin(roll) cos(pitch), -g cos(roll) cos(pitch)).
    """
    import math
    return [G * math.sin(pitch), -G * math.sin(roll) * math.cos(pitch), -G * math.cos(roll) * math.cos(pitch)]


def raw_rows(count=11, yaw_rate=0.1, step=1.0):
    """Rows of RAW_HEADER: level, at rest, turning about down at ``yaw_rate`` rad/s."""
    return [[i * step, 0.0, 0.0, -G, 0.0, 0.0, yaw_rate] for i in range(count)]


def raw_columns(rows, header=None):
    """``rows`` as a column dict keyed by ``header`` (RAW_HEADER by default)."""
    header = header or RAW_HEADER
    return {name: [row[k] for row in rows] for k, name in enumerate(header)}


def raw_table(rows=None, header=None, axis=None):
    """An onyx ScanTable of raw IMU rows (built lazily so the module imports without onyx)."""
    from scans import ScanTable
    return ScanTable.build(raw_columns(rows or raw_rows(), header), axis)


def tumble(count=300, step=0.1, rest=10, seed=3):
    """True (count, 3) yaw/pitch/roll, specific force and gyro rates of a raw-IMU tumble.

    The first ``rest`` rows are level and still (for levelling); after that the
    body turns at random rates. Each interval turns by the mean of its two rate
    rows, applied in body axes: the rule onyx ``StrapdownNavigator`` integrates.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation
    rates = np.random.default_rng(seed).normal(0.0, 1.0, (count, 3))
    rates[:rest] = 0.0
    attitudes = [Rotation.identity()]
    for k in range(count - 1):
        attitudes.append(attitudes[-1] * Rotation.from_rotvec(0.5 * (rates[k] + rates[k + 1]) * step))
    body_to_ned = Rotation.concatenate(attitudes)
    force = body_to_ned.inv().apply([0.0, 0.0, -G])
    return body_to_ned.as_euler('ZYX'), force, rates


def tumble_text(field_nt, force, rates, step=0.1):
    """CSV of a raw-IMU magnetic scan: time, Bx/By/Bz in nT, accelerometer and gyroscope."""
    lines = [','.join(RAW_HEADER[:1] + ['Bx_nT', 'By_nT', 'Bz_nT'] + RAW_HEADER[1:])]
    for k in range(len(field_nt)):
        lines.append(','.join(repr(float(v)) for v in [k * step, *field_nt[k], *force[k], *rates[k]]))
    return '\n'.join(lines) + '\n'


def raw_magnetic_text(count=11, yaw_rate=0.1):
    """CSV of a raw-IMU magnetic scan: constant field (1, 2, 3) nT plus RAW_HEADER columns."""
    header = RAW_HEADER[:1] + ['Bx_nT', 'By_nT', 'Bz_nT'] + RAW_HEADER[1:]
    lines = [','.join(header)]
    for row in raw_rows(count, yaw_rate):
        lines.append(','.join(str(v) for v in [row[0], 1.0, 2.0, 3.0, *row[1:]]))
    return '\n'.join(lines) + '\n'
