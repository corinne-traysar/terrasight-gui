"""JSON endpoints behind the dashboard's Calibration and Offline Data views.

The browser sends the chosen file's name and text with every request, so the
server keeps no state and never reads or writes files of its own.

GET  /api/calibration/status   whether fitting is available here, and defaults
POST /api/scan/load            {name, text} -> columns, pre-selected channels and
                               the yaw/pitch/roll columns (derived from a raw IMU
                               when the file has no angles)
POST /api/scan/crop            {name, text, start, end, channels} -> cropped CSV
POST /api/calibration/fit      {... crop fields, method, reference_nt, mounting}
                               -> onyx calibration JSON and a summary in nT
POST /api/calibration/fit-file {name, text, reference_nt, mounting} -> the same for
                               every row of an imported calibration file; the
                               method follows its columns (imu with yaw/pitch/roll,
                               else ellipsoid)
POST /api/calibration/apply    {name, text, calibration} -> calibrated CSV and summary
POST /api/offline/load         {sensor, name, text} -> B vectors in nT and the
                               scan's yaw/pitch/roll in degrees
POST /api/offline/calibrate    {name, text, calibration} -> calibrated B east/north/
                               up vectors in nT and the calibration's angles

Every POST works on the onyx ``scans``, ``calibration`` and ``navigation``
packages (numpy, scipy, Python 3.12+); without them they answer 503 with the
reason, and the status endpoint says so. This package itself imports without
them, so the Pi dashboard starts either way. Callers check the request origin
before handing a POST to ``serve``.

``router`` dispatches, ``scan_endpoints`` and ``calibration_endpoints`` answer,
``request_fields`` validates the JSON body and ``reply`` writes the response.
The module-level ``handles``, ``handle`` and ``serve`` use one shared router.
"""
from offline_analysis.magnetic_calibration.reference import DEFAULT_REFERENCE_NT
from offline_analysis.web_api.calibration_endpoints import MISSING_ONYX, CalibrationEndpoints
from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.router import MAX_BODY_BYTES, NEEDS_ONYX, POST_ROUTES, STATUS_PATH, WebApiRouter

ROUTER = WebApiRouter()
handles = ROUTER.handles
handle = ROUTER.handle
serve = ROUTER.serve
calibration_support = CalibrationEndpoints.support

__all__ = ['DEFAULT_REFERENCE_NT', 'MAX_BODY_BYTES', 'MISSING_ONYX', 'NEEDS_ONYX', 'POST_ROUTES',
           'ROUTER', 'STATUS_PATH', 'CalibrationEndpoints', 'Reply', 'WebApiRouter', 'calibration_support',
           'handle', 'handles', 'serve']
