"""Route analysis API requests to their endpoints and turn failures into JSON errors."""
from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import urlsplit

from offline_analysis.web_api.calibration_endpoints import CalibrationEndpoints
from offline_analysis.web_api.reply import Reply
from offline_analysis.web_api.request_fields import RequestFields
from offline_analysis.web_api.scan_endpoints import ScanEndpoints

MAX_BODY_BYTES = 64 * 1024 * 1024
STATUS_PATH = '/api/calibration/status'
POST_ROUTES: dict[str, Callable[[RequestFields], Reply]] = {
    '/api/scan/load': ScanEndpoints.load, '/api/scan/crop': ScanEndpoints.crop,
    '/api/offline/load': ScanEndpoints.offline, '/api/calibration/fit': CalibrationEndpoints.fit,
    '/api/calibration/fit-file': CalibrationEndpoints.fit_file, '/api/calibration/apply': CalibrationEndpoints.apply,
    '/api/offline/calibrate': CalibrationEndpoints.offline_calibrate}
NEEDS_CALIBRATION = frozenset(('/api/calibration/fit', '/api/calibration/fit-file', '/api/calibration/apply',
                               '/api/offline/calibrate'))


class WebApiRouter:
    """Answers the analysis API; client mistakes give 400 and missing onyx gives 503."""

    def handles(self, method: str, raw_path: str) -> bool:
        """True when this API answers ``method`` on the request path ``raw_path``."""
        path = urlsplit(raw_path).path
        return path == STATUS_PATH if method == 'GET' else method == 'POST' and path in POST_ROUTES

    def handle(self, method: str, raw_path: str, body: bytes = b'') -> Reply:
        """Answer one request with its body ``body`` (UTF-8 JSON for POST)."""
        path = urlsplit(raw_path).path
        if method == 'GET' and path == STATUS_PATH:
            return CalibrationEndpoints.status()
        route = POST_ROUTES.get(path) if method == 'POST' else None
        if route is None:
            return Reply(404, {'error': 'Not found'})
        if path in NEEDS_CALIBRATION:
            available, reason = CalibrationEndpoints.support()
            if not available:
                return Reply(503, {'error': reason})
        return self._run(route, body)

    @staticmethod
    def _run(route: Callable[[RequestFields], Reply], body: bytes) -> Reply:
        """Decode ``body`` and run ``route``; every failure becomes a JSON error reply."""
        try:
            request = json.loads(body.decode('utf-8'))
            if not isinstance(request, dict):
                raise ValueError('the request body must be a JSON object')
            return route(RequestFields(request))
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            return Reply(400, {'error': str(error) or type(error).__name__})
        except Exception as error:  # noqa: BLE001  (report, never drop the connection)
            return Reply(500, {'error': f'{type(error).__name__}: {error}'})

    def serve(self, handler: Any) -> None:
        """Read the request of a ``BaseHTTPRequestHandler``, answer it and write the reply."""
        body = b''
        if handler.command == 'POST':
            length = self._content_length(handler)
            if not 0 <= length <= MAX_BODY_BYTES:
                Reply(413, {'error': f'Files up to {MAX_BODY_BYTES // 2**20} MB are accepted.'}).write(handler)
                return
            body = handler.rfile.read(length)
        self.handle(handler.command, handler.path, body).write(handler)

    @staticmethod
    def _content_length(handler: Any) -> int:
        """The request's Content-Length, or -1 when it is not an integer."""
        try:
            return int(handler.headers.get('Content-Length', '0'))
        except ValueError:
            return -1
