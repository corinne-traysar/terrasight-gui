"""Tests of web_api/reply.py: JSON-safe bodies and writing a reply on an HTTP handler."""
import gzip
import io
import json
import math
import unittest

from offline_analysis.web_api.reply import Reply, json_safe


class FakeHandler:
    """Records what a BaseHTTPRequestHandler would send."""

    def __init__(self, accept_encoding='', broken=False):
        """Accept ``accept_encoding``; ``broken`` makes the write fail like a closed browser tab."""
        self.headers = {'Accept-Encoding': accept_encoding}
        self.sent_headers = {}
        self.status = None
        self.wfile = io.BytesIO()
        if broken:
            self.wfile.write = self._broken_write

    @staticmethod
    def _broken_write(data):
        """Fail like a browser that hung up."""
        raise BrokenPipeError

    def send_response(self, status):
        """Record the status."""
        self.status = status

    def send_header(self, name, value):
        """Record one header."""
        self.sent_headers[name] = value

    def end_headers(self):
        """Nothing to flush."""


class JsonSafeTests(unittest.TestCase):
    """Non-finite floats become null at any depth; other values are untouched."""

    def test_nested_non_finite_values_become_none(self):
        value = {'a': [1.0, math.nan, (math.inf, -math.inf)], 'b': {'c': 2, 'd': 'text'}}
        self.assertEqual(json_safe(value), {'a': [1.0, None, [None, None]], 'b': {'c': 2, 'd': 'text'}})

    def test_encoded_is_compact_json(self):
        self.assertEqual(Reply(200, {'x': [1.5, math.nan]}).encoded(), b'{"x":[1.5,null]}')


class WriteTests(unittest.TestCase):
    """Reply.write: headers, optional gzip and tolerance of a closed connection."""

    def test_plain_reply(self):
        handler = FakeHandler()
        Reply(404, {'error': 'Not found'}).write(handler)
        self.assertEqual(handler.status, 404)
        self.assertEqual(json.loads(handler.wfile.getvalue()), {'error': 'Not found'})
        self.assertEqual(handler.sent_headers['Content-Length'], str(len(handler.wfile.getvalue())))
        self.assertEqual(handler.sent_headers['Cache-Control'], 'no-store')
        self.assertNotIn('Content-Encoding', handler.sent_headers)

    def test_gzip_when_accepted(self):
        handler = FakeHandler('gzip, deflate')
        Reply(200, {'rows': 3}).write(handler)
        self.assertEqual(handler.sent_headers['Content-Encoding'], 'gzip')
        self.assertEqual(json.loads(gzip.decompress(handler.wfile.getvalue())), {'rows': 3})

    def test_closed_connection_is_ignored(self):
        Reply(200, {}).write(FakeHandler(broken=True))


if __name__ == '__main__':
    unittest.main()
