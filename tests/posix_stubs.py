"""Let the serial-port sensor modules import on Windows for tests that never open a port.

``sensors/vn100.py`` and ``sensors/ap230.py`` import ``fcntl`` and ``termios`` at
module level but use them only inside their serial-port functions. On Windows
these POSIX modules do not exist, so ``install()`` registers empty stand-ins
(with ``termios.error`` = ``OSError``) before those imports. On Linux and macOS
the real modules are present and nothing is changed. Tests that open a serial
port still need a POSIX machine.
"""
import sys
import types


def install():
    """Register stand-in ``fcntl`` and ``termios`` modules where the real ones are missing."""
    for name in ('fcntl', 'termios'):
        try:
            __import__(name)
        except ImportError:
            stand_in = types.ModuleType(name)
            setattr(stand_in, 'error', OSError)  # the readers catch termios.error alongside OSError
            sys.modules[name] = stand_in


install()
