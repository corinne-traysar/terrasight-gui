"""Shared by the API and server tests: direct POSTs, onyx availability, the preview module and page links."""
import json
import re

from calibration_model import calibration_text  # noqa: F401  (re-exported for the API tests)
from dashboard.web_assets import WEB
from desktop_tools import preview_theme as preview  # noqa: F401  (re-exported for the HTTP tests)
from offline_analysis import web_api

FIT_AVAILABLE, _ = web_api.calibration_support()
LOCAL_LINK = re.compile(rb'(?:src|href)="(/[^"]*)"')


def post(path, body):
    """Answer a POST with a JSON body directly (no server)."""
    return web_api.handle('POST', path, json.dumps(body).encode())


def page_links():
    """Every local URL (script, style, image, embedded page) that a page under web/pages refers to."""
    return sorted({link.decode() for page in (WEB / 'pages').glob('*.html')
                   for link in LOCAL_LINK.findall(page.read_bytes())})
