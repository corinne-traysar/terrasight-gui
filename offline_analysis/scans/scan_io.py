"""Read scans from delimited text or JSON, and write cropped scans as CSV.

The dashboard sends file contents rather than paths, so ``parse_scan`` and
``scan_csv`` work on text; ``load_scan`` and ``save_scan`` wrap them for files.
Reading is done by ``scan_readers`` (text or JSON, chosen by the file name);
columns that are neither numbers nor ISO-8601 times are skipped, and ISO times
become seconds since the first row.
"""
from __future__ import annotations

import csv
import io
import math
from pathlib import Path

from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_readers import ScanReader


def is_json_name(name: str) -> bool:
    """True when the file name ends in ``.json`` (any case)."""
    return Path(name).suffix.lower() == '.json'


def parse_scan(name: str, text: str) -> Scan:
    """Parse the contents of the file ``name`` (``.json`` or delimited text) as a scan.

    Raises:
        ValueError: if the file has no rows or no numeric column, or is invalid JSON.
    """
    return ScanReader.for_name(name).read(text)


def load_scan(path: Path) -> Scan:
    """Load ``path`` (``.json`` or delimited text) as a scan with a sample axis.

    Raises:
        ValueError: if the file has no rows or no numeric column.
    """
    return parse_scan(Path(path).name, Path(path).read_text(encoding='utf-8-sig'))


def scan_csv(scan: Scan) -> str:
    """The scan as CSV text: header, then one line per row (axis column first, NaN empty)."""
    handle = io.StringIO(newline='')
    writer = csv.writer(handle, lineterminator='\n')
    names = [scan.axis] + scan.channels
    writer.writerow(names)
    writer.writerows(zip(*(_cells(scan.columns[n]) for n in names)))
    return handle.getvalue()


def save_scan(scan: Scan, path: Path, overwrite: bool = False) -> None:
    """Write ``scan`` as CSV (axis column first); an existing file is kept unless ``overwrite``.

    Raises:
        FileExistsError: if ``path`` exists and ``overwrite`` is false.
    """
    with Path(path).open('w' if overwrite else 'x', newline='', encoding='utf-8') as handle:
        handle.write(scan_csv(scan))


def _cells(values: tuple[float, ...]) -> list[str]:
    """Format floats for CSV, writing NaN as an empty cell."""
    return ['' if math.isnan(v) else repr(v) for v in values]
