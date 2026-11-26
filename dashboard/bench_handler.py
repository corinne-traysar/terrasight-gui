"""HTTP handler of the unified bench dashboard: pages, telemetry and instrument controls.

GET serves the file-analysis APIs, the combined telemetry feed, instrument status
and the dashboard pages; anything else falls through to the VN-100 handler (its
page, stream and recording). POST runs same-origin start/stop controls, refused
while the Pi health guard keeps acquisition stopped.
"""
import gzip
import json
import time
import socket
from urllib.parse import urlsplit, parse_qs

from offline_analysis import web_api
from dashboard.connection import render_connection_panel
from dashboard.vn100_app import Handler as VNHandler
from dashboard.mc95a_app import display_snapshot
from dashboard.web_assets import ASSETS, WEB  # noqa: F401  (WEB: the web root, re-exported)

JS='text/javascript'
PAGES={'/':('bench.html','text/html'),'/bench.js':('bench.js',JS),'/telemetry.js':('telemetry.js',JS),
       '/mc95a':('mc95a.html','text/html'),'/mc95a.js':('mc95a.js',JS),
       '/ap230':('ap230.html','text/html'),'/ap230.js':('ap230.js',JS),
       '/calibration':('calibration.html','text/html'),'/calibration.js':('calibration.js',JS),
       '/calibration-plot.js':('calibration-plot.js',JS),'/calibration-fit.js':('calibration-fit.js',JS),
       '/offline':('offline.html','text/html'),'/offline.js':('offline.js',JS),
       '/offline-calibration.js':('offline-calibration.js',JS),
       '/angles':('angles.html','text/html'),'/angles.js':('angles.js',JS),'/scan-plot.js':('scan-plot.js',JS)}
RESUME_PATHS=('/api/acquisition/resume','/api/vn100/start','/api/ap230/start')


class BenchHandler(VNHandler):
    """HTTP handler of the bench dashboard; VN-100 pages and recording fall through to VNHandler."""

    protocol_version='HTTP/1.1'

    def setup(self):
        """Disable Nagle's algorithm so small telemetry replies leave immediately."""
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)

    def __init__(self,*args,mc,health,vn,ap,**kwargs):
        """Serve the MC95A reader ``mc``, Pi ``health``, VN-100 control ``vn`` and AP230 reader ``ap``."""
        self.mc=mc;self.health=health;self.vn=vn;self.ap=ap
        super().__init__(*args,**kwargs)

    def send_json(self,value,code=200):
        """Send ``value`` as JSON, gzip-compressed when the client accepts it."""
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
        """Answer file-analysis and telemetry APIs, then dashboard pages, then VN-100 files."""
        path=urlsplit(self.path).path
        if web_api.handles('GET',self.path):web_api.serve(self);return
        route=self._get_routes().get(path)
        if route is not None:route();return
        if path=='/vn100':self.path='/'
        elif path in PAGES:self._send_page(*PAGES[path]);return
        super().do_GET()

    def _get_routes(self):
        """GET API paths mapped to the methods that answer them."""
        return {'/api/telemetry':self._send_telemetry,'/api/live':self._send_live,
                '/api/health':lambda:self.send_json(self.health.snapshot()),
                '/api/ap230':lambda:self.send_json(self.ap.snapshot()),
                '/api/bench':lambda:self.send_json(self._bench_status())}

    def _send_telemetry(self):
        """One combined MC95A, AP230, Pi health and VN-100 update (query cursors select new data)."""
        try:
            ap_after=int(parse_qs(urlsplit(self.path).query).get('ap_after',['0'])[0])
            if ap_after<0:raise ValueError('Invalid AP230 cursor')
            mc=display_snapshot(self.mc,self.path)
        except ValueError:self.send_error(400,'Invalid telemetry query');return
        self.send_json({'mc':mc,'ap':self.ap.snapshot(after=ap_after),
                        'health':self.health.snapshot(),'vn':self.vn.snapshot(),'sent_at':time.time()})

    def _send_live(self):
        """The MC95A display snapshot plus whether the thermal guard is active."""
        try:data=display_snapshot(self.mc,self.path)
        except ValueError:self.send_error(400,'Invalid display query');return
        self.send_json(data|{'thermal_guard_active':self.health.snapshot()['thermal_guard_active']})

    def _bench_status(self):
        """Status of every instrument and the Pi, without sample data."""
        return {'health':self.health.snapshot(),'mc95a':{'status':self.mc.snapshot()['status']},
                'vn100':self.vn.snapshot()|{'status':self.measurements.snapshot()['status']},
                'ap230':{k:v for k,v in self.ap.snapshot().items() if k not in ('samples','latest')}}

    def _send_page(self,name,mime):
        """Send the web file ``name``; the Overview gets this host's connection panel."""
        content=ASSETS.read(name)
        if name=='bench.html':content=render_connection_panel(content,'http://'+self.headers.get('Host','localhost:8000'))
        self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(content)

    def do_POST(self):
        """Run same-origin controls; resuming is refused while the Pi is too hot."""
        if self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
            self.send_error(403,'Controls require the same GUI origin');return
        if web_api.handles('POST',self.path):web_api.serve(self);return
        if self.path in RESUME_PATHS and not self.health.can_resume():
            self.send_json({'error':'Thermal guard: wait until the Pi cools below 70 C before resuming.'},409);return
        action=self._control_routes().get(self.path)
        if action is None:super().do_POST();return
        self.send_json(action())

    def _control_routes(self):
        """POST control paths mapped to the instrument actions they run."""
        return {'/api/acquisition/pause':lambda:self.mc.set_paused(True),
                '/api/acquisition/resume':lambda:self.mc.set_paused(False),
                '/api/vn100/start':self.vn.start,'/api/vn100/stop':self.vn.stop,
                '/api/ap230/start':self.ap.start,'/api/ap230/stop':self.ap.stop}

