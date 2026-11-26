"""Tests of desktop_tools/preview_handler.py: pages served locally, telemetry relayed read-only."""
import http.client
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from desktop_tools import preview_handler
from desktop_tools import preview_theme as preview

class ReadOnlyPreviewTests(unittest.TestCase):
    def setUp(self):
        self.upstream_reads=[]
        reads=self.upstream_reads
        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                reads.append(self.path);content=b'{"temperature_C":58.4}'
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
            def log_message(self,format,*args):pass
        self.upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.server=preview.PreviewServer(('127.0.0.1',0),preview.Preview,'http://127.0.0.1:'+str(self.upstream.server_port))
        self.threads=[]
        for server in (self.upstream,self.server):
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.threads.append(thread)
    def tearDown(self):
        for server in (self.server,self.upstream):server.shutdown();server.server_close()
        for thread in self.threads:thread.join()
    def request(self,path,method='GET'):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        connection.request(method,path);response=connection.getresponse();result=(response.status,response.read());connection.close();return result
    def test_acquisition_commands_are_never_forwarded(self):
        for method in ('POST','PUT','PATCH','DELETE'):
            status,_=self.request('/api/acquisition/pause',method);self.assertEqual(status,403)
        self.assertEqual(self.upstream_reads,[])
    def test_telemetry_responses_are_shared(self):
        for _ in range(3):
            status,body=self.request('/api/health');self.assertEqual(status,200);self.assertIn(b'58.4',body)
        self.assertEqual(self.upstream_reads,['/api/health'])
    def test_distinct_history_cursors_are_not_served_the_same_cached_response(self):
        self.request('/api/live?after=1');self.request('/api/live?after=2')
        self.assertEqual(self.upstream_reads,['/api/live?after=1','/api/live?after=2'])
    def test_combined_telemetry_is_forwarded(self):
        self.assertEqual(self.request('/api/telemetry?after=4&ap_after=8')[0],200)
        self.assertEqual(self.upstream_reads,['/api/telemetry?after=4&ap_after=8'])
    def test_preview_is_labeled_and_cannot_read_outside_web_directory(self):
        status,body=self.request('/');self.assertEqual(status,200);self.assertIn(b'Controls Read-Only',body)
        self.assertEqual(self.request('/../bench_app.py')[0],404)
        self.assertEqual(self.request('/api/arbitrary')[0],404)

if __name__=='__main__':unittest.main()


class RouteTableTests(unittest.TestCase):
    """The page routes and relayed APIs, and the re-exports used by preview_theme."""

    def test_routes_name_existing_pages_and_re_exports_match(self):
        self.assertEqual(preview_handler.ROUTES['/'], 'bench.html')
        self.assertIn('/api/telemetry', preview_handler.READ_APIS)
        self.assertIs(preview.Preview, preview_handler.Preview)


if __name__ == '__main__':
    unittest.main()
