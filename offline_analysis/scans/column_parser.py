"""Turn the string columns of a scan file into numeric columns.

A column becomes floats when every non-empty cell is a number, else seconds
since its first time when every non-empty cell is an ISO-8601 time; any other
column is dropped. Empty cells (``''``, ``None``, ``null``) become NaN.
"""
from __future__ import annotations

import math
from datetime import datetime

EMPTY_CELLS = frozenset(('', 'None', 'null'))


class ColumnParser:
    """Numeric conversion of header-named string columns."""

    def numeric_columns(self, table: dict[str, list[str]]) -> dict[str, tuple[float, ...]]:
        """Every column of ``table`` that converts, in file order.

        Raises:
            ValueError: if no column converts.
        """
        out = {name: values for name, cells in table.items() if (values := self.convert(cells))}
        if not out:
            raise ValueError('the scan has no numeric columns')
        return out

    def convert(self, cells: list[str]) -> tuple[float, ...] | None:
        """Cells as floats, else as ISO-8601 seconds from the first time; None when neither (or all empty)."""
        if all(c in EMPTY_CELLS for c in cells):
            return None
        for parse in (self.floats, self.iso_seconds):
            try:
                return parse(cells)
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def floats(cells: list[str]) -> tuple[float, ...]:
        """Every cell as a float; empty cells become NaN. Raises ValueError for any other text."""
        return tuple(math.nan if c in EMPTY_CELLS else float(c) for c in cells)

    @staticmethod
    def iso_seconds(cells: list[str]) -> tuple[float, ...]:
        """ISO-8601 times as seconds after the first one; empty cells become NaN.

        Raises:
            ValueError: for a cell that is not an ISO-8601 time.
            TypeError: when zone-aware and naive times are mixed.
        """
        times = [None if c in EMPTY_CELLS else datetime.fromisoformat(c.replace('Z', '+00:00')) for c in cells]
        origin = next(t for t in times if t is not None)
        return tuple(math.nan if t is None else (t - origin).total_seconds() for t in times)
