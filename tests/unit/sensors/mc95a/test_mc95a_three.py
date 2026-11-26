import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sensors.mc95a import MC95AReader
from mc95a_helpers import FakeHat, wait_for


class MultiHat(FakeHat):
    def __init__(self, address, trace):
        super().__init__()
        self.address=address
        self.trace=trace
    def a_in_clock_config_write(self, source, rate):
        self.trace.append(('clock',self.address,source))
    def a_in_scan_start(self, mask, count, flags):
        self.trace.append(('start',self.address,mask));super().a_in_scan_start(mask,count,flags)
    def a_in_scan_read(self, count, timeout):
        time.sleep(.005)
        return SimpleNamespace(data=[.003]*1024 if self.address==1 else [.001,.002]*1024,
                               hardware_overrun=False,buffer_overrun=False)
    def a_in_scan_stop(self):
        self.trace.append(('stop',self.address));super().a_in_scan_stop()


class ThreeSensorTests(unittest.TestCase):
    def test_shared_clock_routing_and_pause_stops_both_hats(self):
        trace=[]; hats=[MultiHat(i,trace) for i in range(2)]
        module=SimpleNamespace(mcc172=lambda address:hats[address],
            OptionFlags=SimpleNamespace(CONTINUOUS=1),SourceType=SimpleNamespace(LOCAL=0,MASTER=1,SLAVE=2))
        with patch.dict(sys.modules,{'daqhats':module}):
            reader=MC95AReader(third=True);reader.start()
            try:
                wait_for(lambda:reader.snapshot()['sequence']>=2)
                reader.set_paused(True);wait_for(lambda:reader.snapshot()['status']=='paused')
                snap=reader.snapshot();channels=snap['channels']
                self.assertEqual([(c['board_address'],c['board_channel']) for c in channels],[(0,0),(0,1),(1,0)])
                self.assertEqual([round(c['latest']['mean_V'],3) for c in channels],[.001,.002,.003])
                self.assertEqual(trace[:4],[('clock',1,2),('clock',0,1),('start',1,1),('start',0,3)])
                self.assertIn(('stop',0),trace);self.assertIn(('stop',1),trace)
                self.assertIn('unverified',snap['timing'])
                count=snap['samples_per_channel'];time.sleep(.03)
                self.assertEqual(reader.snapshot()['samples_per_channel'],count)
                reader.set_paused(False);wait_for(lambda:reader.snapshot()['samples_per_channel']>count)
                self.assertTrue(all(h.iepe_checks>=4 for h in hats))
            finally:reader.stop()
