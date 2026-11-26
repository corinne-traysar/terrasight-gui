"""Integration: the unified bench server with a real MC95A reader and Pi health, over HTTP.
"""
import http.client
import json
import threading
import unittest

import posix_stubs  # noqa: F401  (lets the serial sensor modules import on Windows)
from dashboard.bench_app import make_bench_server, VNControl, BenchMeasurements
from sensors.mc95a import MC95AReader
from dashboard.pi_health import PiHealth


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
    def test_calibration_and_offline_views_share_the_server(self):
        for path,marker in (('/calibration',b'Fit Magnetic Calibration'),('/calibration.js',b'/api/scan/load'),('/offline',b'Offline Data'),('/offline.js',b'/api/offline/load'),('/scan-plot.js',b'envelope'),('/',b'data-src="/offline"'),('/angles',b'Calibration and Scan Angles'),('/angles.js',b'terrasight-angles'),('/offline-calibration.js',b'/api/offline/calibrate')):
            status,data=self.request(path);self.assertEqual(status,200);self.assertIn(marker,data)
        status,data=self.request('/api/calibration/status');self.assertEqual(status,200);self.assertIn('available',json.loads(data))
        body=json.dumps({'name':'scan.csv','text':'t,Bx,By,Bz\n0,1,2,3\n1,4,5,6\n'})
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=2)
        conn.request('POST','/api/scan/load',body=body,headers={'Origin':'http://127.0.0.1:'+str(self.port)})
        r=conn.getresponse();self.assertEqual(r.status,200);self.assertEqual(json.loads(r.read())['profiles']['magnetic']['b_axes'],['Bx','By','Bz']);conn.close()
        self.assertEqual(self.request('/api/scan/load','POST')[0],403)
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

if __name__ == '__main__':
    unittest.main()
