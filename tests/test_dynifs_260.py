"""2.6.0: a MikroTik gives each VPN session (<sstp-user>) a new interface index: the names of every index are kept
(snmp.remember_names, from the counter reads every minute), a gone index keeps its name, and Capacity marks such
interfaces dynamic (the page folds them by name).
Run: python -m unittest discover -s tests"""
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
import ifcounters  # noqa: E402
import snmp  # noqa: E402


class Names(unittest.TestCase):
    def setUp(self):
        self.f = os.path.join(tempfile.mkdtemp(), 'seen.json')
        self.p = [mock.patch.object(snmp, 'SEEN', self.f), mock.patch.object(snmp, '_seen', [None, {}])]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_kept_and_touched_hourly(self):
        t = 1_700_000_000
        self.assertTrue(snmp.remember_names('10.0.0.1', {2: 'ether1', 15731993: '<sstp-yegor>', 5: '', 6: None}, t))
        self.assertFalse(snmp.remember_names('10.0.0.1', {2: 'ether1'}, t + 60))          # nothing new: no write
        self.assertTrue(snmp.remember_names('10.0.0.1', {2: 'ether1'}, t + snmp.SEEN_TOUCH))
        self.assertTrue(snmp.remember_names('10.0.0.1', {2: 'wan'}, t + snmp.SEEN_TOUCH + 1))    # renamed
        self.assertEqual(snmp.seen_names(), {'10.0.0.1': {'2': 'wan', '15731993': '<sstp-yegor>'}})

    def test_old_dropped(self):
        t = 1_700_000_000
        snmp.remember_names('10.0.0.1', {15729679: '<sstp-yegor>'}, t)
        snmp.remember_names('10.0.0.1', {15731993: '<sstp-yegor>'}, t + snmp.SEEN_KEEP + 10)
        self.assertEqual(set(snmp.seen_names()['10.0.0.1']), {'15731993'})

    def test_past_in_data_and_merge(self):
        snmp.remember_names('10.0.0.1', {15729679: '<sstp-yegor>', 2: 'ether1'}, time.time())
        data = {'10.0.0.1': {'ok': True, 'ifs': {'2': {'name': 'ether1'}, '15731993': {'name': '<sstp-yegor>'}}, 'addrs': {'2': ['192.0.2.1/24']}}}
        load = snmp._load
        with mock.patch.object(snmp, '_load', side_effect=lambda p: data if p == snmp.DATA else load(p)):
            d = snmp.load_data()
        self.assertEqual(d['10.0.0.1']['past'], {'15729679': '<sstp-yegor>'})          # only gone indexes
        m = snmp.merge({'10.0.0.1': {'if_names': {'2': 'WAN'}}}, d, {'10.0.0.1': {'enabled': True}})
        self.assertEqual(m['10.0.0.1']['if_names'], {'15729679': '<sstp-yegor>', '2': 'WAN', '15731993': '<sstp-yegor>'})
        self.assertEqual(api.iface({}, 15729679, 0, 0, (), d['10.0.0.1'])['name'], '<sstp-yegor>')

    def test_counter_thread_keeps_them(self):
        found = {2: {'in_octets': 1, 'out_octets': 1, 'name': 'ether1'}, 15731993: {'in_octets': 1, 'out_octets': 1, 'name': '<sstp-yegor>'}}
        with mock.patch.object(snmp, 'load_settings', return_value={'10.0.0.1': {'enabled': True}}), \
             mock.patch.object(ifcounters, 'read', return_value=found), mock.patch.object(ifcounters, 'ch'), \
             mock.patch.object(ifcounters, '_status'):
            ifcounters.Poller(log=lambda m: None).once()
        self.assertEqual(snmp.seen_names()['10.0.0.1']['15731993'], '<sstp-yegor>')
        self.assertIn('name', ifcounters.COMMON)


class Dynamic(unittest.TestCase):
    def test_which(self):
        mt = {'vendor': 'MikroTik'}
        self.assertEqual(api.iface_dynamic(mt, 15731993, '<sstp-yegor>'), '<sstp-yegor>')
        self.assertEqual(api.iface_dynamic({}, 7, '<pppoe-client1>'), '<pppoe-client1>')
        self.assertEqual(api.iface_dynamic(mt, 15738749, 'if 15738749'), '')          # an earlier one, name not kept
        self.assertIsNone(api.iface_dynamic({'vendor': 'Fortinet'}, 15738749, 'if 15738749'))
        self.assertIsNone(api.iface_dynamic(mt, 2, 'ether1'))
        self.assertIsNone(api.iface_dynamic(mt, 12, 'if 12'))
        self.assertIsNone(api.iface_dynamic(mt, 3, '<>'))

    def test_page_and_report(self):
        root = os.path.dirname(api.__file__)
        with open(os.path.join(root, 'web', 'app.js')) as f:
            js = f.read()
        self.assertIn('every.filter(x => !x.dynamic)', js)
        self.assertIn('groups.map(dynHtml)', js)
        with open(os.path.join(root, 'reports.py')) as f:
            self.assertIn("not x.get('dynamic')", f.read())
        with open(os.path.join(root, 'api.py')) as f:
            self.assertIn("'dynamic': dyn is not None", f.read())


if __name__ == '__main__':
    unittest.main()


class DeviceInterfaces(unittest.TestCase):
    def test_marked(self):      # (2.6.0) Settings → Devices folds them by this mark
        mt = {'vendor': 'MikroTik'}
        self.assertEqual(api.iface(mt, 15731993, 0, 0, (), {'ifs': {'15731993': {'name': '<sstp-yegor>'}}})['dyn'], '<sstp-yegor>')
        self.assertEqual(api.iface(mt, 15738749, 0, 0, (), None)['dyn'], '')
        self.assertIsNone(api.iface(mt, 2, 0, 0, (), {'ifs': {'2': {'name': 'ether1'}}})['dyn'])
        with open(os.path.join(os.path.dirname(api.__file__), 'web', 'app.js')) as f:
            self.assertIn("x.interfaces.filter(i => i.dyn == null)", f.read())
