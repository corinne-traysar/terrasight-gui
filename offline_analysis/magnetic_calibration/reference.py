"""Calibration defaults that need no third-party packages.

The reference field is WMM2025 at the Bar-Gyora observatory, Israel (the
values of onyx ``magnetics.earth_field.ISRAEL_BAR_GYORA``), east/north/up, nT.
"""
import math

BAR_GYORA_ENU_NT = (2608.0, 30063.0, -33654.0)
DEFAULT_REFERENCE_NT = math.sqrt(sum(c * c for c in BAR_GYORA_ENU_NT))
METHODS = ('auto', 'ellipsoid', 'imu')
MOUNTING_NAMES = ('enu', 'body')
