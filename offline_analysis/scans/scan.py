"""A scan as named numeric columns over one sample axis, and cropping it.

The sample axis is the column rows are ordered by (time, distance or row
number); its unit is whatever the source file used. Values are floats; a
missing cell is NaN.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

ROW_AXIS = 'row'


@dataclass(frozen=True)
class Scan:
    """Named float columns of equal length plus the name of the sample-axis column."""

    axis: str
    columns: Dict[str, Tuple[float, ...]]

    def __post_init__(self) -> None:
        """Check that the axis exists and every column has the same length.

        Raises:
            ValueError: on a missing axis column or ragged columns.
        """
        if self.axis not in self.columns:
            raise ValueError(f'axis column {self.axis!r} is not in the scan')
        if len({len(values) for values in self.columns.values()}) != 1:
            raise ValueError('all scan columns must have the same length')

    @property
    def rows(self) -> int:
        """Number of samples."""
        return len(self.columns[self.axis])

    @property
    def axis_values(self) -> tuple[float, ...]:
        """Sample-axis values, in the source file's unit."""
        return self.columns[self.axis]

    @property
    def channels(self) -> list[str]:
        """Every column name except the sample axis, in file order."""
        return [name for name in self.columns if name != self.axis]

    def axis_range(self) -> tuple[float, float]:
        """Smallest and largest finite sample-axis value.

        Raises:
            ValueError: if the axis has no finite value.
        """
        finite = [v for v in self.axis_values if math.isfinite(v)]
        if not finite:
            raise ValueError('the sample axis has no finite values')
        return min(finite), max(finite)

    def crop(self, start: float, end: float, channels: Sequence[str]) -> Scan:
        """Keep the rows with ``start <= axis <= end`` and only ``channels``.

        ``start`` and ``end`` may be given in either order. The axis column is
        always kept.

        Raises:
            ValueError: on an unknown channel, no channel, or an empty window.
        """
        unknown = [name for name in channels if name not in self.columns]
        if unknown:
            raise ValueError(f'unknown channels: {", ".join(unknown)}')
        if not channels:
            raise ValueError('select at least one channel to keep')
        keep = window_rows(self.axis_values, start, end)
        if not keep:
            raise ValueError('the crop window contains no samples')
        names = [self.axis] + [name for name in channels if name != self.axis]
        return Scan(self.axis, {n: tuple(self.columns[n][i] for i in keep) for n in names})


def window_rows(axis: Sequence[float], start: float, end: float) -> list[int]:
    """Return the row indices whose axis value lies in the closed window [start, end].

    The bounds may be given in either order; NaN axis values are never inside.
    """
    low, high = min(start, end), max(start, end)
    return [i for i, value in enumerate(axis) if low <= value <= high]


def with_row_axis(columns: dict[str, tuple[float, ...]]) -> Scan:
    """Build a scan whose sample axis is the row number 0, 1, 2, ...

    Raises:
        ValueError: if ``columns`` is empty or already has a ``row`` column.
    """
    if not columns:
        raise ValueError('the scan has no numeric columns')
    if ROW_AXIS in columns:
        raise ValueError(f'column {ROW_AXIS!r} already exists')
    count = len(next(iter(columns.values())))
    return Scan(ROW_AXIS, {ROW_AXIS: tuple(float(i) for i in range(count)), **columns})
