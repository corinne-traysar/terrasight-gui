"""Typed access to the fields of one analysis API request (a decoded JSON object).

Every accessor raises ValueError with the field name when the value has the
wrong type, so the router can answer the client with 400 and a clear message.
"""
from __future__ import annotations

import math
from typing import Any

from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_io import parse_scan


class RequestFields:
    """The fields of one request body: text, finite numbers, the scan and its crop."""

    def __init__(self, request: dict[str, Any]):
        """Wrap the decoded JSON object ``request``."""
        self.request = request

    def get(self, key: str, default: Any = None) -> Any:
        """The raw value of ``key`` (``default`` when absent)."""
        return self.request.get(key, default)

    def text(self, key: str) -> str:
        """The string field ``key``."""
        value = self.request.get(key)
        if not isinstance(value, str):
            raise ValueError(f'{key} must be text')
        return value

    def number(self, key: str, default: Any = None) -> float:
        """The field ``key`` as a finite float (``default`` when absent)."""
        return finite_number(self.request.get(key, default), key)

    def scan(self) -> tuple[str, Scan]:
        """The file name and its parsed scan (``name`` and ``text`` fields)."""
        name = self.text('name')
        return name, parse_scan(name, self.text('text'))

    def cropped(self) -> Scan:
        """The scan cropped to [``start``, ``end``] and the selected ``channels``."""
        channels = self.request.get('channels')
        if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
            raise ValueError('channels must be a list of column names')
        return self.scan()[1].crop(self.number('start'), self.number('end'), channels)


def finite_number(value: Any, key: str) -> float:
    """``value`` as a finite float; booleans and non-numbers raise ValueError naming ``key``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{key} must be a finite number')
    return float(value)


def clean(values: Any) -> list[float | None]:
    """Floats for JSON: NaN and infinities become None."""
    return [v if math.isfinite(v) else None for v in values]
