"""2.6.0: the administrator decides how FlowSphera uses reverse DNS — off (nothing asked, no DNS names), only for the hosts a
page shows, or also in the background at 5 / 20 / 50 lookups a second; FT_DNS_RATE gives the default.
Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402


class Settings(unittest.TestCase):
    def setUp(self):
        self.f = os.path.join(tempfile.mkdtemp(), 'dns.json')
        self.p = [mock.patch.object(api, 'DNS_SETTINGS', self.f), mock.patch.object(api, '_dns_set', [None, None])]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_default_and_env(self):
        for env, want in (('', ('background', 20)), ('0', ('off', 20)), ('off', ('off', 20)), ('shown', ('shown', 20)),
                          ('5', ('background', 5)), ('50', ('background', 50)), ('7', ('background', 20))):
            with mock.patch.dict(os.environ, {'FT_DNS_RATE': env}):
                api._dns_set[:] = [None, None]
                d = api.dns_settings()
            self.assertEqual((d['mode'], d['rate']), want, env)

    def test_saved_wins_and_checked(self):
        self.assertEqual(api.post_dns({'mode': 'shown', 'rate': 5})['mode'], 'shown')
        with mock.patch.dict(os.environ, {'FT_DNS_RATE': 'off'}):
            api._dns_set[:] = [None, None]
            self.assertEqual(api.dns_settings(), {'mode': 'shown', 'rate': 5})
        for bad in ({'mode': 'fast'}, {'mode': 'background', 'rate': 1000}, {}):
            with self.assertRaises(api.BadRequest):
                api.post_dns(bad)
        g = api.get_dns()
        self.assertEqual((g['rates'], g['days'], g['max_hosts']), ([5, 20, 50], api.DNS_DAYS, api.DNS_HOSTS))

    def test_off_asks_nothing_and_shows_no_dns_name(self):
        n = api.Names.__new__(api.Names)
        n.pool, n.cache, n.pending, n.lock, n.dirty = mock.Mock(), {'10.0.0.7': ('printer.lan', time.time() - 7200)}, set(), threading.Lock(), False
        n.manual, n.self_ips = {'10.0.0.5': 'Office PC'}, {}
        api.post_dns({'mode': 'off', 'rate': 20})
        self.assertEqual((n.get('10.0.0.7'), n.get('10.0.0.8'), n.get('10.0.0.5')), ('', '', 'Office PC'))
        n.pool.submit.assert_not_called()
        self.assertEqual(n.find('printer'), [])
        api.post_dns({'mode': 'shown', 'rate': 20})
        self.assertEqual(n.get('10.0.0.7'), 'printer.lan')
        n.pool.submit.assert_called_once()                   # stale (2 h): asked again
        self.assertEqual(n.find('printer')[0]['ip'], '10.0.0.7')

    def _indexer_pass(self):
        stop = threading.Event()
        with mock.patch.object(api, 'inside_hosts', return_value=['10.0.0.20']), mock.patch.object(api.NAMES, 'index') as idx, \
             mock.patch.object(api.NAMES, 'save_cache'), mock.patch.object(api, 'web_query'):
            t = threading.Thread(target=api.dns_indexer, args=(stop,), kwargs={'first': 0})
            t.start()
            time.sleep(0.3)
            stop.set()
            t.join(2)
        return idx

    def test_background_pass_follows_the_choice(self):
        api.post_dns({'mode': 'background', 'rate': 5})
        idx = self._indexer_pass()
        idx.assert_called_once()
        self.assertEqual(idx.call_args.kwargs['rate'], 5)
        for mode in ('shown', 'off'):
            api.post_dns({'mode': mode, 'rate': 20})
            self._indexer_pass().assert_not_called()

    def test_page(self):
        with open(os.path.join(os.path.dirname(api.__file__), 'web', 'app.js')) as f:
            js = f.read()
        self.assertIn('async function dnsPanel()', js)
        self.assertIn("apiPost('dns', {mode, rate})", js)
        self.assertIn('/api/dns', api.ADMIN_GET)


if __name__ == '__main__':
    unittest.main()
