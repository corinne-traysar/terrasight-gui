"""A scan or simulation output as magnetic or electromagnetic vectors in nT, for the Offline Data view.

The file is read as onyx ``MagneticScan`` (``field_t``) or
``ElectromagneticScan`` (``real_t``/``imaginary_t``), which find the columns
and convert their units to tesla; this module sends them in nT. Rows keep
file order. Axes are labelled E/N/U when the scan is an onyx-calibrated one,
a JSON file declares ``coordinate_frame: east_north_up`` (the bunker outputs)
or the first field column has an east name, else x/y/z. The browser rotates
the axis frame and draws the graphs.
"""
from __future__ import annotations

import json
from typing import Any

from calibration.arrays import FloatArray
from scans import ElectromagneticScan, MagneticScan, Scan
from scans.columns.channels import tokens

from offline_analysis.scans.attitude_record import AttitudeRecord, finite_list
from offline_analysis.scans.scan_loader import LOADER

ENU = ('E', 'N', 'U')
XYZ = ('x', 'y', 'z')
NANOTESLA = 1e-9


def viewer_data(sensor: str, name: str, text: str) -> dict[str, Any]:
    """The sensor's vectors (nT) from the file ``name`` with contents ``text``.

    Magnetic data gives ``field_nt``; electromagnetic data gives the phasor
    parts ``real_nt`` and ``imag_nt``. ``attitude`` holds the scan's yaw/pitch/
    roll in degrees for the angle window, or None. Missing values are None.

    Raises:
        ValueError: on an unknown sensor, or a file without that sensor's columns.
    """
    if sensor == 'electromagnetic':
        from offline_analysis.scans.recorded_channels import RecordedChannels
        recording = RecordedChannels.viewer(LOADER.data(name, text), name, text)
        if recording is not None:
            return recording
    scan = LOADER.sensor_scan(sensor, name, text)
    return dict(sensor=sensor, source=name, count=scan.rows, columns=list(scan.sensor_columns),
                labels=list(labels(scan, name, text)), attitude=AttitudeRecord.of_scan(scan),
                **vectors_nt(scan))


def vectors_nt(scan: Scan) -> dict[str, list[list[Any]]]:
    """``field_nt`` of a magnetic scan, or ``real_nt`` and ``imag_nt`` of an electromagnetic one."""
    if isinstance(scan, MagneticScan):
        return {'field_nt': _nt(scan.field_t)}
    if isinstance(scan, ElectromagneticScan):
        return {'real_nt': _nt(scan.real_t), 'imag_nt': _nt(scan.imaginary_t)}
    raise TypeError(f'no Offline Data vectors for {type(scan).__name__}')


def labels(scan: Scan, name: str, text: str) -> tuple[str, str, str]:
    """E/N/U for a calibrated or east/north/up scan, else x/y/z."""
    first = set(tokens(scan.sensor_columns[0]))
    if scan.is_calibrated or {'e', 'east'} & first or _declared_frame(name, text) == 'east_north_up':
        return ENU
    return XYZ


def _nt(vectors_t: FloatArray) -> list[list[Any]]:
    """(N, 3) tesla vectors as nT lists; a missing component is None."""
    return [finite_list(row) for row in vectors_t / NANOTESLA]


def _declared_frame(name: str, text: str) -> str | None:
    """The ``coordinate_frame`` of a JSON object file, else None."""
    if not name.lower().endswith('.json'):
        return None
    data = json.loads(text.lstrip('﻿'))
    return data.get('coordinate_frame') if isinstance(data, dict) else None
