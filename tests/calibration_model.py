"""Synthetic magnetic calibration data shared by the onyx scan and calibration tests.

Needs numpy, scipy and onyx ``scans``, ``calibration`` and ``navigation``
(Python 3.12+); ``MISSING`` holds the reason when they do not import (as on
the Pi without onyx), and the tests skip with it.

Synthetic model (onyx convention): raw_i = A (M^T R_i^T h) + b, in nT. ``R_i``
takes IMU body forward/right/down to east/north/up for yaw/pitch/roll i
(aerospace Z-Y-X); ``h`` is the WMM2025 Bar-Gyora field (east/north/up); ``M``
is the sensor mounting (X/Y/Z = east/north/up when level, facing north); ``A``
the distortion and ``b`` the offset. A correct calibration returns ``h`` for
every row; 0.01 nT on a ~45,000 nT field leaves room for round-off only.
"""
from offline_analysis.magnetic_calibration.reference import BAR_GYORA_ENU_NT


def missing_reason():
    """None when numpy, scipy and onyx ``scans``/``calibration``/``navigation`` import, else why not."""
    try:
        import numpy  # noqa: F401
        import scipy.spatial.transform  # noqa: F401
        import calibration  # noqa: F401
        import navigation  # noqa: F401
        import scans  # noqa: F401
    except (ImportError, SyntaxError) as error:
        return f'numpy, scipy and onyx scans/calibration/navigation are needed: {error}'
    return None


MISSING = missing_reason()

TOLERANCE_NT = 0.01


def model():
    """Offset, symmetric soft iron, a small misalignment and the NED/ENU swap."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    offset = np.array([1200.0, -800.0, 450.0])
    soft_iron = np.array([[1.05, 0.02, -0.01], [0.02, 0.97, 0.015], [-0.01, 0.015, 1.02]])
    misalignment = Rotation.from_euler('xyz', [2.0, -1.5, 1.0], degrees=True).as_matrix()
    ned_to_enu = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
    return offset, soft_iron, misalignment, ned_to_enu


def attitudes_rad(count, seed=7):
    """(count, 3) yaw, pitch, roll in radians of uniformly random orientations."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    return Rotation.random(count, rng=np.random.default_rng(seed)).as_euler('ZYX')


def raw_field_nt(attitude_rad, distortion):
    """(N, 3) raw sensor readings in nT for each attitude row (see module model)."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    offset, _, _, ned_to_enu = model()
    body_to_enu = ned_to_enu @ Rotation.from_euler('ZYX', attitude_rad).as_matrix()
    body = np.einsum('nji,j->ni', body_to_enu, np.array(BAR_GYORA_ENU_NT))
    return (body @ ned_to_enu) @ distortion.T + offset


def recording(with_attitude=True, distortion=None, count=60):
    """An onyx MagneticScan of ``count`` random orientations: Bx/By/Bz in nT, angles in radians."""
    import numpy as np
    from scans import MagneticScan
    distortion = model()[1] if distortion is None else distortion
    attitude = attitudes_rad(count)
    field = raw_field_nt(attitude, distortion)
    columns = {'t': np.arange(count, dtype=float), 'Bx_nT': field[:, 0], 'By_nT': field[:, 1], 'Bz_nT': field[:, 2]}
    if with_attitude:
        columns.update(yaw_rad=attitude[:, 0], pitch_rad=attitude[:, 1], roll_rad=attitude[:, 2])
    return MagneticScan(columns, 't')


def scan(**columns):
    """An onyx ScanData with sample axis ``t`` = 0, 1, 2 and the given columns."""
    from scans import ScanData
    return ScanData({'t': (0.0, 1.0, 2.0), **columns}, 't')


def calibration_text(with_attitude, count=80):
    """A synthetic calibration scan CSV (nT, degrees) of ``count`` random orientations."""
    import numpy as np
    _, soft_iron, misalignment, _ = model()
    attitude = attitudes_rad(count)
    field = raw_field_nt(attitude, soft_iron @ misalignment if with_attitude else soft_iron)
    header = ['time [s]', 'Bx [nT]', 'By [nT]', 'Bz [nT]'] + (['yaw [deg]', 'pitch [deg]', 'roll [deg]'] if with_attitude else [])
    rows = [[i, *field[i], *(np.degrees(attitude[i]) if with_attitude else [])] for i in range(count)]
    return '\n'.join([','.join(header)] + [','.join(repr(float(v)) for v in row) for row in rows]) + '\n'
