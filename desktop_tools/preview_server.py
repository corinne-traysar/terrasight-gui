"""HTTP server of the local preview: where the Pi is and the shared short-lived API cache."""
import socket
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

# Share recent responses between Overview and an already-open instrument iframe.
# Never extend a response's lifetime on upstream failure or fabricate telemetry.
TTLS = {'/api/live': .2, '/api/ap230': .25, '/api/bench': 1.0, '/api/health': 1.0}


class PreviewServer(ThreadingHTTPServer):
    """Threading server that relays read-only telemetry from the Pi at ``pi_url``."""

    daemon_threads = True

    def __init__(self, address, handler, pi_url: str):
        """Listen on ``address`` with ``handler``; ``pi_url`` is shown and fetched from."""
        super().__init__(address, handler)
        self.pi_url = pi_url
        self.display_pi_url = pi_url
        self.api_cache: dict[str, tuple[float, bytes, str]] = {}
        self.api_locks = {path: threading.Lock() for path in TTLS}

    def resolve_pi_host(self) -> None:
        """Fetch from the Pi's IP address; repeated mDNS lookups can stall each poll.

        The shown address keeps the host name. HTTPS and unresolvable names are left as they are.
        """
        parsed = urlsplit(self.pi_url)
        if parsed.scheme != 'http' or parsed.hostname is None:
            return
        try:
            address = socket.gethostbyname(parsed.hostname)
        except OSError:
            return
        self.pi_url = f'http://{address}:{parsed.port or 80}'
