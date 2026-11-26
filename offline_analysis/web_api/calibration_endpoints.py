"""Analysis endpoints that fit and apply an onyx magnetic calibration, and the onyx status.

Every analysis endpoint needs numpy, scipy and the onyx ``scans``,
``calibration`` and ``navigation`` packages (Python 3.12+). They are imported
only when a request arrives; ``support`` tells the router whether they can run.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from offline_analysis.magnetic_calibration.reference import DEFAULT_REFERENCE_NT, METHODS, MOUNTING_NAMES
from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.request_fields import RequestFields

if TYPE_CHECKING:
    from scans import MagneticScan

MISSING_ONYX = ('The Calibration and Offline Data views need numpy, scipy and the onyx scans, calibration '
                'and navigation packages (Python 3.12+) in the Python that runs this server. Install an '
                'onyx-demo-sims checkout there (see the README, "Calibration and Offline Data").')


class CalibrationEndpoints:
    """GET /api/calibration/status; POST fit, fit-file, apply and /api/offline/calibrate."""

    @staticmethod
    def support() -> tuple[bool, str | None]:
        """(True, None) when numpy and onyx import, else (False, reason)."""
        try:
            import offline_analysis.magnetic_calibration.calibrated_output  # noqa: F401  (needs numpy + onyx)
            import offline_analysis.scans.viewer_data  # noqa: F401  (onyx scans + navigation)
        except (ImportError, SyntaxError) as error:
            return False, f'{MISSING_ONYX} ({type(error).__name__}: {error})'
        return True, None

    @classmethod
    def status(cls) -> Reply:
        """Whether the onyx analysis is available, why not, and the fitting defaults."""
        available, reason = cls.support()
        return Reply(200, dict(available=available, reason=reason, default_reference_nt=DEFAULT_REFERENCE_NT,
                               methods=list(METHODS), mountings=list(MOUNTING_NAMES),
                               python=sys.version.split()[0]))

    @classmethod
    def fit(cls, fields: RequestFields) -> Reply:
        """Fit the cropped window and selected channels with the requested ``method``."""
        from offline_analysis.scans.scan_loader import ScanLoader
        scan = ScanLoader.magnetic(fields.cropped())
        return cls._fit(scan, fields, str(fields.get('method', 'auto')))

    @classmethod
    def fit_file(cls, fields: RequestFields) -> Reply:
        """Fit every row of an imported calibration file; its columns choose the method.

        A file with yaw, pitch and roll (its own, or derived from a raw IMU) gets
        the IMU method, one without them the ellipsoid method; ``file_rows``
        counts the rows before incomplete ones are skipped.
        """
        scan = fields.magnetic()
        reply = cls._fit(scan, fields, 'auto')
        reply.body['file_rows'] = scan.rows
        return reply

    @staticmethod
    def _fit(scan: MagneticScan, fields: RequestFields, method: str) -> Reply:
        """Fit ``scan`` with ``method`` and the request's reference |B| (nT) and mounting."""
        from offline_analysis.magnetic_calibration.calibrated_output import fit_summary
        from offline_analysis.magnetic_calibration.calibration_document import CalibrationDocument
        from offline_analysis.magnetic_calibration.magnetic_calibrator import MagneticCalibrator
        calibrator = MagneticCalibrator(method, fields.number('reference_nt', DEFAULT_REFERENCE_NT),
                                        str(fields.get('mounting', 'enu')))
        calibration = calibrator.fit(scan)
        return Reply(200, dict(calibration_json=CalibrationDocument.text(calibration, scan),
                               summary=fit_summary(calibration, scan)))

    @staticmethod
    def apply(fields: RequestFields) -> Reply:
        """Calibrate every row of the file with the given calibration JSON text."""
        from offline_analysis.magnetic_calibration.calibrated_output import CalibratedOutput
        from offline_analysis.magnetic_calibration.calibration_document import CalibrationDocument
        calibration = CalibrationDocument.parse(fields.text('calibration'))
        output = CalibratedOutput(fields.magnetic(), calibration)
        return Reply(200, dict(csv=output.csv(), summary=output.summary()))

    @staticmethod
    def offline_calibrate(fields: RequestFields) -> Reply:
        """Calibrate the Offline Data view's magnetic file; report the calibration's angles."""
        from offline_analysis.magnetic_calibration.calibrated_output import offline_calibration
        calibration = fields.text('calibration')
        return Reply(200, dict(source=fields.text('name'), **offline_calibration(calibration, fields.magnetic())))
