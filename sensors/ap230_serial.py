"""AP230 serial protocol: the ASCII row format (gauss) and the 9600 baud 8N1 port setup.

Rows look like ``A +0.3000 -0.4000 +0.0000`` (optional A/D prefix, X Y Z in gauss);
``parse_row`` returns microtesla. Shared by ``ap230`` (dashboard reader) and
``ap230_capture_session`` (finite capture).
"""
import fcntl
import math
import re
import termios

ROW = re.compile(rb'\s*(?:[AD]\s+)?([+-]\d+\.\d{4}) +([+-]\d+\.\d{4}) +([+-]\d+\.\d{4})\s*')


def parse_row(line):
    """[x, y, z, |B|] in microtesla from one ASCII row in gauss, or None when it is not a reading."""
    match = ROW.fullmatch(line)
    if match is None:
        return None
    xyz = [float(value) * 100 for value in match.groups()]  # Gauss to microtesla.
    return [*xyz, math.sqrt(sum(value * value for value in xyz))]


def configure_port(fd):
    """Take ``fd`` exclusively as raw 9600 8N1 with non-blocking reads; return its old settings."""
    fcntl.ioctl(fd, termios.TIOCEXCL)
    old = termios.tcgetattr(fd)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[4] = attrs[5] = termios.B9600
    attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return old
