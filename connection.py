"""Local-only Pi connection settings; never contains authentication secrets."""
import html
import json
import os
from pathlib import Path
import re
import shlex
from urllib.parse import urlsplit

CONFIG = Path(__file__).parent / 'connection.local.json'


def validate_pi_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise ValueError('Pi URL must be an HTTP(S) origin without credentials or a path.')
    parsed.port  # Validate the port before starting a server.
    return value.rstrip('/')


def load_connection():
    settings = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    settings['pi_url'] = validate_pi_url(os.environ.get(
        'TERRASIGHT_PI_URL', settings.get('pi_url', 'http://mypi.local:8000')))
    target = os.environ.get('TERRASIGHT_SSH_TARGET', settings.get('ssh_target'))
    if target and (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:\[\]-]*', target)
                   or target.count('@') > 1):
        raise ValueError('SSH target must be a hostname or user@hostname.')
    settings['ssh_target'] = target
    return settings


def ssh_target(pi_url, settings):
    return settings.get('ssh_target') or urlsplit(pi_url).hostname


def render_connection_panel(content, pi_url):
    pi_url = validate_pi_url(pi_url)
    target = ssh_target(pi_url, load_connection())
    command = shlex.join(['ssh', '-t', target, 'tmux new-session -A -s terrasight'])
    values = {'SSH_COMMAND': command, 'SSH_URL': 'ssh://' + target,
              'PI_URL': pi_url + '/', 'PI_LABEL': urlsplit(pi_url).netloc}
    for key, value in values.items():
        content = content.replace(('{{' + key + '}}').encode(), html.escape(value).encode())
    return content
