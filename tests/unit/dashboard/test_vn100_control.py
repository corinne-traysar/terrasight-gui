"""Unit tests for dashboard/vn100_control.py: the bench's VN-100 start/stop control.

The serial reader is replaced by a fake, so no port is opened.
"""
import unittest
from unittest import mock

import posix_stubs  # noqa: F401  (lets sensors.vn100 import on Windows)
from dashboard import vn100_control
from dashboard.vn100_control import BenchMeasurements, VNControl


class FakeReader:
    """Records start/stop calls in place of VN100Reader."""

    instances = []

    def __init__(self, device, measurements):
        self.device, self.measurements = device, measurements
        self.started = self.stopped = 0
        FakeReader.instances.append(self)

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


class BenchMeasurementsTests(unittest.TestCase):
    def test_status_is_stopped_while_acquisition_is_off(self):
        self.assertEqual(BenchMeasurements().snapshot()['status'], 'stopped')

    def test_status_is_the_reader_state_while_acquisition_runs(self):
        measurements = BenchMeasurements()
        measurements.acquisition_running = True
        # No port opened yet: the underlying Measurements reports disconnected.
        self.assertEqual(measurements.snapshot()['status'], 'disconnected')

    def test_snapshot_keeps_samples_after_the_cursor(self):
        measurements = BenchMeasurements()
        measurements.add({'magnetic': [0.1, 0.2, 0.3]})
        measurements.add({'magnetic': [0.4, 0.5, 0.6]})
        self.assertEqual([s['sequence'] for s in measurements.snapshot(after=1)['samples']], [2])


class VNControlTests(unittest.TestCase):
    def setUp(self):
        FakeReader.instances = []
        patcher = mock.patch.object(vn100_control, 'VN100Reader', FakeReader)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.measurements = BenchMeasurements()
        self.control = VNControl('/dev/fake-vn100', self.measurements)

    def test_start_opens_one_reader_on_the_device(self):
        self.assertEqual(self.control.start(), {'running': True, 'device': '/dev/fake-vn100'})
        self.assertEqual(len(FakeReader.instances), 1)
        self.assertEqual(FakeReader.instances[0].device, '/dev/fake-vn100')
        self.assertEqual(FakeReader.instances[0].started, 1)
        self.assertTrue(self.measurements.acquisition_running)

    def test_start_twice_keeps_the_first_reader(self):
        self.control.start()
        self.control.start()
        self.assertEqual(len(FakeReader.instances), 1)

    def test_stop_stops_the_reader_and_marks_measurements_stopped(self):
        self.control.start()
        self.assertEqual(self.control.stop(), {'running': False, 'device': '/dev/fake-vn100'})
        self.assertEqual(FakeReader.instances[0].stopped, 1)
        snapshot = self.measurements.snapshot()
        self.assertEqual((snapshot['status'], snapshot['error']), ('stopped', 'VN-100 acquisition stopped'))

    def test_stop_without_a_reader_is_safe(self):
        self.assertEqual(self.control.stop()['running'], False)
        self.assertEqual(FakeReader.instances, [])

    def test_stop_ends_an_active_recording(self):
        with mock.patch.object(self.measurements, 'stop_recording') as stop_recording:
            self.control.stop()
        stop_recording.assert_called_once_with()

    def test_snapshot_reports_whether_the_reader_runs(self):
        self.assertFalse(self.control.snapshot()['running'])
        self.control.start()
        self.assertEqual(self.control.snapshot(), {'running': True, 'device': '/dev/fake-vn100'})


if __name__ == '__main__':
    unittest.main()
