"""Fake MCC172 boards and a fake ``daqhats`` module for MC95A tests without hardware.

Signals are functions of the sample index ``n`` returning volts, sampled at
``RATE_HZ``, so tests can derive expected RMS and spectra by hand.
"""
import math
import time
from types import SimpleNamespace

RATE_HZ = 10240.0  # The MCC172 rate MC95AReader requests and the fake clock reports.


def tone(amplitude_v, frequency_hz):
    """A sine of ``amplitude_v`` peak volts at ``frequency_hz``, phase 0 at n = 0."""
    return lambda n: amplitude_v * math.sin(2 * math.pi * frequency_hz * n / RATE_HZ)


def constant(volts):
    """A DC level of ``volts``."""
    return lambda n: volts


class SignalHat:
    """One fake MCC172 board whose selected channels return continuous signals.

    ``signals`` maps board channel -> signal. Scan blocks interleave the
    channels in ascending order (ch0, ch1, ch0, ch1, ...) as daqhats does, and
    the sample index carries over between blocks so tones stay phase-continuous.
    """

    def __init__(self, signals, overrun=False):
        self.signals = signals
        self.overrun = overrun
        self.next_sample = 0
        self.actions = []

    def iepe_config_write(self, channel, value):
        assert value == 0, 'IEPE must stay off'

    def iepe_config_read(self, channel):
        return 0

    def a_in_sensitivity_write(self, channel, value):
        pass

    def a_in_clock_config_write(self, source, rate):
        pass

    def a_in_clock_config_read(self):
        return 0, RATE_HZ, True

    def a_in_scan_start(self, mask, count, flags):
        self.actions.append('start')

    def a_in_scan_read(self, count, timeout):
        time.sleep(.002)
        indices = range(self.next_sample, self.next_sample + count)
        data = [self.signals[ch](n) for n in indices for ch in sorted(self.signals)]
        self.next_sample += count
        return SimpleNamespace(data=data, hardware_overrun=self.overrun, buffer_overrun=False)

    def a_in_scan_stop(self):
        self.actions.append('stop')

    def a_in_scan_cleanup(self):
        self.actions.append('cleanup')


def fake_daqhats(hats):
    """A stand-in ``daqhats`` module whose ``mcc172(address)`` returns ``hats[address]``."""
    return SimpleNamespace(mcc172=lambda address: hats[address],
                           OptionFlags=SimpleNamespace(CONTINUOUS=1),
                           SourceType=SimpleNamespace(LOCAL=0, MASTER=1, SLAVE=2))


def wait_for(predicate):
    """Return once ``predicate()`` is true; fail after 2 s."""
    deadline = time.monotonic()+2
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('Timed out waiting for acquisition state')
        time.sleep(.005)


class FakeHat:
    """A fake MCC172 board returning a fixed 1 mV / 2 mV pattern; records start/stop/cleanup."""

    def __init__(self, fail_stop=False):
        self.actions = []
        self.fail_stop = fail_stop
        self.iepe_checks = 0
    def iepe_config_write(self, ch, value):
        assert value == 0
    def iepe_config_read(self, ch):
        self.iepe_checks += 1
        return 0
    def a_in_sensitivity_write(self, ch, value): pass
    def a_in_clock_config_write(self, source, rate): pass
    def a_in_clock_config_read(self): return 0, 10240, True
    def a_in_scan_start(self, mask, count, flags): self.actions.append('start')
    def a_in_scan_read(self, count, timeout):
        time.sleep(.005)
        return SimpleNamespace(data=[.001,.002]*1024,hardware_overrun=False,buffer_overrun=False)
    def a_in_scan_stop(self):
        self.actions.append('stop')
        if self.fail_stop: raise OSError('stop failed')
    def a_in_scan_cleanup(self): self.actions.append('cleanup')
