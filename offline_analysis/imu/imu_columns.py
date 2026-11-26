"""Find a scan's raw IMU columns: the accelerometer and gyroscope triples and their units.

Columns are grouped into x/y/z triples with onyx ``triples``. A triple is the
accelerometer when its name holds ``acc``, ``accel``, ``acceleration``,
``accelerometer`` or ``force`` (``specific_force_x``), the gyroscope when it
holds ``gyro``, ``gyr``, ``gyroscope``, ``angular`` (``angular_rate_x``) or
``omega``. Units come from the column name: ``g`` (``acc_x [g]``) means
standard gravities, ``deg``/``dps``/``°`` means degrees per second; otherwise
m/s² and rad/s. Axes x/y/z are the IMU body axes forward/right/down, the onyx
``navigation`` convention (a level IMU at rest reads (0, 0, -g), as the VN-100 does).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from navigation import STANDARD_GRAVITY_M_S2
from scans.columns.channels import tokens
from scans.columns.components import Triple, triples

_ACCELEROMETER = frozenset(('acc', 'accel', 'acceleration', 'accelerometer', 'force'))
_GYROSCOPE = frozenset(('gyro', 'gyr', 'gyroscope', 'angular', 'omega'))
_IN_G = re.compile(r'(^|[^a-z])g($|[^a-z])')
_IN_DEGREES = re.compile(r'deg|dps|°')


@dataclass(frozen=True)
class RawImuColumns:
    """The accelerometer triple, the gyroscope triple when present, and their unit factors.

    Attributes:
        accelerometer: x/y/z specific-force columns.
        gyroscope: x/y/z angular-rate columns, or None.
        to_m_s2: factor converting accelerometer values to m/s².
        to_rad_s: factor converting gyroscope values to rad/s.
    """

    accelerometer: Triple
    gyroscope: Optional[Triple]
    to_m_s2: float = 1.0
    to_rad_s: float = 1.0

    @classmethod
    def find(cls, names: Iterable[str]) -> Optional[RawImuColumns]:
        """The raw IMU columns among ``names``, or None without an accelerometer triple."""
        found = triples(list(names))
        accelerometer = _first_triple(found, _ACCELEROMETER)
        if accelerometer is None:
            return None
        gyroscope = _first_triple(found, _GYROSCOPE)
        return cls(accelerometer, gyroscope, acceleration_scale(accelerometer[0]),
                   1.0 if gyroscope is None else rate_scale(gyroscope[0]))

    @property
    def names(self) -> tuple[str, ...]:
        """Every raw IMU column, accelerometer first."""
        return self.accelerometer + (self.gyroscope or ())


def acceleration_scale(name: str) -> float:
    """Factor converting the accelerometer column ``name`` to m/s² (g or m/s²)."""
    return STANDARD_GRAVITY_M_S2 if _IN_G.search(name.lower()) else 1.0


def rate_scale(name: str) -> float:
    """Factor converting the gyroscope column ``name`` to rad/s (deg/s or rad/s)."""
    return math.pi / 180.0 if _IN_DEGREES.search(name.lower()) else 1.0


def _first_triple(found: dict[str, Triple], words: frozenset[str]) -> Optional[Triple]:
    """The first triple whose vector key holds one of ``words`` as a token."""
    return next((triple for key, triple in found.items() if words.intersection(tokens(key))), None)
