"""Calibration documents, calibrated scans and short JSON summaries of fits, in nT.

Needs numpy and the onyx ``calibration`` package. A calibration document is the
onyx ``onyx-vector-calibration/1`` JSON that ``calibration.save_parameters``
writes. A calibrated scan holds the sample axis of the kept rows plus
``B_east_nT``, ``B_north_nT``, ``B_up_nT`` and ``B_total_nT``; the Calibration
and Offline Data views read it back as a magnetic east/north/up scan, and
``offline_calibration`` gives the Offline Data view the same rows as vectors.
"""
from __future__ import annotations

import json

import numpy as np
from calibration import VectorCalibrationParameters
from calibration.vector.parameter_storage import FORMAT

from offline_analysis.magnetic_calibration.calibration_angles import ATTITUDE_KEY, calibration_angles, recording_attitude
from offline_analysis.magnetic_calibration.magnetic_calibrator import calibrated_enu_nt
from offline_analysis.magnetic_calibration.magnetic_recording import NT_TO_T, MagneticRecording, read_recording
from offline_analysis.scans.scan import Scan

ENU_COLUMNS = ('B_east_nT', 'B_north_nT', 'B_up_nT')
TOTAL_COLUMN = 'B_total_nT'


def calibration_json(parameters: VectorCalibrationParameters,
                     recording: MagneticRecording | None = None) -> str:
    """``parameters`` as the text ``calibration.save_parameters`` would write.

    With a ``recording`` that has attitude, the document also carries the
    yaw/pitch/roll (degrees) of every fitted row under ``calibration_attitude``
    for the Offline Data angle window; onyx ignores the extra key.
    """
    document = {'format': FORMAT, **parameters.to_dict()}
    if recording is not None and recording.attitude_rad is not None and recording.attitude_columns:
        document[ATTITUDE_KEY] = recording_attitude(recording.axis, recording.axis_values.tolist(),
                                                    recording.attitude_rad.tolist(), recording.attitude_columns)
    return json.dumps(document, indent=2) + '\n'


def parse_calibration(text: str) -> VectorCalibrationParameters:
    """Parameters from calibration JSON text (as ``calibration.load_parameters`` reads).

    Raises:
        ValueError: on invalid JSON, a wrong format tag or missing fields.
    """
    document = json.loads(text)
    if not isinstance(document, dict) or document.get('format') != FORMAT:
        raise ValueError(f'the calibration file is not a {FORMAT} calibration')
    try:
        return VectorCalibrationParameters.from_dict(document)
    except (KeyError, TypeError) as error:
        raise ValueError(f'the calibration file is incomplete: {error}') from error


def calibrated_scan(parameters: VectorCalibrationParameters, recording: MagneticRecording) -> Scan:
    """The recording's rows calibrated with ``parameters``, as east/north/up nT columns."""
    enu = calibrated_enu_nt(parameters, recording)
    columns = {recording.axis: tuple(recording.axis_values.tolist())}
    columns.update({name: tuple(enu[:, k].tolist()) for k, name in enumerate(ENU_COLUMNS)})
    columns[TOTAL_COLUMN] = tuple(np.linalg.norm(enu, axis=1).tolist())
    return Scan(recording.axis, columns)


def fit_summary(parameters: VectorCalibrationParameters,
                recording: MagneticRecording) -> dict[str, object]:
    """Method, rows, columns used, offset, residual and Earth field (nT) of a fit."""
    earth = parameters.earth_field_enu_t
    return dict(method=parameters.method, rows=recording.count,
                b_columns=list(recording.field_columns),
                attitude_columns=list(recording.attitude_columns or []),
                reference_nt=parameters.reference_magnitude_t / NT_TO_T,
                offset_nt=_nt(parameters.offset_t),
                residual_rms_nt=parameters.residual_rms_t / NT_TO_T,
                earth_field_enu_nt=None if earth is None else _nt(earth))


def apply_summary(scan: Scan, recording: MagneticRecording) -> dict[str, object]:
    """Rows, whether attitude was used, and the mean and spread of calibrated |B| (nT)."""
    total = np.asarray(scan.columns[TOTAL_COLUMN])
    return dict(rows=scan.rows, attitude_used=recording.has_attitude,
                b_total_mean_nt=float(total.mean()), b_total_std_nt=float(total.std()))


def offline_calibration(text: str, scan: Scan) -> dict[str, object]:
    """Calibrate ``scan`` with the calibration JSON ``text`` for the Offline Data view.

    Returns the kept rows' calibrated east/north/up vectors (nT), the apply
    summary, the B columns read and the calibration's angles.

    Raises:
        ValueError: on a bad calibration or a scan without a complete B row.
    """
    parameters = parse_calibration(text)
    angles = calibration_angles(json.loads(text))
    recording = read_recording(scan)
    calibrated = calibrated_scan(parameters, recording)
    field = [[calibrated.columns[name][i] for name in ENU_COLUMNS] for i in range(calibrated.rows)]
    return dict(count=calibrated.rows, labels=['E', 'N', 'U'], field_nt=field,
                b_columns=list(recording.field_columns),
                summary=apply_summary(calibrated, recording), calibration=angles)


def _nt(vector_t: np.ndarray) -> list[float]:
    """A tesla vector as a list of nT values."""
    return [float(v) / NT_TO_T for v in vector_t]
