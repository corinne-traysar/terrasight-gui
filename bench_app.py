"""Unified Terrasight bench dashboard with independent sensor controls."""
import argparse
import gzip
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import socket
from urllib.parse import urlsplit, parse_qs
from connection import render_connection_panel
from app import Handler as VNHandler
from ap230 import AP230Reader, DEFAULT_DEVICE as AP230_DEVICE
from mc95a import MC95AReader
from mc95a_app import display_snapshot
from pi_health import PiHealth
from vn100 import Measurements,VN100Reader

WEB=Path(__file__).parent/'web'
DEFAULT_DEVICE='/dev/serial/by-id/usb-FTDI_USB-RS232-WE_AV0LSPFW-if00-port0'


class BenchMeasurements(Measurements):
    acquisition_running=False
    def snapshot(self,after=0):
        data=super().snapshot(after)
        if not self.acquisition_running:
            data['status']='stopped'
        return data


class VNControl:
    def __init__(self,device,measurements):
        self.device=device;self.measurements=measurements;self.reader=None;self.lock=threading.Lock()
    def start(self):
        with self.lock:
            if self.reader is None:
                self.measurements.acquisition_running=True
                self.reader=VN100Reader(self.device,self.measurements);self.reader.start()
        return {'running':True,'device':self.device}
    def stop(self):
        with self.lock:
            if self.reader is not None:self.reader.stop();self.reader=None
            self.measurements.stop_recording()
            self.measurements.acquisition_running=False
            self.measurements.connection(False,'VN-100 acquisition stopped')
        return {'running':False,'device':self.device}
    def snapshot(self):
        with self.lock:return {'running':self.reader is not None,'device':self.device}


class BenchHandler(VNHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    def __init__(self,*args,mc,health,vn,ap,**kwargs):
        self.mc=mc;self.health=health;self.vn=vn;self.ap=ap
        super().__init__(*args,**kwargs)
    def send_json(self,value,code=200):
        content=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
        compressed='gzip' in self.headers.get('Accept-Encoding','')
        if compressed:content=gzip.compress(content,compresslevel=1)
        self.send_response(code);self.send_header('Content-Type','application/json')
        self.send_header('Vary','Accept-Encoding')
        if compressed:self.send_header('Content-Encoding','gzip')
        self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store')
        self.end_headers()
        try:self.wfile.write(content)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/telemetry':
            try:
                query=parse_qs(urlsplit(self.path).query)
                ap_after=int(query.get('ap_after',['0'])[0])
                if ap_after<0:raise ValueError('Invalid AP230 cursor')
                mc=display_snapshot(self.mc,self.path)
            except ValueError:self.send_error(400,'Invalid telemetry query');return
            self.send_json({'mc':mc,'ap':self.ap.snapshot(after=ap_after),
                            'health':self.health.snapshot(),'vn':self.vn.snapshot(),
                            'sent_at':time.time()});return
        if path=='/api/live':
            try:data=display_snapshot(self.mc,self.path)
            except ValueError:self.send_error(400,'Invalid display query');return
            self.send_json(data | {'thermal_guard_active':self.health.snapshot()['thermal_guard_active']});return
        if path=='/api/health':self.send_json(self.health.snapshot());return
        if path=='/api/ap230':self.send_json(self.ap.snapshot());return
        if path=='/api/bench':
            self.send_json({'health':self.health.snapshot(),'mc95a':{'status':self.mc.snapshot()['status']},
                            'vn100':self.vn.snapshot() | {'status':self.measurements.snapshot()['status']},
                            'ap230':{k:v for k,v in self.ap.snapshot().items() if k not in ('samples','latest')}});return
        files={'/':('bench.html','text/html'),'/bench.js':('bench.js','text/javascript'),
               '/telemetry.js':('telemetry.js','text/javascript'),
               '/mc95a':('mc95a.html','text/html'),'/mc95a.js':('mc95a.js','text/javascript'),
               '/ap230':('ap230.html','text/html'),'/ap230.js':('ap230.js','text/javascript')}
        if path=='/vn100':self.path='/';super().do_GET();return
        if path in files:
            name,mime=files[path];content=(WEB/name).read_bytes()
            if name=='bench.html':content=render_connection_panel(content,'http://'+self.headers.get('Host','localhost:8000'))
            self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8')
            self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(content);return
        super().do_GET()
    def do_POST(self):
        if self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
            self.send_error(403,'Controls require the same GUI origin');return
        if self.path in ('/api/acquisition/resume','/api/vn100/start','/api/ap230/start') and not self.health.can_resume():
            self.send_json({'error':'Thermal guard: wait until the Pi cools below 70 C before resuming.'},409);return
        if self.path=='/api/acquisition/pause':self.send_json(self.mc.set_paused(True));return
        if self.path=='/api/acquisition/resume':self.send_json(self.mc.set_paused(False));return
        if self.path=='/api/vn100/start':self.send_json(self.vn.start());return
        if self.path=='/api/vn100/stop':self.send_json(self.vn.stop());return
        if self.path=='/api/ap230/start':self.send_json(self.ap.start());return
        if self.path=='/api/ap230/stop':self.send_json(self.ap.stop());return
        super().do_POST()


def make_bench_server(host,port,measurements,mc,health,vn,ap=None):
    return ThreadingHTTPServer((host,port),partial(BenchHandler,measurements=measurements,mc=mc,health=health,vn=vn,ap=ap if ap is not None else AP230Reader()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8000)
    p.add_argument('--device',default=DEFAULT_DEVICE);p.add_argument('--third',action='store_true')
    p.add_argument('--ap230-device',default=AP230_DEVICE)
    args=p.parse_args()
    measurements=BenchMeasurements(recording_directory=Path.home()/'terrasight-bench'/'captures')
    measurements.connection(False,'VN-100 acquisition stopped')
    mc=MC95AReader(third=args.third);mc.set_paused(True)
    vn=VNControl(args.device,measurements)
    ap=AP230Reader(args.ap230_device)
    def pause_all():mc.set_paused(True);vn.stop();ap.stop()
    health=PiHealth(on_hot=pause_all)
    server=make_bench_server(args.host,args.port,measurements,mc,health,vn,ap)
    mc.start();health.start()
    print(f'Terrasight Bench: http://mypi.local:{args.port} — acquisition starts stopped',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:print('Stopping unified bench dashboard',flush=True)
    finally:server.server_close();health.stop();mc.stop();vn.stop();ap.stop()


if __name__=='__main__':main()
