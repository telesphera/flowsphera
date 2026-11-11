"""2.4.2: an administrator may send more than 64 KB (an own IP list of 20,000 entries used to stop at about 3,000
lines with «too large»); the own list keeps its comments; /api/devices carries the server's clock.
Run: python -m unittest discover -s tests"""
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import detect  # noqa: E402


def post(body, role):
    """do_POST of a request carrying `body`, sent by a user of `role` (None = not signed in); (code, answer)."""
    h = api.H.__new__(api.H)
    data = json.dumps(body).encode()
    h.path, h.rfile = '/api/nowhere', io.BytesIO(data)
    h.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(data))}
    got = {}
    h.json = lambda code, obj: got.update(code=code, obj=obj)
    h.who = lambda: ('u', role, None) if role else (None, None, None)
    h.token, h.client_ip = (lambda: None), (lambda: '127.0.0.1')
    h.do_POST()
    return got['code'], got['obj']


class BodyLimit(unittest.TestCase):
    BIG = {'own_list': [f'10.{i // 250}.{i % 250}.0/24' for i in range(20000)]}      # ≈ 360 KB

    def test_admin_may_send_a_big_list(self):
        code, obj = post(self.BIG, 'admin')
        self.assertNotEqual(code, 413, obj)          # read and routed: this path does not exist → 404

    def test_others_still_stop_at_64_kb(self):
        self.assertEqual(post(self.BIG, 'viewer')[0], 413)
        self.assertEqual(post(self.BIG, None)[0], 413)

    def test_above_the_big_limit(self):
        with mock.patch.object(api, 'BIG_BODY', 100000):
            self.assertEqual(post(self.BIG, 'admin')[0], 413)


class OwnList(unittest.TestCase):
    def test_comments_and_lines(self):
        c = detect.validate({'own_list': ['; Spamhaus DROP List', '1.10.16.0/20 ; SBL256894', '# mine',
                                          '203.0.113.9 # a scanner', '198.51.100.7, 198.51.100.8', '  ']})
        self.assertEqual(c['own_list'], ['1.10.16.0/20', '198.51.100.7', '198.51.100.8', '203.0.113.9'])

    def test_text_as_before(self):
        self.assertEqual(detect.validate({'own_list': '203.0.113.9, 198.51.100.0/24'})['own_list'],
                         ['198.51.100.0/24', '203.0.113.9'])

    def test_twenty_thousand(self):
        self.assertEqual(len(detect.validate(BodyLimit.BIG)['own_list']), 20000)


class ServerClock(unittest.TestCase):
    def test_devices_carry_now(self):
        src = open(api.__file__).read()
        self.assertIn("'now': int(time.time())", src[src.index('def api_devices'):])
        js = open(os.path.join(os.path.dirname(api.__file__), 'web', 'app.js')).read()
        self.assertNotIn('Date.now() / 1000 - x.last', js)
        self.assertEqual(js.count('srvNow('), 2)


if __name__ == '__main__':
    unittest.main()
