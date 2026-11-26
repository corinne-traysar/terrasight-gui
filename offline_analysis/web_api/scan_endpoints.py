"""Analysis endpoints that load, crop and view scans with onyx ``scans``.

onyx is imported when a request arrives, so the router imports this module
on a server without it (where these routes answer 503).
"""
from __future__ import annotations

from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.request_fields import RequestFields, clean


class ScanEndpoints:
    """POST /api/scan/load, /api/scan/crop and /api/offline/load."""

    @staticmethod
    def load(fields: RequestFields) -> Reply:
        """Every numeric column, each sensor profile's B-axis and IMU picks, and the
        yaw/pitch/roll columns (with factors to degrees, and how they were derived
        from a raw IMU) when the file has them."""
        from offline_analysis.scans.attitude_record import AttitudeRecord
        from offline_analysis.scans.channel_profiles import PROFILES
        name, data = fields.scan()
        profiles = {key: {'b_axes': list(chosen.b_axes), 'imu': list(chosen.imu)}
                    for key, chosen in ((k, p.select(data.channels)) for k, p in PROFILES.items())}
        return Reply(200, dict(name=name, axis=data.axis, rows=data.rows, channels=data.channels,
                               axis_values=clean(data.axis_values),
                               columns={n: clean(data.column(n)) for n in data.channels},
                               profiles=profiles, attitude=AttitudeRecord.factors(data)))

    @staticmethod
    def crop(fields: RequestFields) -> Reply:
        """The window and selected channels of the file as CSV (axis column first)."""
        from offline_analysis.scans.scan_window import csv_text
        cropped = fields.cropped()
        return Reply(200, dict(csv=csv_text(cropped), rows=cropped.rows, channels=len(cropped.channels)))

    @staticmethod
    def offline(fields: RequestFields) -> Reply:
        """The magnetic field or electromagnetic phasor vectors of the file, in nT."""
        from offline_analysis.scans.viewer_data import viewer_data
        return Reply(200, viewer_data(fields.text('sensor'), fields.text('name'), fields.text('text')))
