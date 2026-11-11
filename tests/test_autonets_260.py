"""2.6.0: Top hosts → Networks without named networks — the networks of the devices' interface addresses (SNMP or typed)
with their own masks, else a /24 guess; a named network wins; net: takes such a network by its address.
Run: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import common  # noqa: E402

EXP = {'192.0.2.1': {'name': 'fw', 'wan_ifs': [1], 'if_names': {'1': 'wan', '5': 'lan', '6': 'big', '7': 'vpn'},
                     'if_addrs': {'1': ['198.51.100.58/24'], '5': ['192.168.1.1/24'], '6': ['10.10.0.1/16'],
                                  '7': ['10.1.1.1/32'], '8': ['bad'], '9': ['11.0.0.1/7']}},
       '192.0.2.2': {'name': 'rb', 'if_addrs': {'3': ['192.168.1.2/24', '172.31.1.1/24']}}}


def named(nets):
    path = common.UI_NETWORKS          # the module's STATE_DIR: the first test module imported set it
    with open(path, 'w') as f:
        json.dump(nets, f)
    os.utime(path, (time.time() + len(nets), time.time() + len(nets)))      # a new time: read again


class Auto(unittest.TestCase):
    def setUp(self):
        api.AUTO_NETS.update(t=0.0, key=None, v=[])
        named([])
        self.p = [mock.patch.object(api, 'exporters_cfg', return_value=EXP), mock.patch.object(api.snmp, 'merge', side_effect=lambda e: e)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        named([])

    def test_networks_of_the_interfaces(self):
        got = [(x['net'], x['iface'], x['device']) for x in api.auto_networks()]
        self.assertEqual(got, [('172.31.1.0/24', 'if 3', 'rb'), ('192.168.1.0/24', 'lan', 'fw'), ('198.51.100.0/24', 'wan', 'fw'),
                               ('10.10.0.0/16', 'big', 'fw')])        # narrowest first; /32, wider than /8, bad left out

    def test_named_wins(self):
        named([{'net': '192.168.1.0/24', 'name': 'Office'}])
        self.assertNotIn('192.168.1.0/24', [x['net'] for x in api.auto_networks()])
        self.assertEqual(api.net_kind('Office'), ('named', ['192.168.1.0/24']))
        self.assertEqual(api.net_kind('10.10.0.0/16'), ('iface', {'net': '10.10.0.0/16', 'iface': 'big', 'device': 'fw'}))
        self.assertEqual(api.net_kind('10.0.4.0/24'), ('guess', None))
        self.assertEqual(api.net_kind(''), (None, None))

    def test_expression(self):
        named([{'net': '192.168.1.0/24', 'name': 'Office'}])
        p = {}
        e = api.net_expr('int_ip', p)
        self.assertTrue(e.startswith('multiIf(isIPAddressInRange(int_ip, {nc0:String}), {nn0:String}, isIPAddressInRange(int_ip, {na0:String}), {na0:String}'))
        self.assertTrue(e.endswith(api.GUESS_NET.format(c='int_ip') + ')'))
        self.assertEqual((p['nn0'], p['na0'], p['na2']), ('Office', '172.31.1.0/24', '10.10.0.0/16'))      # Office's own network is no auto one

    def test_nothing_known_is_only_the_guess(self):
        with mock.patch.object(api, 'exporters_cfg', return_value={}):
            self.assertEqual(api.net_expr('int_ip', {}), api.GUESS_NET.format(c='int_ip'))

    def test_rows(self):
        named([{'net': '192.168.1.0/24', 'name': 'Office'}])
        rows = [{'k': 'Office'}, {'k': '10.10.0.0/16'}, {'k': '10.0.4.0/24'}, {'k': ''}]
        api.net_rows(rows, {}, '')
        self.assertEqual(rows, [{'k': 'Office', 'nets': ['192.168.1.0/24']},
                                {'k': '10.10.0.0/16', 'nets': ['10.10.0.0/16'], 'auto': 'iface', 'iface': 'big', 'device': 'fw'},
                                {'k': '10.0.4.0/24', 'nets': ['10.0.4.0/24'], 'auto': 'guess'}, {'k': '', 'nets': []}])

    def test_filter_by_address(self):
        q = {'range': ['24h'], 'f': [json.dumps([{'k': 'net', 'v': '10.10.0.5/16'}])]}
        where, p, *_ = api.scope(q)
        self.assertIn('10.10.0.0/16', p.values())
        self.assertIn('multiIf(', where)
        with self.assertRaises(api.BadRequest):
            api.scope({'range': ['24h'], 'f': [json.dumps([{'k': 'net', 'v': 'Nowhere'}])]})

    def test_events(self):
        a = {'ip': '10.10.3.4'}
        self.assertTrue(api._event_match(a, {'k': 'net', 'v': '10.10.0.0/16'}))
        self.assertFalse(api._event_match(a, {'k': 'net', 'v': '10.20.0.0/16'}))

    def test_cached(self):
        api.auto_networks()
        with mock.patch.object(api, 'exporters_cfg', return_value={}):
            self.assertEqual(len(api.auto_networks()), 4)          # within AUTO_TTL
            named([{'net': '10.99.0.0/16', 'name': 'X'}])            # a new name: made again
            self.assertEqual(api.auto_networks(), [])


class Page(unittest.TestCase):
    def test_ui(self):
        with open(os.path.join(os.path.dirname(api.__file__), 'web', 'app.js')) as f:
            js = f.read()
        self.assertNotIn('noNets', js)
        self.assertIn("r.auto === 'guess'", js)
        self.assertIn("key === 'net' && !netFind(v) && v.includes('/')", js)


if __name__ == '__main__':
    unittest.main()
