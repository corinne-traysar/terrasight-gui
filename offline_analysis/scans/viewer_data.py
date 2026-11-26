"""Read a scan or simulation output as magnetic or electromagnetic vectors in nT.

Any file ``scan_io.parse_scan`` reads works (CSV/TSV/text/JSON), including the
Pi's VN-100 recordings (``magnetic_x_gauss``…) and calibrated CSVs. Rows keep
file order, so the sample index counts from the first row. Axes are labelled
E/N/U when a JSON file declares ``coordinate_frame: east_north_up`` (the bunker
outputs) or the columns use e/n/u names, else x/y/z. The browser rotates the
axis frame and draws the graphs; this module only extracts the vectors.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Sequence

from offline_analysis.magnetic_calibration.calibration_angles import scan_attitude
from offline_analysis.scans.channels import normalize
from offline_analysis.scans.components import Triple, magnetic_triple, phasor_triples, unit_scale_nt
from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_io import is_json_name, parse_scan

ENU = ('E', 'N', 'U')
XYZ = ('x', 'y', 'z')
SENSORS = ('magnetic', 'electromagnetic')
Vector = List[Optional[float]]


def viewer_data(sensor: str, name: str, text: str) -> dict[str, Any]:
    """The sensor's vectors (nT) from the file ``name`` with contents ``text``.

    Magnetic data gives ``field_nt``; electromagnetic data gives the phasor
    parts ``real_nt`` and ``imag_nt``. ``attitude`` holds the scan's yaw/pitch/
    roll in degrees for the angle window, or None. Missing values are None.

    Raises:
        ValueError: on an unknown sensor, or a file without that sensor's columns.
    """
    if sensor not in SENSORS:
        raise ValueError(f'unknown sensor {sensor!r}; choose magnetic or electromagnetic')
    scan = parse_scan(name, text)
    if sensor == 'magnetic':
        triple = magnetic_triple(scan.channels)
        vectors = {'field_nt': _vectors(scan, triple)}
        columns = list(triple)
    else:
        real, imag = phasor_triples(scan.channels)
        triple = real
        vectors = {'real_nt': _vectors(scan, real), 'imag_nt': _vectors(scan, imag)}
        columns = list(real + imag)
    return {'sensor': sensor, 'source': name, 'count': scan.rows, 'columns': columns,
            'labels': list(_labels(name, text, triple)), 'attitude': scan_attitude(scan), **vectors}


def _vectors(scan: Scan, triple: Triple) -> list[Vector]:
    """The triple's columns as nT vectors; a missing component is None."""
    scales = [unit_scale_nt(name) for name in triple]
    columns = [scan.columns[name] for name in triple]
    return [[_finite(columns[k][i] * scales[k]) for k in range(3)] for i in range(scan.rows)]


def _finite(value: float) -> float | None:
    """``value``, or None when it is NaN or infinite (JSON has no NaN)."""
    return value if value == value and abs(value) != float('inf') else None


def _labels(name: str, text: str, triple: Sequence[str]) -> tuple[str, str, str]:
    """E/N/U for an east-north-up file or an east-named first column, else x/y/z."""
    tokens = re.split(r'[_.\- ]+', normalize(triple[0]))
    if 'e' in tokens or 'east' in tokens or _declared_frame(name, text) == 'east_north_up':
        return ENU
    return XYZ


def _declared_frame(name: str, text: str) -> str | None:
    """The ``coordinate_frame`` of a JSON object file, else None."""
    if not is_json_name(name):
        return None
    data = json.loads(text.lstrip('﻿'))
    return data.get('coordinate_frame') if isinstance(data, dict) else None
