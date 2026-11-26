"""Tests of desktop_tools/preview_server.py: the preview server's Pi address and API cache."""
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch

from desktop_tools import preview_server
from desktop_tools.preview_server import TTLS, PreviewServer


class PreviewServerTests(unittest.TestCase):
    """A server on a free local port; resolve_pi_host is checked with a fake resolver."""

    def setUp(self):
        """A server for http://mypi.local:8000 (nothing is served)."""
        self.server = PreviewServer(('127.0.0.1', 0), BaseHTTPRequestHandler, 'http://mypi.local:8000')

    def tearDown(self):
        """Release the port."""
        self.server.server_close()

    def test_starts_with_an_empty_cache_and_one_lock_per_cached_api(self):
        self.assertEqual(self.server.api_cache, {})
        self.assertEqual(set(self.server.api_locks), set(TTLS))
        self.assertTrue(self.server.daemon_threads)

    def test_resolving_keeps_the_shown_name_and_fetches_by_address(self):
        with patch.object(preview_server.socket, 'gethostbyname', return_value='192.168.1.20') as lookup:
            self.server.resolve_pi_host()
        lookup.assert_called_once_with('mypi.local')
        self.assertEqual(self.server.pi_url, 'http://192.168.1.20:8000')
        self.assertEqual(self.server.display_pi_url, 'http://mypi.local:8000')

    def test_default_port_is_80(self):
        self.server.pi_url = 'http://mypi.local'
        with patch.object(preview_server.socket, 'gethostbyname', return_value='10.0.0.2'):
            self.server.resolve_pi_host()
        self.assertEqual(self.server.pi_url, 'http://10.0.0.2:80')

    def test_unresolvable_or_https_hosts_are_left_unchanged(self):
        with patch.object(preview_server.socket, 'gethostbyname', side_effect=OSError('no such host')):
            self.server.resolve_pi_host()
        self.assertEqual(self.server.pi_url, 'http://mypi.local:8000')
        self.server.pi_url = 'https://mypi.local'
        with patch.object(preview_server.socket, 'gethostbyname') as lookup:
            self.server.resolve_pi_host()
        lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
