"""Analysis endpoints that need only the standard library: load, crop and view scans."""
from __future__ import annotations

import math

from offline_analysis.scans.attitude_columns import angle_scale, attitude_columns
from offline_analysis.scans.channels import PROFILES
from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_io import scan_csv
from offline_analysis.scans.viewer_data import viewer_data
from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.request_fields import RequestFields, clean


class ScanEndpoints:
    """POST /api/scan/load, /api/scan/crop and /api/offline/load."""

    @staticmethod
    def load(fields: RequestFields) -> Reply:
        """Every numeric column, each sensor profile's B-axis and IMU picks, and the
        yaw/pitch/roll columns (with factors to degrees) when the file has all three."""
        name, scan = fields.scan()
        profiles = {key: {'b_axes': list(chosen.b_axes), 'imu': list(chosen.imu)}
                    for key, chosen in ((k, p.select(scan.channels)) for k, p in PROFILES.items())}
        return Reply(200, dict(name=name, axis=scan.axis, rows=scan.rows, channels=scan.channels,
                               axis_values=clean(scan.axis_values),
                               columns={n: clean(scan.columns[n]) for n in scan.channels},
                               profiles=profiles, attitude=ScanEndpoints.attitude(scan)))

    @staticmethod
    def attitude(scan: Scan) -> dict | None:
        """The yaw/pitch/roll column names and their factors to degrees, or None."""
        angles = attitude_columns(scan.channels)
        if angles is None:
            return None
        return dict(columns=list(angles),
                    to_degrees=[angle_scale(n, scan.columns[n]) * 180 / math.pi for n in angles])

    @staticmethod
    def crop(fields: RequestFields) -> Reply:
        """The window and selected channels of the file as CSV (axis column first)."""
        cropped = fields.cropped()
        return Reply(200, dict(csv=scan_csv(cropped), rows=cropped.rows, channels=len(cropped.channels)))

    @staticmethod
    def offline(fields: RequestFields) -> Reply:
        """The magnetic field or electromagnetic phasor vectors of the file, in nT."""
        return Reply(200, viewer_data(fields.text('sensor'), fields.text('name'), fields.text('text')))
