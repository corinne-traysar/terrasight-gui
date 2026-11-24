import http.client
import json
import threading
import unittest
from bench_app import make_bench_server, VNControl, BenchMeasurements
from mc95a import MC95AReader
from pi_health import PiHealth, decode_throttled
from vn100 import Measurements


class HealthTests(unittest.TestCase):
    def test_guard_hysteresis_and_no_automatic_resume(self):
        calls=[];temperature=[76]
        h=PiHealth(on_hot=lambda:calls.append('paused'),temperature_reader=lambda:temperature[0],throttle_reader=lambda:0)
        h.sample();self.assertFalse(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=73;h.sample();self.assertFalse(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=69;h.sample();self.assertTrue(h.can_resume());self.assertEqual(calls,['paused'])
        temperature[0]=76;h.sample();self.assertEqual(calls,['paused','paused'])

    def test_current_and_historical_throttle_flags_are_distinct(self):
        flags=decode_throttled((1<<2)|(1<<16))
        self.assertTrue(flags['throttled']);self.assertFalse(flags['undervoltage'])
        self.assertTrue(flags['undervoltage_occurred']);self.assertFalse(flags['throttled_occurred'])

    def test_missing_telemetry_is_reported(self):
        def missing():raise OSError('not present')
        h=PiHealth(temperature_reader=missing,throttle_reader=missing);h.sample()
        self.assertIsNone(h.snapshot()['temperature_C']);self.assertIsNone(h.snapshot()['flags'])
        self.assertEqual(len(h.snapshot()['errors']),2)


class UnifiedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.m=BenchMeasurements();self.mc=MC95AReader(third=True);self.mc.set_paused(True)
        self.health=PiHealth(temperature_reader=lambda:60,throttle_reader=lambda:0);self.health.sample()
        self.vn=VNControl('/missing-device',self.m)
        self.server=make_bench_server('127.0.0.1',0,self.m,self.mc,self.health,self.vn)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_port
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.vn.stop()
    def request(self,path,method='GET',headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=2)
        conn.request(method,path,headers=headers or {});r=conn.getresponse();status=r.status;data=r.read();conn.close();return status,data
    def test_all_views_and_apis_share_one_server(self):
        for path,marker in (('/',b'Terrasight Bench'),('/vn100',b'IMU - VN100'),('/mc95a',b'EM - MC95A'),('/bench.js',b'vnControl'),('/ap230',b'Mag - AP230'),('/ap230.js',b'/api/ap230/')):
            status,data=self.request(path);self.assertEqual(status,200);self.assertIn(marker,data)
        status,data=self.request('/api/live');self.assertEqual(status,200);self.assertEqual(len(json.loads(data)['channels']),3)
        status,data=self.request('/api/samples');self.assertEqual(status,200);self.assertEqual(json.loads(data)['received'],0);self.assertEqual(json.loads(data)['status'],'stopped')
        status,data=self.request('/api/bench');self.assertEqual(status,200);self.assertEqual(json.loads(data)['health']['temperature_C'],60)
        self.assertEqual(json.loads(data)['ap230']['status'],'stopped')
        status,data=self.request('/api/ap230');self.assertEqual(status,200);self.assertEqual(json.loads(data)['samples'],[])
    def test_origin_guard_and_thermal_resume_block(self):
        self.assertEqual(self.request('/api/acquisition/resume','POST')[0],403)
        self.health.temperature_reader=lambda:76;self.health.sample()
        headers={'Origin':'http://127.0.0.1:'+str(self.port)}
        self.assertEqual(self.request('/api/acquisition/resume','POST',headers)[0],409)
        self.assertTrue(self.mc.pause_requested.is_set())
        self.assertEqual(self.request('/api/vn100/start','POST',headers)[0],409)
        self.assertEqual(self.request('/api/ap230/start','POST')[0],403)
        self.assertEqual(self.request('/api/ap230/start','POST',headers)[0],409)
        self.assertEqual(self.request('/api/ap230/stop','POST',headers)[0],200)
        self.health.temperature_reader=lambda:69;self.health.sample()
        self.assertEqual(self.request('/api/acquisition/resume','POST',headers)[0],200)
        self.assertFalse(self.mc.pause_requested.is_set())

    def test_combined_telemetry_keeps_live_ap230_independent_of_display_history(self):
        import time
        for _ in range(3):
            self.server.RequestHandlerClass.keywords['ap'].accept(b'+0.1000 +0.2000 +0.3000', time.time(), time.monotonic())
        status,body=self.request('/api/telemetry?after=0&ap_after=2&spectrum_max_hz=0')
        self.assertEqual(status,200)
        data=json.loads(body)
        self.assertEqual(len(data['ap']['samples']),1)
        self.assertEqual(data['ap']['count'],3)
        self.assertEqual(data['ap']['samples_start_count'],3)
        self.assertEqual(len(data['mc']['channels']),3)
        self.assertIn('health',data)
        self.assertIn('vn',data)
        self.assertEqual(self.request('/telemetry.js')[0],200)
