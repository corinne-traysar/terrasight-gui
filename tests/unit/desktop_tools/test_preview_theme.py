"""Tests of desktop_tools/preview_theme.py: the preview's command line and start-up."""
import unittest
from unittest.mock import patch

from desktop_tools import preview_theme


class PreviewThemeTests(unittest.TestCase):
    """parse_args defaults and main's server lifecycle (with a fake server)."""

    def test_defaults_come_from_the_connection_settings(self):
        with patch.object(preview_theme, 'load_connection', return_value={'pi_url': 'http://pi.example:8000'}):
            args = preview_theme.parse_args([])
        self.assertEqual((args.port, args.pi_url), (8766, 'http://pi.example:8000'))

    def test_main_serves_until_ctrl_c_and_closes(self):
        with patch.object(preview_theme, 'PreviewServer') as server, patch('builtins.print'):
            server.return_value.serve_forever.side_effect = KeyboardInterrupt
            preview_theme.main(['--port', '9000', '--pi-url', 'http://mypi.local:8000'])
        address, handler, pi_url = server.call_args.args
        self.assertEqual((address, handler, pi_url), (('127.0.0.1', 9000), preview_theme.Preview, 'http://mypi.local:8000'))
        server.return_value.resolve_pi_host.assert_called_once()
        server.return_value.server_close.assert_called_once()

    def test_unsafe_pi_url_is_refused_before_serving(self):
        with patch.object(preview_theme, 'PreviewServer') as server, self.assertRaises(ValueError):
            preview_theme.main(['--pi-url', 'file:///etc/passwd'])
        server.assert_not_called()


if __name__ == '__main__':
    unittest.main()
