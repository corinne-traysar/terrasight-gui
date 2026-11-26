"""Unit tests for desktop_tools/connect_pi.py: the ssh command it hands to the OS.

``os.execvp`` is faked, and the settings file is redirected to a temporary folder.
"""
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from dashboard import connection

SCRIPT = Path(__file__).resolve().parents[3] / 'desktop_tools' / 'connect_pi.py'
TMUX = 'tmux new-session -A -s terrasight'


class ConnectPiTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.config = Path(folder.name) / 'connection.local.json'
        for patcher in (patch.object(connection, 'CONFIG', self.config),
                        patch.dict(os.environ), patch.object(sys, 'path', list(sys.path))):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop('TERRASIGHT_PI_URL', None)
        os.environ.pop('TERRASIGHT_SSH_TARGET', None)

    def write_config(self, **settings):
        self.config.write_text(json.dumps(settings))

    def run_script(self, run_name='__main__'):
        """Run connect_pi.py and return the faked execvp mock."""
        with patch('os.execvp') as execvp:
            runpy.run_path(str(SCRIPT), run_name=run_name)
        return execvp

    def test_configured_ssh_target_joins_the_shared_tmux_session(self):
        self.write_config(pi_url='http://pi.example:8000', ssh_target='bench@pi.example')
        self.run_script().assert_called_once_with('ssh', ['ssh', '-t', 'bench@pi.example', TMUX])

    def test_without_ssh_target_the_dashboard_hostname_is_used(self):
        self.write_config(pi_url='http://100.64.0.2:8000')
        self.run_script().assert_called_once_with('ssh', ['ssh', '-t', '100.64.0.2', TMUX])

    def test_without_settings_file_the_lan_default_is_used(self):
        self.run_script().assert_called_once_with('ssh', ['ssh', '-t', 'mypi.local', TMUX])

    def test_environment_target_overrides_the_settings_file(self):
        self.write_config(pi_url='http://pi.example:8000', ssh_target='bench@pi.example')
        os.environ['TERRASIGHT_SSH_TARGET'] = 'other@tailnet-pi'
        self.run_script().assert_called_once_with('ssh', ['ssh', '-t', 'other@tailnet-pi', TMUX])

    def test_unsafe_ssh_target_is_rejected_before_exec(self):
        self.write_config(ssh_target='pi; rm -rf ~')
        with patch('os.execvp') as execvp, self.assertRaisesRegex(ValueError, 'SSH target must be'):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        execvp.assert_not_called()

    def test_importing_the_module_does_not_connect(self):
        self.write_config(ssh_target='bench@pi.example')
        self.run_script(run_name='connect_pi').assert_not_called()


if __name__ == '__main__':
    unittest.main()
