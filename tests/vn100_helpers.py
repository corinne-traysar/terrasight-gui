"""Shared by the VN-100 tests: a real captured packet and a wait-until helper."""
import time

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)

# Actual packet captured from the bench sensor; expected field order from UM001.
PACKET = b'$VNYMR,-083.439,+017.941,-014.121,-00.0699,+00.1379,+00.3359,+02.985,+02.457,-08.997,-00.013756,-00.019038,-00.007451*69\r\n'


def eventually(check, timeout=3):
    """Return once ``check()`` is true; fail after ``timeout`` seconds."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        time.sleep(.02)
    raise AssertionError('condition not reached before timeout')
