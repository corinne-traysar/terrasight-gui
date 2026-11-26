"""Sample times in seconds for integrating a gyroscope, taken from a scan's time axis.

onyx ``navigation`` needs strictly increasing times. The Pi's VN-100 recordings
stamp rows with receipt times, and packets read together share one time, so
each group of equal times is spread evenly up to the next distinct time (the
last group uses the median step). Times that go backwards are an error. The
unit comes from the axis name: ``_ms`` milliseconds, ``_us`` microseconds,
otherwise seconds (onyx's reader already turns ISO-8601 times into seconds).
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np
from calibration.arrays import FloatArray
from numpy.typing import ArrayLike
from scans.columns.channels import normalize

_TIME_AXIS = re.compile(r'^(time|timestamp|t|received|elapsed|nominal_elapsed)(_([a-z]+))?$')
_UNITS = {'ms': 1e-3, 'us': 1e-6}


class SampleTimes:
    """Turns a scan's sample axis into strictly increasing seconds."""

    @staticmethod
    def seconds_per_unit(axis: str) -> Optional[float]:
        """Seconds per axis unit when ``axis`` names a time column, else None."""
        match = _TIME_AXIS.match(normalize(axis))
        if match is None:
            return None
        return _UNITS.get(match.group(3) or '', 1.0)

    @staticmethod
    def strictly_increasing(times: ArrayLike) -> FloatArray:
        """``times`` with each run of equal values spread evenly toward the next value.

        Raises:
            ValueError: if the times go backwards or hold fewer than two distinct values.
        """
        times = np.asarray(times, dtype=np.float64)
        if np.any(np.diff(times) < 0):
            raise ValueError('the time axis goes backwards; sort the scan by time')
        values, first, counts = np.unique(times, return_index=True, return_counts=True)
        if values.size < 2:
            raise ValueError('the time axis needs at least two distinct times')
        steps = np.diff(values)
        steps = np.append(steps, np.median(steps))
        position = np.arange(times.size) - np.repeat(first, counts)
        return times + position / np.repeat(counts, counts) * np.repeat(steps, counts)

    @classmethod
    def of_axis(cls, axis: str, values: ArrayLike) -> FloatArray:
        """Strictly increasing seconds from the sample axis ``axis`` and its ``values``.

        Raises:
            ValueError: if the axis is not a time axis or its times are unusable.
        """
        scale = cls.seconds_per_unit(axis)
        if scale is None:
            raise ValueError(f'the sample axis {axis!r} is not a time axis')
        return cls.strictly_increasing(np.asarray(values, dtype=np.float64) * scale)
