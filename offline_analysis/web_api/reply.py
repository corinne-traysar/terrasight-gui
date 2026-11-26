"""HTTP replies of the analysis API: a status with a JSON body, written gzip-aware."""
from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Reply:
    """An HTTP status and a JSON-ready body."""

    status: int
    body: Dict[str, Any]

    def encoded(self) -> bytes:
        """The body as compact JSON; NaN and infinities become null."""
        return json.dumps(json_safe(self.body), allow_nan=False, separators=(',', ':')).encode()

    def write(self, handler: Any) -> None:
        """Send this reply on a ``BaseHTTPRequestHandler``, gzip-compressed when accepted."""
        content = self.encoded()
        compressed = 'gzip' in handler.headers.get('Accept-Encoding', '')
        if compressed:
            content = gzip.compress(content, compresslevel=1)
        handler.send_response(self.status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Vary', 'Accept-Encoding')
        if compressed:
            handler.send_header('Content-Encoding', 'gzip')
        handler.send_header('Content-Length', str(len(content)))
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        try:
            handler.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass


def json_safe(value: Any) -> Any:
    """``value`` with every non-finite float replaced by None, recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value
