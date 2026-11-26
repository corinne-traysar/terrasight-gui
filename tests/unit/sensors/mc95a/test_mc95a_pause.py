"""Tests of sensors/mc95a.py: pausing and resuming acquisition on a fake MCC172 HAT."""
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sensors.mc95a import MC95AReader
from mc95a_helpers import FakeHat, wait_for


class PauseTests(unittest.TestCase):
    def run_reader(self, hat):
        return patch.dict(sys.modules, {'daqhats':SimpleNamespace(mcc172=lambda address:hat,
            OptionFlags=SimpleNamespace(CONTINUOUS=1),SourceType=SimpleNamespace(LOCAL=0))})

    def test_pause_acknowledges_hardware_stop_and_resume_rechecks_iepe(self):
        hat=FakeHat()
        with self.run_reader(hat):
            reader=MC95AReader()
            reader.start()
            try:
                wait_for(lambda:reader.snapshot()['sequence']>=2)
                reader.set_paused(True)
                wait_for(lambda:reader.snapshot()['status']=='paused')
                self.assertEqual(hat.actions[-2:],['stop','cleanup'])
                count=reader.snapshot()['samples_per_channel']
                time.sleep(.04)
                self.assertEqual(reader.snapshot()['samples_per_channel'],count)
                reader.set_paused(False)
                wait_for(lambda:reader.snapshot()['samples_per_channel']>count)
                self.assertGreaterEqual(hat.iepe_checks,4)
                self.assertEqual(hat.actions[:4],['start','stop','cleanup','start'])
            finally: reader.stop()

    def test_failed_stop_never_reports_paused(self):
        hat=FakeHat(fail_stop=True)
        with self.run_reader(hat):
            reader=MC95AReader();reader.start()
            try:
                wait_for(lambda:reader.snapshot()['sequence']>0)
                reader.set_paused(True)
                wait_for(reader.quit.is_set)
                self.assertEqual(reader.snapshot()['status'],'error')
                self.assertIn('Could not stop ADC',reader.snapshot()['error'])
                self.assertFalse(reader.paused.is_set())
            finally: reader.stop()

    def test_start_paused_does_not_start_adc(self):
        hat=FakeHat()
        with self.run_reader(hat):
            reader=MC95AReader();reader.set_paused(True);reader.start()
            try:
                wait_for(lambda:reader.snapshot()['status']=='paused')
                self.assertEqual(hat.actions,[])
                reader.set_paused(False)
                wait_for(lambda:reader.snapshot()['sequence']>0)
                self.assertEqual(hat.actions,['start'])
            finally:reader.stop()
