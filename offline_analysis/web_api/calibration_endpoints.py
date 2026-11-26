"""Analysis endpoints that fit and apply an onyx magnetic calibration.

They need numpy and the onyx ``calibration`` package (Python 3.12+), imported
only when a request arrives; ``support`` tells the router whether they can run.
"""
from __future__ import annotations

import sys

from offline_analysis.magnetic_calibration.reference import DEFAULT_REFERENCE_NT, METHODS, MOUNTING_NAMES
from offline_analysis.scans.scan import Scan
from offline_analysis.scans.scan_io import scan_csv
from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.request_fields import RequestFields

MISSING_CALIBRATION = ('Calibration fitting needs numpy and the onyx calibration package '
                       '(Python 3.12+) in the Python that runs this server. Loading, cropping '
                       'and viewing still work.')


class CalibrationEndpoints:
    """GET /api/calibration/status; POST fit, fit-file, apply and /api/offline/calibrate."""

    @staticmethod
    def support() -> tuple[bool, str | None]:
        """(True, None) when numpy and onyx ``calibration`` import, else (False, reason)."""
        try:
            import offline_analysis.magnetic_calibration.calibrated_output  # noqa: F401  (needs numpy + onyx)
        except (ImportError, SyntaxError) as error:
            return False, f'{MISSING_CALIBRATION} ({type(error).__name__}: {error})'
        return True, None

    @classmethod
    def status(cls) -> Reply:
        """Whether fitting is available, why not, and the fitting defaults."""
        available, reason = cls.support()
        return Reply(200, dict(available=available, reason=reason, default_reference_nt=DEFAULT_REFERENCE_NT,
                               methods=list(METHODS), mountings=list(MOUNTING_NAMES),
                               python=sys.version.split()[0]))

    @classmethod
    def fit(cls, fields: RequestFields) -> Reply:
        """Fit the cropped window and selected channels with the requested ``method``."""
        return cls._fit(fields.cropped(), fields, str(fields.get('method', 'auto')))

    @classmethod
    def fit_file(cls, fields: RequestFields) -> Reply:
        """Fit every row of an imported calibration file; its columns choose the method.

        A file with yaw, pitch and roll columns gets the IMU method, one without
        them the ellipsoid method; ``file_rows`` counts the rows before incomplete
        ones are skipped.
        """
        scan = fields.scan()[1]
        reply = cls._fit(scan, fields, 'auto')
        reply.body['file_rows'] = scan.rows
        return reply

    @staticmethod
    def _fit(scan: Scan, fields: RequestFields, method: str) -> Reply:
        """Fit ``scan`` with ``method`` and the request's reference |B| (nT) and mounting."""
        from offline_analysis.magnetic_calibration.calibrated_output import calibration_json, fit_summary
        from offline_analysis.magnetic_calibration.magnetic_calibrator import fit_recording
        from offline_analysis.magnetic_calibration.magnetic_recording import read_recording
        recording = read_recording(scan)
        reference = fields.number('reference_nt', DEFAULT_REFERENCE_NT)
        parameters = fit_recording(recording, method, reference, str(fields.get('mounting', 'enu')))
        return Reply(200, dict(calibration_json=calibration_json(parameters, recording),
                               summary=fit_summary(parameters, recording)))

    @staticmethod
    def apply(fields: RequestFields) -> Reply:
        """Calibrate every row of the file with the given calibration JSON text."""
        from offline_analysis.magnetic_calibration.calibrated_output import (apply_summary, calibrated_scan,
                                                                             parse_calibration)
        from offline_analysis.magnetic_calibration.magnetic_recording import read_recording
        parameters = parse_calibration(fields.text('calibration'))
        recording = read_recording(fields.scan()[1])
        scan = calibrated_scan(parameters, recording)
        return Reply(200, dict(csv=scan_csv(scan), summary=apply_summary(scan, recording)))

    @staticmethod
    def offline_calibrate(fields: RequestFields) -> Reply:
        """Calibrate the Offline Data view's magnetic file; report the calibration's angles."""
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        name, scan = fields.scan()
        return Reply(200, dict(source=name, **offline_calibration(fields.text('calibration'), scan)))
