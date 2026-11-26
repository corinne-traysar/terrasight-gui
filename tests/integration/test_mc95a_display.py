import gzip
import json
import math

from integration import test_bench_app_server as bench_server


class DisplayTransferTests(bench_server.UnifiedHTTPTests):
    def test_incremental_display_preserves_measurements_and_limits_transfer(self):
        for block in range(610):
            values = [math.sin(2 * math.pi * 50 * (i + block * 1024) / 10240) * .001
                      for i in range(1024)]
            self.mc.publish([values] * 3, 10240)
        full = self.mc.snapshot()
        status, body = self.request('/api/live?after=609&spectrum_max_hz=500')
        self.assertEqual(status, 200)
        slim = json.loads(body)
        self.assertLess(len(body), 200000)
        for original, channel in zip(full['channels'], slim['channels']):
            self.assertEqual(channel['latest'], original['latest'])
            self.assertEqual(len(channel['history']), 1)
            self.assertEqual(channel['history'][0]['sequence'], 610)
            self.assertEqual(channel['history_start_sequence'], 11)
            self.assertEqual(channel['spectrum']['band_rms_V'], original['spectrum']['band_rms_V'])
            self.assertEqual(channel['spectrum']['peak_Hz'], original['spectrum']['peak_Hz'])
            self.assertLessEqual(max(channel['spectrum']['frequency_Hz']), 501.25)
        _, compressed = self.request('/api/live?after=609&spectrum_max_hz=500',
                                     headers={'Accept-Encoding': 'gzip'})
        self.assertEqual(json.loads(gzip.decompress(compressed))['sequence'], 610)
        self.assertLess(len(compressed), 50000)

    def test_invalid_display_query_returns_bad_request(self):
        for query in ('after=no', 'spectrum_max_hz=nan', 'spectrum_max_hz=-1'):
            self.assertEqual(self.request('/api/live?' + query)[0], 400)
