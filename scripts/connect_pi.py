#!/usr/bin/env python3
"""Open the existing shared Pi session using local connection settings."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connection import load_connection, ssh_target

if __name__ == '__main__':
    settings = load_connection()
    os.execvp('ssh', ['ssh', '-t', ssh_target(settings['pi_url'], settings),
                      'tmux new-session -A -s terrasight'])
