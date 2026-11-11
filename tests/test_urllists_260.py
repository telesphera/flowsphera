"""2.6.0: IP reputation lists added by URL — checked in the settings, downloaded by the same machinery as the built-in
lists (now, after a change of address, then on their own schedule), any common shape read, removed ones forgotten.
Run: python -m unittest discover -s tests"""
import collections
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import api  # noqa: E402
import detect  # noqa: E402
import reputation  # noqa: E402


class Parse(unittest.TestCase):
    def test_shapes(self):
        p = lambda t: list(reputation._auto(t))      # noqa: E731
        self.assertEqual(p('; Spamhaus DROP\n1.10.16.0/20 ; SBL256894\n# x\n\n203.0.113.9 # scanner\n'), ['1.10.16.0/20', '203.0.113.9'])
        self.assertEqual(p('ip,first_seen\n198.51.100.7,2026-01-01\n'), ['ip', '198.51.100.7'])          # the header is no address: dropped later
        self.assertEqual(p('["203.0.113.1", "198.51.100.0/24"]'), ['203.0.113.1', '198.51.100.0/24'])
        self.assertEqual(p('{"data": [{"ip_address": "203.0.113.2"}, {"cidr": "198.51.100.0/25"}, {"x": 1}]}'), ['203.0.113.2', '198.51.100.0/25'])
        self.assertEqual(p('{"cidr":"1.10.16.0/20","sblid":"SBL1"}\n{"cidr":"2.56.192.0/22"}\n{"type":"metadata"}'), ['1.10.16.0/20', '2.56.192.0/22'])
        self.assertEqual(p('﻿203.0.113.3\tfoo\n'), ['203.0.113.3'])
        self.assertEqual(reputation.networks(p('ip\n10.0.0.1\n45.155.205.4\n')), [reputation.ipaddress.ip_network('45.155.205.4/32')])


class Settings(unittest.TestCase):
    def test_checked(self):
        got = detect.url_lists([{'url': ' https://example.org/a.txt ', 'name': '  My   list ', 'category': 'malware', 'hours': 6, 'on': False, 'id': 'ab12'},
                                {'url': 'http://198.51.100.5:8080/b', 'hours': '5', 'category': 'nope', 'id': 'ab12'}])
        self.assertEqual(got[0], {'id': 'ab12', 'name': 'My list', 'url': 'https://example.org/a.txt', 'category': 'malware', 'hours': 6, 'on': False})
        self.assertEqual((got[1]['name'], got[1]['category'], got[1]['hours'], got[1]['on']), ('198.51.100.5', 'attack', 24, True))
        self.assertNotEqual(got[1]['id'], 'ab12')                 # a repeated id gets a new one
        for bad in ('ftp://x/y', 'file:///etc/passwd', 'https://', 'https://a b/c', 'x' * 10):
            with self.assertRaises(ValueError, msg=bad):
                detect.url_lists([{'url': bad}])
        with self.assertRaises(ValueError):
            detect.url_lists([{'url': f'https://x.org/{i}'} for i in range(reputation.URL_MAX + 1)])
        self.assertEqual(detect.validate({'url_lists': [{'url': 'https://x.org/a', 'id': 'k1'}]})['url_lists'][0]['id'], 'k1')

    def test_enabled_and_known(self):
        cfg = detect.defaults()
        cfg['url_lists'] = [{'id': 'a1', 'name': 'A', 'url': 'https://x.org/a', 'category': 'drop', 'hours': 24, 'on': True},
                            {'id': 'b2', 'name': 'B', 'url': 'https://x.org/b', 'category': 'drop', 'hours': 24, 'on': False}]
        en = detect.enabled_lists(cfg)
        self.assertIn('url_a1', en)
        self.assertNotIn('url_b2', en)
        reputation.use_url_lists(cfg['url_lists'])
        self.assertEqual((reputation.title('url_a1'), reputation.title('feodo'), reputation.category(['url_a1'])), ('A', 'abuse.ch Feodo Tracker', 'drop'))
        reputation.use_url_lists([{'id': 's1', 'name': 'S', 'url': 'https://x.org/s', 'category': 'spam', 'hours': 24}])
        self.assertEqual((reputation.category(['url_s1']), reputation.category(['url_s1', 'tor_exit']), reputation.category(['url_s1', 'cins'])),
                         ('spam', 'spam', 'attack'))      # (2.6.0) spam: below attack, above Tor
        self.assertEqual(detect.url_lists([{'url': 'https://x.org/s', 'category': 'spam'}])[0]['category'], 'spam')
        reputation.use_url_lists([])

    def test_saved_and_read_back(self):
        with mock.patch.object(detect, 'CONFIG', os.path.join(TMP, 'state', 'detect_test.json')):
            detect.save_config(detect.validate({'url_lists': [{'url': 'https://x.org/a', 'id': 'k1', 'name': 'K'}]}))
            cfg = detect.load_config()
        self.assertEqual(cfg['url_lists'][0]['name'], 'K')
        self.assertEqual(reputation.title('url_k1'), 'K')        # load_config made it known
        reputation.use_url_lists([])


