"""Browser exports reopen through the real analysis endpoints, including CSV crops."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from offline_analysis.web_api.router import WebApiRouter
from offline_analysis.web_api.calibration_endpoints import CalibrationEndpoints

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('node') and CalibrationEndpoints.support()[0], 'Node and onyx required')
class SensorRecordingImportTest(unittest.TestCase):
    """Cross-language contracts between downloaded JSON, scans, cropping and plots."""

    @classmethod
    def setUpClass(cls):
        """Create exported files with the real browser capture model under Node."""
        script = "process.stdout.write(JSON.stringify(require('./tests/browser/live/recording_data.cjs')))"
        cls.files = json.loads(subprocess.check_output(['node', '-e', script], cwd=ROOT, text=True))

    def post(self, route, fields):
        """Call the same router used by the preview and Pi servers."""
        reply = WebApiRouter().handle('POST', route, json.dumps(fields).encode())
        self.assertEqual(reply.status, 200, reply.body)
        return reply.body

    def test_ap230_opens_for_calibration_and_offline(self):
        """AP230 uT becomes nT, and the joined IMU angles are recognized."""
        fields = {'name': 'ap230.json', 'text': json.dumps(self.files['ap'])}
        scan = self.post('/api/scan/load', fields)
        self.assertIn('magnetic_x_uT', scan['profiles']['magnetic']['b_axes'])
        self.assertIn('yaw_deg', scan['profiles']['magnetic']['imu'])
        result = self.post('/api/offline/load', dict(fields, sensor='magnetic'))
        self.assertEqual(result['field_nt'][0], [3000, 4000, 12000])
        self.assertEqual(result['attitude']['degrees'][0], [30, 5, -2])

    def test_mc95a_opens_and_crop_reopens_as_scalar(self):
        """MC95A raw voltage and RMS field load without manufacturing AC phase."""
        fields = {'name': 'mc95a.json', 'text': json.dumps(self.files['mc'])}
        loaded = self.post('/api/scan/load', fields)
        self.assertIn('mc95a_s1_field_rms_nT', loaded['profiles']['electromagnetic']['b_axes'])
        result = self.post('/api/offline/load', dict(fields, sensor='electromagnetic'))
        self.assertEqual(result['scalar_traces'][0]['values'], [20])
        self.assertTrue(any(g['unit'] == 'V ADC' for g in result['scalar_traces']))
        self.assertNotIn('real_nt', result)
        crop = self.post('/api/scan/crop', dict(fields, start=5, end=5, channels=loaded['channels']))
        reopened = self.post('/api/offline/load', dict(name='crop.csv', text=crop['csv'], sensor='electromagnetic'))
        self.assertEqual(reopened['scalar_traces'][0]['values'], [20])
