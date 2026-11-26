"""The Calibration view's crop: a sample-axis window plus the channels to keep, and CSV output.

onyx ``ScanData.crop`` keeps the rows with ``start <= axis <= end`` (either
order). Unlike onyx ``select``, which always keeps the IMU angles, the window
keeps exactly the selected channels: deselecting yaw/pitch/roll is how the
user asks for a calibration without the IMU. CSV is onyx's writer (axis
column first, NaN as an empty cell).
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from scans import ScanData
from scans.files.scan_writers import CsvScanWriter


class ScanWindow:
    """A closed window [start, end] on the sample axis and the channels to keep."""

    def __init__(self, start: float, end: float, channels: Sequence[str]):
        """Store the window; ValueError when no channel is chosen."""
        if not channels:
            raise ValueError('select at least one channel to keep')
        self.start, self.end, self.channels = start, end, list(channels)

    def apply(self, data: ScanData) -> ScanData:
        """The rows of ``data`` inside the window with only the axis and the chosen channels.

        Raises:
            ValueError: on an unknown channel or a window without samples.
        """
        cropped = data.crop(self.start, self.end)
        table = cropped.table.take(np.arange(cropped.rows), self.channels)
        return ScanData(table.columns, table.axis, table.metadata)


def csv_text(data: ScanData) -> str:
    """``data`` as CSV text: header, then one line per row (axis first, NaN empty)."""
    return CsvScanWriter().text(data.table)
