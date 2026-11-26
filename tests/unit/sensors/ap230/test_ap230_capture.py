"""Tests of sensors/ap230_capture.py: the command line (row parsing is in test_ap230_serial)."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from sensors import ap230_capture


class ReExportTests(unittest.TestCase):
    """Older imports of parse_row from ap230_capture keep working."""

    def test_parse_row_is_re_exported(self):
        self.assertEqual(ap230_capture.parse_row(b'+0.0100 +0.0000 +0.0000'), [1.0, 0.0, 0.0, 1.0])


class CommandLineTests(unittest.TestCase):
    """parse_args limits and main's exit status from the capture summary."""

    def test_seconds_outside_0_to_3600_are_rejected(self):
        for seconds in ('0', '-1', '3600.5'):
            with self.subTest(seconds=seconds), patch('sys.stderr'), self.assertRaises(SystemExit):
                ap230_capture.parse_args(['--port', '/dev/x', '--seconds', seconds])
        self.assertEqual(ap230_capture.parse_args(['--port', '/dev/x', '--seconds', '3600']).seconds, 3600)

    def run_main(self, summary):
        """Run main with a fake capture returning ``summary``; return the capture folder."""
        with tempfile.TemporaryDirectory() as folder, patch('builtins.print'), \
                patch.object(ap230_capture, 'AP230Capture') as capture:
            capture.return_value.run.return_value = summary
            try:
                ap230_capture.main(['--port', '/dev/x', '--seconds', '1', '--output', folder])
            finally:
                created = [p.name for p in Path(folder).iterdir()]
        self.assertEqual(len(created), 1, 'one new UTC-stamped folder')
        self.assertEqual(capture.call_args.args[:2], ('/dev/x', 1.0))
        return created[0]

    def test_successful_capture_exits_normally(self):
        name = self.run_main({'error': None, 'samples': 3})
        self.assertRegex(name, r'^\d{8}T\d{6}_\d{6}Z$')

    def test_error_or_no_readings_exit_1(self):
        for summary in ({'error': 'OSError: gone', 'samples': 3}, {'error': None, 'samples': 0}):
            with self.subTest(summary=summary), self.assertRaises(SystemExit) as exit_:
                self.run_main(summary)
            self.assertEqual(exit_.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
