import os
import pty
import select
import time
import unittest
from ap230 import AP230Reader
from ap230_capture import parse_row


class AP230Tests(unittest.TestCase):
    def test_units_and_incomplete_or_garbled_rows(self):
        self.assertEqual(parse_row(b' A +0.3000 -0.4000 +0.0000 '), [30, -40, 0, 50])
        for line in [b'+0.3000 -0.4000', b'junk +0.3000 -0.4000 +0.0000',
                     b'\x00+0.3000 -0.4000 +0.0000']:
            self.assertIsNone(parse_row(line))

    def test_real_serial_framing_start_and_stop(self):
        master, slave = pty.openpty()
        reader = AP230Reader(os.ttyname(slave))
        try:
            reader.start()
            ready, _, _ = select.select([master], [], [], 3)
            self.assertTrue(ready, 'Reader did not clear the partial command')
            self.assertEqual(os.read(master, 100), b'S\r')
            ready, _, _ = select.select([master], [], [], 3)
            self.assertTrue(ready, 'Reader did not request Auto-Send')
            self.assertEqual(os.read(master, 100), b'A\r')
            os.write(master, b'garbled\r\n A +0.3000 -0.')
            time.sleep(.02)
            os.write(master, b'4000 +0.0000\r\n+0.1000 +0.2000 +0.3000\r\n')
            deadline = time.monotonic()+2
            while reader.snapshot()['count'] < 2 and time.monotonic() < deadline:
                time.sleep(.01)
            data = reader.snapshot()
            self.assertEqual(data['status'], 'live')
            self.assertEqual(data['count'], 2)
            self.assertEqual(data['nonmeasurement_lines'], 1)
            self.assertEqual(data['samples'][0][1:], [30, -40, 0, 50])
            self.assertEqual(data['latest'][1:4], [10,20,30])
            self.assertEqual(reader.stop()['status'], 'stopped')
            self.assertFalse(reader.thread.is_alive())
            self.assertEqual(os.read(master, 100), b'S\r')
        finally:
            reader.stop()
            os.close(master)
            os.close(slave)

    def test_stale_measurements_are_not_live(self):
        reader=AP230Reader()
        class Running:
            def is_alive(self):return True
        reader.thread=Running()
        reader.accept(b'+0.1000 +0.2000 +0.3000',time.time()-5,time.monotonic()-5)
        self.assertEqual(reader.snapshot()['status'],'stale')
