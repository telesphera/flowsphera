"""2.5.0: search by host name — every name known (manual, device addresses, reverse DNS) is searched, the reverse DNS
names are kept across restarts and the inside hosts of the last week get theirs in the background.
Run: python -m unittest discover -s tests"""
import json
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


def names(manual=None, self_ips=None, dns=None):
    n = api.Names.__new__(api.Names)
    n.pool = mock.Mock()
    n.cache, n.pending, n.lock, n.dirty = dict(dns or {}), set(), threading.Lock(), False
    n.manual, n.self_ips = dict(manual or {}), dict(self_ips or {})
    return n


class Find(unittest.TestCase):
    def setUp(self):
        now = time.time()
        self.n = names({'10.0.0.5': 'Printer office', '10.0.0.9': 'nas'}, {'10.0.0.1': 'fw-main (self)'},
                       {'10.0.0.7': ('printer2.lan', now), '10.0.0.5': ('old-dns-name', now), '10.0.0.8': ('', now),
                        '10.0.0.11': ('laptop-printerless.lan', now)})

    def test_every_source_any_case_begins_first(self):
        got = self.n.find('PRINTER')
        self.assertEqual([(r['name'], r['src']) for r in got],
                         [('Printer office', 'manual'), ('printer2.lan', 'dns'), ('laptop-printerless.lan', 'dns')])

    def test_the_name_shown_wins(self):            # a manual name hides the host's DNS name
        self.assertEqual(self.n.find('old-dns'), [])
        self.assertEqual(self.n.find('fw-')[0], {'ip': '10.0.0.1', 'name': 'fw-main (self)', 'src': 'device'})

    def test_empty_and_limit(self):
        self.assertEqual(self.n.find('  '), [])
        self.assertEqual(len(self.n.find('.lan', limit=1)), 1)

    def test_endpoint(self):
        with mock.patch.object(api, 'NAMES', self.n):
            self.assertEqual(api.api_hosts_find({'q': ['nas'], 'limit': ['999']})['hosts'][0]['ip'], '10.0.0.9')
            self.assertEqual(api.api_hosts_find({'q': ['lan'], 'limit': ['x']})['hosts'][0]['name'], 'laptop-printerless.lan')
            self.assertEqual(api.api_hosts_find({})['hosts'], [])


class Cache(unittest.TestCase):
    def test_saved_and_loaded_old_dropped(self):
        f = os.path.join(TMP, 'state', 'dns_test.json')
        with mock.patch.object(api, 'DNS_FILE', f):
            n = names(dns={'10.0.0.7': ('printer2.lan', time.time())})
            n.dirty = True
            n.save_cache()
            self.assertFalse(n.dirty)
            raw = json.load(open(f))
            raw['10.0.0.99'] = ['gone.lan', time.time() - api.DNS_KEEP - 10]
            json.dump(raw, open(f, 'w'))
            m = names()
            m.load_cache()
            self.assertEqual(set(m.cache), {'10.0.0.7'})
            self.assertEqual(m.cache['10.0.0.7'][0], 'printer2.lan')
            open(f, 'w').write('not json')
            m.load_cache()
            self.assertEqual(m.cache, {})


class Index(unittest.TestCase):
    def test_only_inside_hosts_without_a_fresh_name(self):
        now = time.time()
        n = names({'10.0.0.5': 'Printer'}, {'10.0.0.1': 'fw (self)'},
                  {'10.0.0.7': ('fresh.lan', now), '10.0.0.8': ('stale.lan', now - api.DNS_REFRESH - 5),
                   '10.0.0.3': ('', now - api.DNS_KEEP - 5)})
        ok = n.index(['10.0.0.5', '10.0.0.1', '10.0.0.7', '10.0.0.8', '8.8.8.8', '10.0.0.20'], rate=10000)
        self.assertTrue(ok)
        self.assertEqual(sorted(c.args[1] for c in n.pool.submit.call_args_list), ['10.0.0.20', '10.0.0.8'])
        self.assertNotIn('10.0.0.3', n.cache)      # not seen for a month: forgotten
        self.assertTrue(n.dirty)

    def test_stops(self):
        stop = threading.Event()
        stop.set()
        n = names()
        self.assertFalse(n.index(['10.0.0.20'], stop, rate=10000))
        n.pool.submit.assert_not_called()

    def test_resolve_marks_dirty(self):
        n = names()
        with mock.patch.object(api.socket, 'gethostbyaddr', return_value=('pc.lan', [], [])):
            n._resolve('10.0.0.20')
        self.assertEqual(n.cache['10.0.0.20'][0], 'pc.lan')
        self.assertTrue(n.dirty)

    def test_inside_hosts_query(self):
        with mock.patch.object(api, 'ch', return_value=[{'ip': '10.0.0.20', 'b': 5}]) as ch, \
             mock.patch.object(api.rollups, 'source', return_value=('(SELECT 1)', None)) as src:
            self.assertEqual(api.inside_hosts(), ['10.0.0.20'])
        self.assertEqual(src.call_args.args[0], ['int_ip'])
        self.assertIn('ORDER BY b DESC LIMIT 20000', ch.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
