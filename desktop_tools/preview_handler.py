"""HTTP handler of the local preview: this checkout's pages with read-only Pi telemetry.

Pages and scripts come from the local ``web/`` tree, file analysis runs locally
(``offline_analysis.web_api``), read-only Pi APIs are relayed (briefly cached so
several open views share one Pi request) and every acquisition control is refused.
"""
import gzip
from http.server import BaseHTTPRequestHandler
import threading
import time
from typing import cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen, Request

from dashboard.connection import render_connection_panel
from dashboard.web_assets import ASSETS
from desktop_tools.preview_server import TTLS, PreviewServer
from offline_analysis import web_api

ROUTES = {'/':'bench.html','/vn100':'index.html','/mc95a':'mc95a.html','/ap230':'ap230.html',
          '/calibration':'calibration.html','/offline':'offline.html','/angles':'angles.html'}
READ_APIS = {'/api/bench','/api/health','/api/live','/api/ap230','/api/samples','/api/events','/api/telemetry'}
PREVIEW_LABEL = b'Local Preview / Live Data / Controls Read-Only'


class Preview(BaseHTTPRequestHandler):
    """Local preview handler: web files from this checkout, telemetry read from the Pi."""

    protocol_version='HTTP/1.1'

    @property
    def preview(self) -> PreviewServer:
        """The serving PreviewServer (Pi address, API cache and its locks)."""
        return cast(PreviewServer, self.server)

    def send_content(self,content,mime,status=200):
        """Send ``content`` uncached with ``status``."""
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)

    def do_GET(self):
        """Answer a GET; a browser that hangs up mid-reply is ignored."""
        try: self.read_get()
        except (BrokenPipeError, ConnectionResetError): pass

    def read_get(self):
        """Run file analysis locally, relay read-only Pi APIs, else serve a web file."""
        path=urlsplit(self.path).path
        # File analysis runs here, on this computer's files; it never reaches the Pi.
        if web_api.handles('GET',self.path):web_api.serve(self);return
        if path=='/api/events':self._relay_events()
        elif path in READ_APIS:self._relay_api(path)
        else:self._send_file(ROUTES.get(path,path.lstrip('/')))

    def _relay_events(self):
        """Pass the Pi's VN-100 event stream through until either side closes it."""
        try:
            with urlopen(self.preview.pi_url+self.path,timeout=4) as response:
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store');self.end_headers()
                while True:
                    chunk=response.read1(16384)
                    if not chunk:break
                    self.wfile.write(chunk);self.wfile.flush()
        except (URLError,TimeoutError,OSError): pass

    def _relay_api(self,path):
        """Send the Pi's reply to this read-only API, cached for its TTL; 502 when unreachable."""
        try:
            with self.preview.api_locks.get(path,threading.Lock()):
                cached=self.preview.api_cache.get(self.path)
                if path not in TTLS or cached is None or time.monotonic()-cached[0]>=TTLS[path]:
                    cached=self._fetch_api()
                    if path in TTLS:self.preview.api_cache[self.path]=cached
            self.send_content(cached[1],cached[2])
        except (URLError,TimeoutError,OSError):
            self.send_content(b'{"error":"Pi telemetry unavailable"}','application/json',502)

    def _fetch_api(self):
        """(time, body, Content-Type) of this request answered by the Pi, decompressed."""
        request=Request(self.preview.pi_url+self.path,headers={'Accept-Encoding':'gzip'})
        with urlopen(request,timeout=1.2) as response:
            content=response.read();mime=response.headers.get('Content-Type','application/json')
            if response.headers.get('Content-Encoding')=='gzip':content=gzip.decompress(content)
        return (time.monotonic(),content,mime)

    def _send_file(self,name):
        """Send the web file called ``name`` (404 for unknown names); mark the Overview as a preview."""
        target=ASSETS.find(name)
        if target is None:self.send_error(404);return
        content=target.read_bytes()
        if target.name=='bench.html':
            content=render_connection_panel(content,getattr(self.server,'display_pi_url',self.preview.pi_url))
            content=content.replace(b'<body class="bench-shell">',b'<body class="bench-shell" data-preview="true">').replace(b'Live Instrument Workspace',PREVIEW_LABEL).replace(b'</nav>',b'</nav><p class="preview-banner">'+PREVIEW_LABEL+b'</p>')
        self.send_content(content,ASSETS.mime_type(name)+'; charset=utf-8')

    def do_POST(self):
        """Run same-origin file analysis; every acquisition control is refused (read-only)."""
        if web_api.handles(self.command,self.path):
            try:
                if self.headers.get('Origin')!='http://'+self.headers.get('Host',''):
                    self.send_content(b'{"error":"File analysis requires the same preview origin"}','application/json',403);return
                web_api.serve(self)
            except (BrokenPipeError,ConnectionResetError):pass
            return
        try:self.send_content(b'{"error":"Preview is read-only. Use the live Pi dashboard for acquisition controls."}','application/json',403)
        except (BrokenPipeError,ConnectionResetError):pass
    do_PUT=do_PATCH=do_DELETE=do_POST

    def log_message(self,format,*args):  # noqa: A002  (the base class names it format)
        """Stay quiet: preview polls would flood the terminal."""
