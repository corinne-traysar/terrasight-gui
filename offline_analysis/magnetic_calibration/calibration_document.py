"""An onyx calibration as the JSON text the browser downloads and opens again.

The text is onyx's ``onyx-vector-calibration/1`` document (what
``VectorCalibration.save`` writes). A document fitted on a scan with attitude
also carries ``calibration_attitude``: the yaw/pitch/roll (degrees) of every
fitted row, for the Offline Data angle window; onyx ignores the extra key.
Parsing restores the onyx calibration class named by the document's method.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from calibration import EllipsoidCalibration, ImuCalibration, VectorCalibration, VectorCalibrationParameters
from calibration.vector.parameter_storage import FORMAT
from scans import MagneticScan
from scans.enu_rows import complete_rows

from offline_analysis.scans.attitude_record import AttitudeRecord

ATTITUDE_KEY = 'calibration_attitude'
CLASSES: dict[str, type[VectorCalibration]] = {'ellipsoid': EllipsoidCalibration, 'imu': ImuCalibration}


class CalibrationDocument:
    """Writes and reads calibration JSON text."""

    @staticmethod
    def text(calibration: VectorCalibration, scan: Optional[MagneticScan] = None) -> str:
        """The fitted ``calibration`` as indented JSON, with the fitted rows' attitude when ``scan`` has it."""
        document: dict[str, Any] = {'format': FORMAT, **calibration.parameters.to_dict()}
        if scan is not None and scan.attitude_columns is not None:
            rows = complete_rows([scan.field_t], scan.attitude_rad)
            document[ATTITUDE_KEY] = AttitudeRecord.of_scan(scan, rows)
        return json.dumps(document, indent=2, allow_nan=False) + '\n'

    @staticmethod
    def parse(text: str) -> VectorCalibration:
        """The fitted onyx calibration stored in ``text``.

        Raises:
            ValueError: on invalid JSON, a wrong format tag, an unknown method or missing fields.
        """
        document = json.loads(text)
        if not isinstance(document, dict) or document.get('format') != FORMAT:
            raise ValueError(f'the calibration file is not a {FORMAT} calibration')
        try:
            parameters = VectorCalibrationParameters.from_dict(document)
        except (KeyError, TypeError) as error:
            raise ValueError(f'the calibration file is incomplete: {error}') from error
        if parameters.method not in CLASSES:
            raise ValueError(f'unknown calibration method {parameters.method!r}')
        calibration = CLASSES[parameters.method](parameters.reference_magnitude_t)
        calibration.restore(parameters)
        return calibration