class Download(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.p = [mock.patch.object(reputation, 'DIR', self.dir), mock.patch.object(reputation, 'META', os.path.join(self.dir, 'meta.json'))]
        for x in self.p:
            x.start()
        self.got = collections.Counter()

    def tearDown(self):
        for x in self.p:
            x.stop()
        reputation.use_url_lists([])

    def get(self, url, key=None, body=None):
        self.got[url] += 1
        return {'https://x.org/a': '45.155.205.0/24\n185.220.101.7\n', 'https://x.org/c': '45.155.205.9\n', 'https://x.org/empty': '# nothing\n'}[url]

    def lists(self, url='https://x.org/a', hours=24):
        reputation.use_url_lists([{'id': 'a1', 'name': 'A', 'url': url, 'category': 'attack', 'hours': hours}])

    def test_now_then_on_schedule_then_new_address(self):
        self.lists()
        with mock.patch.object(reputation, '_get', side_effect=self.get):
            self.assertEqual(reputation.update(['url_a1'], log=lambda m: None, now=1000), ['url_a1'])
            self.assertEqual(reputation.update(['url_a1'], log=lambda m: None, now=1000 + 3600), [])          # daily
            self.assertEqual(reputation.update(['url_a1'], log=lambda m: None, now=1000 + 86400), ['url_a1'])
            self.lists('https://x.org/c')
            self.assertEqual(reputation.update(['url_a1'], log=lambda m: None, now=1000 + 86400 + 60), ['url_a1'])   # changed: at once
        m = reputation.meta()['url_a1']
        self.assertEqual((m['count'], m['url'], m['ok']), (1, 'https://x.org/c', True))
        idx = reputation.Index(['url_a1'])
        self.assertEqual(idx.lookup('45.155.205.9'), frozenset({'url_a1'}))

    def test_empty_keeps_the_copy_and_says_so(self):
        self.lists()
        with mock.patch.object(reputation, '_get', side_effect=self.get):
            reputation.update(['url_a1'], log=lambda m: None, now=1000)
            reputation.use_url_lists([{'id': 'a1', 'name': 'A', 'url': 'https://x.org/empty', 'category': 'attack', 'hours': 1}])
            said = []
            reputation.update(['url_a1'], log=said.append, now=2000)
        self.assertIn('no addresses', reputation.meta()['url_a1']['error'])
        self.assertTrue(said)
        self.assertEqual(open(os.path.join(self.dir, 'url_a1.txt')).read().split(), ['45.155.205.0/24', '185.220.101.7/32'])

    def test_removed_is_forgotten(self):
        self.lists()
        with mock.patch.object(reputation, '_get', side_effect=self.get):
            reputation.update(['url_a1'], log=lambda m: None, now=1000)
            reputation.use_url_lists([])
            reputation.update([], log=lambda m: None, now=1100)
        self.assertNotIn('url_a1', reputation.meta())
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'url_a1.txt')))

    def test_settings_show_the_state(self):
        cfg = detect.defaults()
        cfg['url_lists'] = [{'id': 'a1', 'name': 'A', 'url': 'https://x.org/a', 'category': 'attack', 'hours': 24, 'on': True}]
        meta = {'url_a1': {'url': 'https://x.org/a', 'count': 2, 'updated': 1000, 'error': ''}}
        with mock.patch.object(detect, 'load_config', return_value=cfg), mock.patch.object(detect, 'services', return_value=[]), \
             mock.patch.object(reputation, 'meta', return_value=meta):
            x = api.get_events_config()['config']['url_lists'][0]
        self.assertEqual((x['count'], x['updated']), (2, 1000))
        meta['url_a1']['url'] = 'https://x.org/old'                  # the address changed: nothing to show yet
        with mock.patch.object(detect, 'load_config', return_value=json.loads(json.dumps(cfg))), mock.patch.object(detect, 'services', return_value=[]), \
             mock.patch.object(reputation, 'meta', return_value=meta):
            self.assertEqual(api.get_events_config()['config']['url_lists'][0]['count'], 0)


class Dictionary(unittest.TestCase):
    def test_no_key_twice(self):           # (2.6.0) json keeps the last of two equal keys silently
        with open(os.path.join(ROOT, 'web', 'i18n', 'uk.json'), encoding='utf-8') as f:
            pairs = json.load(f, object_pairs_hook=lambda p: p)
        c = collections.Counter(k for k, _ in pairs)
        self.assertEqual([k for k, n in c.items() if n > 1], [])


if __name__ == '__main__':
    unittest.main()
