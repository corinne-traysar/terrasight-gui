"""Tests of dashboard/bench_app.py: building the bench server and starting every instrument stopped."""
import sys
import unittest
from unittest.mock import MagicMock, patch

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from dashboard import bench_app


class MakeBenchServerTests(unittest.TestCase):
    """make_bench_server: the handler gets every instrument; AP230 defaults to an unstarted reader."""

    def test_handler_receives_the_instruments(self):
        with patch.object(bench_app, 'ThreadingHTTPServer') as server, \
                patch.object(bench_app, 'AP230Reader') as ap230:
            bench_app.make_bench_server('127.0.0.1', 0, 'measurements', 'mc', 'health', 'vn')
        address, handler = server.call_args.args
        self.assertEqual(address, ('127.0.0.1', 0))
        self.assertEqual(handler.keywords, dict(measurements='measurements', mc='mc', health='health', vn='vn',
                                                ap=ap230.return_value))
        ap230.return_value.start.assert_not_called()


class MainTests(unittest.TestCase):
    """main: instruments start paused/stopped, and Ctrl+C stops all of them."""

    def run_main(self, argv):
        """Run main with fake instruments; return the mocks by name."""
        mocks = {name: MagicMock() for name in ('MC95AReader', 'VNControl', 'AP230Reader', 'PiHealth',
                                                 'BenchMeasurements', 'make_bench_server')}
        mocks['make_bench_server'].return_value.serve_forever.side_effect = KeyboardInterrupt
        with patch.object(sys, 'argv', ['bench_app.py', *argv]), patch('builtins.print'), \
                patch.multiple(bench_app, **mocks):
            bench_app.main()
        return mocks

    def test_everything_starts_stopped_and_is_stopped_on_exit(self):
        mocks = self.run_main(['--port', '8123', '--third'])
        mc, vn, ap = (mocks[n].return_value for n in ('MC95AReader', 'VNControl', 'AP230Reader'))
        mocks['MC95AReader'].assert_called_once_with(third=True)
        mc.set_paused.assert_called_with(True)
        mocks['BenchMeasurements'].return_value.connection.assert_called_once_with(False, 'VN-100 acquisition stopped')
        self.assertEqual(mocks['make_bench_server'].call_args.args[:2], ('0.0.0.0', 8123))
        for instrument in (mc, vn, ap, mocks['PiHealth'].return_value):
            instrument.stop.assert_called_once()
        mocks['make_bench_server'].return_value.server_close.assert_called_once()

    def test_hot_pi_pauses_every_instrument(self):
        mocks = self.run_main([])
        mc, vn, ap = (mocks[n].return_value for n in ('MC95AReader', 'VNControl', 'AP230Reader'))
        on_hot = mocks['PiHealth'].call_args.kwargs['on_hot']
        for instrument in (mc, vn, ap):
            instrument.reset_mock()
        on_hot()
        mc.set_paused.assert_called_once_with(True)
        vn.stop.assert_called_once()
        ap.stop.assert_called_once()

    def test_devices_come_from_the_command_line(self):
        mocks = self.run_main(['--device', '/dev/vn', '--ap230-device', '/dev/ap'])
        self.assertEqual(mocks['VNControl'].call_args.args[0], '/dev/vn')
        mocks['AP230Reader'].assert_called_once_with('/dev/ap')


if __name__ == '__main__':
    unittest.main()
