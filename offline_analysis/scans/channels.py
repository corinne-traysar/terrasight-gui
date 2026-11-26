"""Pick the sample axis, the B-axis channels and the IMU channels of a scan by name.

Names are matched case-insensitively after a trailing unit such as ``[nT]`` or
``(s)`` is removed. A magnetic sensor reports one static field value per axis
(``Bx``, ``mag_y``, ``field_T_2``, ``magnetic_x_gauss``); an electromagnetic
sensor reports per-axis phasor parts, amplitude or phase (``Bx_re``,
``field_T_real_0``, ``strength_T_1``, ``theta_rad_2``). IMU channels are shared
by both sensors.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Tuple

_SEP = r'[_.\- ]*'
_AXIS = r'(x|y|z|e|n|u|east|north|up|[012])'
_PART = r'(real|imag|re|im|amp|amplitude|mag|magnitude|abs|phase|i|q)'
_IMU = re.compile(r'(^|[_.\- ])((imu|acc|gyr|quat|euler|orient|incl|tilt|omega|angular)[a-z]*'
                  r'|roll|pitch|yaw|heading|q[wxyz0-3]|[agw][xyz])(?=$|[_.\- 0-9])')
# ``received_utc`` / ``received_ms`` are the Pi receipt times of the VN-100 CSV recordings.
_AXIS_NAMES = (re.compile(r'^(time|timestamp|t|received)(_[a-z]+)?$'), re.compile(r'^distance(_m)?$'),
               re.compile(r'^(s|s_m)$'), re.compile(r'^(source_index|sample|index|row)$'))


def normalize(name: str) -> str:
    """Lower-case ``name`` and drop a trailing bracketed unit: ``'Bx [nT]'`` -> ``'bx'``."""
    return re.sub(r'\s*[\[(][^\])]*[\])]\s*$', '', name).strip().lower()


def is_imu(name: str) -> bool:
    """True when ``name`` is an accelerometer, gyroscope or orientation channel."""
    return bool(_IMU.search(normalize(name)))


def find_axis(names: Iterable[str]) -> str | None:
    """Return the best sample-axis column (time first, then distance, then index), or None."""
    names = list(names)
    for pattern in _AXIS_NAMES:
        for name in names:
            if pattern.match(normalize(name)):
                return name
    return None


@dataclass(frozen=True)
class ChannelSet:
    """The B-axis and IMU channels chosen from one scan, in file order."""

    b_axes: Tuple[str, ...]
    imu: Tuple[str, ...]

    @property
    def all(self) -> tuple[str, ...]:
        """B-axis channels followed by IMU channels."""
        return self.b_axes + self.imu


class SensorProfile(ABC):
    """How one sensor type names its B-axis channels."""

    label: str

    @property
    @abstractmethod
    def b_pattern(self) -> re.Pattern[str]:
        """Regular expression a normalized B-axis channel name must fully match."""

    def is_b_axis(self, name: str) -> bool:
        """True when ``name`` is one of this sensor's B-axis channels."""
        return bool(self.b_pattern.fullmatch(normalize(name)))

    def select(self, names: Iterable[str]) -> ChannelSet:
        """Split ``names`` into B-axis and IMU channels; a B-axis match wins over IMU."""
        names = list(names)
        b_axes = tuple(n for n in names if self.is_b_axis(n))
        imu = tuple(n for n in names if n not in b_axes and is_imu(n))
        return ChannelSet(b_axes, imu)


class MagneticProfile(SensorProfile):
    """Three-axis magnetometer: one static field value per axis."""

    label = 'Magnetic'

    @property
    def b_pattern(self) -> re.Pattern[str]:
        """``b``, ``mag``, ``magnetic``, ``magnetometer``, ``b_field`` or ``field[_t|_nt]`` plus an axis."""
        return re.compile(rf'(b|mag|magnetic|magnetometer|b_?field|field(_t|_nt)?){_SEP}{_AXIS}'
                          r'(_(t|nt|ut|gauss))?')


class ElectromagneticProfile(SensorProfile):
    """AC (electromagnetic) sensor: per-axis phasor parts, amplitude or phase."""

    label = 'Electromagnetic'

    @property
    def b_pattern(self) -> re.Pattern[str]:
        """A field or strength/phase prefix, an optional part, an axis and an optional part."""
        prefix = r'(b|h|em|field(_t)?|strength(_t)?|theta(_rad)?|amp(litude)?|phase)'
        return re.compile(rf'{prefix}({_SEP}{_PART})?{_SEP}{_AXIS}({_SEP}{_PART})?'
                          r'(_(t|nt|ut|rad|deg))?')


PROFILES: dict[str, SensorProfile] = {'magnetic': MagneticProfile(),
                                      'electromagnetic': ElectromagneticProfile()}
