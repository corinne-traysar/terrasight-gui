#!/usr/bin/env python3
"""Local visual preview with read-only Pi telemetry. No sensor devices are opened."""
import argparse
import sys
import gzip
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen, Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connection import load_connection, render_connection_panel, validate_pi_url

WEB = Path(__file__).resolve().parents[1] / 'web'
ROUTES = {'/':'bench.html','/vn100':'index.html','/mc95a':'mc95a.html','/ap230':'ap230.html'}
READ_APIS = {'/api/bench','/api/health','/api/live','/api/ap230','/api/samples','/api/events','/api/telemetry'}
# Share recent responses between Overview and an already-open instrument iframe.
# Never extend a response's lifetime on upstream failure or fabricate telemetry.
TTLS = {'/api/live':.2,'/api/ap230':.25,'/api/bench':1.0,'/api/health':1.0}

class Preview(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def send_content(self,content,mime,status=200):
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
    def do_GET(self):
        try: self.read_get()
        except (BrokenPipeError, ConnectionResetError): pass
    def read_get(self):
        path=urlsplit(self.path).path
        if path in READ_APIS:
            if path=='/api/events':
                try:
                    with urlopen(self.server.pi_url+self.path,timeout=4) as response:
                        self.send_response(200);self.send_header('Content-Type','text/event-stream')
                        self.send_header('Cache-Control','no-store');self.end_headers()
                        while True:
                            chunk=response.read1(16384)
                            if not chunk:break
                            self.wfile.write(chunk);self.wfile.flush()
                except (URLError,TimeoutError,OSError): pass
                return
            try:
                lock=self.server.api_locks.get(path,threading.Lock())
                with lock:
                    cache_key=self.path
                    cached=self.server.api_cache.get(cache_key)
                    if path not in TTLS or cached is None or time.monotonic()-cached[0]>=TTLS[path]:
                        request=Request(self.server.pi_url+self.path,headers={'Accept-Encoding':'gzip'})
                        with urlopen(request,timeout=1.2) as response:
                            content=response.read();mime=response.headers.get('Content-Type','application/json')
                            if response.headers.get('Content-Encoding')=='gzip':content=gzip.decompress(content)
                        cached=(time.monotonic(),content,mime)
                        if path in TTLS:self.server.api_cache[cache_key]=cached
                self.send_content(cached[1],cached[2])
            except (URLError,TimeoutError,OSError):
                self.send_content(b'{"error":"Pi telemetry unavailable"}','application/json',502)
            return
        name=ROUTES.get(path,path.lstrip('/'));target=(WEB/name).resolve()
        if target.parent!=WEB.resolve() or not target.is_file():self.send_error(404);return
        content=target.read_bytes()
        mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png'}.get(target.suffix,'application/octet-stream')
        if target.name=='bench.html':
            content=render_connection_panel(content,getattr(self.server,'display_pi_url',self.server.pi_url))
            content=content.replace(b'<body class="bench-shell">',b'<body class="bench-shell" data-preview="true">').replace(b'Live Instrument Workspace',b'Local Preview / Live Data / Controls Read-Only').replace(b'</nav>',b'</nav><p class="preview-banner">Local Preview / Live Data / Controls Read-Only</p>')
        self.send_content(content,mime+'; charset=utf-8')
    def do_POST(self):
        try:self.send_content(b'{"error":"Preview is read-only. Use the live Pi dashboard for acquisition controls."}','application/json',403)
        except (BrokenPipeError,ConnectionResetError):pass
    do_PUT=do_PATCH=do_DELETE=do_POST
    def log_message(self,*_):pass

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--pi-url',default=load_connection()['pi_url'])
    args=parser.parse_args();server=ThreadingHTTPServer(('127.0.0.1',args.port),Preview)
    server.daemon_threads=True;server.pi_url=validate_pi_url(args.pi_url);server.display_pi_url=server.pi_url
    # Resolve the bench hostname once; repeated mDNS lookups can stall each poll.
    parsed=urlsplit(server.pi_url)
    try:
        if parsed.scheme=='http':
            address=socket.gethostbyname(parsed.hostname)
            server.pi_url=f'http://{address}:{parsed.port or 80}'
    except OSError:pass
    server.api_cache={};server.api_locks={path:threading.Lock() for path in TTLS}
    print(f'Local read-only preview: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
