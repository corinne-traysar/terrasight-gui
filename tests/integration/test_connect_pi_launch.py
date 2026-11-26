"""Integration tests for desktop_tools/connect_pi.py run in a fresh interpreter.

The script runs by path from a temporary folder with ``python -I``, so it must find
the ``dashboard`` package through its own bootstrap. Only ``os.execvp`` is replaced,
to print the command instead of opening ssh. Environment variables pin the Pi
settings so a developer's own connection.local.json cannot change the result.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'desktop_tools' / 'connect_pi.py'
RUNNER = ('import json, os, runpy, sys\n'
          'def show(file, args):\n'
          '    print(json.dumps([file, args]))\n'
          '    sys.exit(0)\n'
          'os.execvp = show\n'
          'runpy.run_path(sys.argv[1], run_name="__main__")\n')


def launch(**environment):
    """Run the script with the given TERRASIGHT_* variables; return the CompletedProcess."""
    env = {key: value for key, value in os.environ.items() if not key.startswith('TERRASIGHT_')}
    env.update(environment)
    with tempfile.TemporaryDirectory() as folder:
        return subprocess.run([sys.executable, '-I', '-c', RUNNER, str(SCRIPT)], cwd=folder, env=env,
                              capture_output=True, text=True, timeout=30)


class ConnectPiLaunchTests(unittest.TestCase):
    def test_settings_from_environment_produce_the_tmux_ssh_command(self):
        result = launch(TERRASIGHT_PI_URL='http://pi.example:8000', TERRASIGHT_SSH_TARGET='bench@pi.example')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         ['ssh', ['ssh', '-t', 'bench@pi.example', 'tmux new-session -A -s terrasight']])

    def test_invalid_pi_url_stops_before_ssh(self):
        result = launch(TERRASIGHT_PI_URL='ftp://pi.example', TERRASIGHT_SSH_TARGET='bench@pi.example')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('Pi URL must be an HTTP(S) origin', result.stderr)


if __name__ == '__main__':
    unittest.main()
