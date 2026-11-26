"""Find a scan's IMU yaw/pitch/roll columns and convert them to radians.

A column is an angle when its name holds the token ``yaw`` (or ``heading``),
``pitch`` or ``roll``; rate and acceleration channels (``gyro_yaw``,
``yaw_rate``) are not angles. The unit comes from the name (``rad`` or
``deg``/``°``); a name without one is read as degrees when any value exceeds
2π in size, else radians. The onyx convention applies: aerospace Z-Y-X,
body forward/right/down.
"""
from __future__ import annotations

import math
import re
from typing import Iterable, Sequence, Tuple

from offline_analysis.scans.channels import normalize

AttitudeColumns = Tuple[str, str, str]
_ANGLE_WORDS = (('yaw', 'heading'), ('pitch',), ('roll',))
_NOT_ANGLE = frozenset(('gyro', 'gyr', 'rate', 'omega', 'acc', 'accel', 'dot', 'speed'))


def attitude_columns(names: Iterable[str]) -> AttitudeColumns | None:
    """Return the (yaw, pitch, roll) column names in that order, or None if any is missing."""
    names = list(names)
    yaw, pitch, roll = (next((name for name in names if _is_angle(name, words)), None)
                        for words in _ANGLE_WORDS)
    if yaw is None or pitch is None or roll is None:
        return None
    return yaw, pitch, roll


def angle_scale(name: str, values: Sequence[float]) -> float:
    """Factor converting the column ``name`` with ``values`` to radians (1 or π/180)."""
    lowered = name.lower()
    if re.search(r'(^|[^a-z])rad', lowered):
        return 1.0
    if '°' in lowered or re.search(r'(^|[^a-z])deg', lowered):
        return math.pi / 180.0
    finite = [abs(v) for v in values if math.isfinite(v)]
    return math.pi / 180.0 if finite and max(finite) > 2 * math.pi else 1.0


def _is_angle(name: str, words: tuple[str, ...]) -> bool:
    """True when ``name`` has one of ``words`` as a token and no rate/acceleration token."""
    tokens = set(re.split(r'[_.\- ]+', normalize(name)))
    return bool(tokens.intersection(words)) and not tokens.intersection(_NOT_ANGLE)
