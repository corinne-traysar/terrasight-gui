import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dashboard import connection


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name) / 'connection.local.json'
        self.patch = patch.object(connection, 'CONFIG', self.config)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        env = patch.dict('os.environ', {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_local_settings_and_environment_override(self):
        self.config.write_text(json.dumps({'pi_url': 'http://pi.example:8000/',
                                           'ssh_target': 'operator@pi.example'}))
        self.assertEqual(connection.load_connection()['pi_url'], 'http://pi.example:8000')
        with patch.dict('os.environ', {'TERRASIGHT_PI_URL': 'https://other.example'}):
            self.assertEqual(connection.load_connection()['pi_url'], 'https://other.example')

    def test_rejects_credentials_and_non_origin_urls(self):
        for url in ('file:///etc/passwd', 'http://user:secret@pi', 'http://pi/path',
                    'http://pi?token=secret', 'http://pi#fragment', 'http://pi:invalid'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                connection.validate_pi_url(url)

    def test_ssh_target_cannot_be_an_option_or_shell_command(self):
        for target in ('-oProxyCommand=bad', 'pi; bad', 'pi$(bad)', 'user@pi@other'):
            with patch.dict('os.environ', {'TERRASIGHT_SSH_TARGET': target}):
                with self.assertRaises(ValueError):
                    connection.load_connection()

    def test_panel_follows_private_origin_without_hardcoded_account(self):
        content = b'{{SSH_COMMAND}} {{SSH_URL}} {{PI_URL}} {{PI_LABEL}}'
        rendered = connection.render_connection_panel(content, 'http://100.64.0.2:8000')
        self.assertIn(b'ssh -t 100.64.0.2', rendered)
        self.assertIn(b'ssh://100.64.0.2', rendered)
        self.assertIn(b'http://100.64.0.2:8000/', rendered)
        self.assertNotIn(b'{{', rendered)
