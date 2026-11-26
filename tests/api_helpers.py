"""Shared by the analysis API tests: direct POSTs, onyx availability and the preview module."""
import json

from calibration_model import calibration_text  # noqa: F401  (re-exported for the API tests)
from desktop_tools import preview_theme as preview  # noqa: F401  (re-exported for the HTTP tests)
from offline_analysis import web_api

FIT_AVAILABLE, _ = web_api.calibration_support()


def post(path, body):
    """Answer a POST with a JSON body directly (no server)."""
    return web_api.handle('POST', path, json.dumps(body).encode())
