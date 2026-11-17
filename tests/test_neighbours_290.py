"""2.9.0 (GitHub issues #11 #12): links that do not depend on addresses — LLDP neighbours read over SNMP, links set by
hand — and the false links of addresses many devices share (Juniper jsrv.1 / em2.32768 on every MX), and the role
«Management» (an out-of-band port is never on a path). Run: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import common  # noqa: E402
import neighbours as N  # noqa: E402
import snmp  # noqa: E402
import topology as T  # noqa: E402

ASBR, P1, PE, CE = '192.0.2.1', '192.0.2.2', '192.0.2.3', '192.0.2.4'
hx = lambda t: t.encode().hex()


def iface(dev, i, out=0, inb=0):
    return {'exporter': dev, 'iface': i, 'out_bytes': out, 'in_bytes': inb, 'up': 0, 'down': 0, 'internal': out + inb}


def links(topo):
    return {frozenset((lk['a'], lk['b'])): lk for lk in topo['links']}


def hops(topo):
    """what River does (app.js hopsFromInternet): breadth first from the internet over every link"""
    m, q = {T.INTERNET: 0}, [T.INTERNET]
    while q:
        c = q.pop(0)
        for lk in topo['links']:
            o = lk['b'] if lk['a'] == c else lk['a'] if lk['b'] == c else None
            if o and o not in m:
                m[o] = m[c] + 1
                q.append(o)
    return m


class FakeSession:
    def __init__(self, walks):
        self.walks = walks

    def walk(self, oid, raw=False):
        return snmp.parse(self.walks.get(oid, ''), raw)


class Parse(unittest.TestCase):
    def test_fortigate_rem_table_and_stack(self):
        """the rows a FortiGate 40F (FortiOS 7.4) answered on 2026-11-17: a FortiAP on port 5"""
        rem = '\n'.join([
            '.1.0.8802.1.1.2.1.4.1.1.4.2200157.5.1 = INTEGER: 4',
            '.1.0.8802.1.1.2.1.4.1.1.5.2200157.5.1 = Hex-STRING: 70 4C A5 93 C3 40 ',
            '.1.0.8802.1.1.2.1.4.1.1.6.2200157.5.1 = INTEGER: 3',
            '.1.0.8802.1.1.2.1.4.1.1.7.2200157.5.1 = Hex-STRING: 70 4C A5 93 C3 40 ',
            '.1.0.8802.1.1.2.1.4.1.1.8.2200157.5.1 = Hex-STRING: 65 74 68 30 ',
            '.1.0.8802.1.1.2.1.4.1.1.9.2200157.5.1 = Hex-STRING: 46 6F 72 74 69 41 50 2D 32 32 31 45 '])
        man = '.1.0.8802.1.1.2.1.4.2.1.1.2200157.5.1.1.4.192.168.1.100 = INTEGER: 1'
        stack = '.1.3.6.1.2.1.31.1.2.1.3.0.3 = INTEGER: 1\n.1.3.6.1.2.1.31.1.2.1.3.10.5 = INTEGER: 1\n.1.3.6.1.2.1.31.1.2.1.3.19.1 = INTEGER: 1'
        lldp, st = snmp._lldp(FakeSession({snmp.LLDP_REM: rem, snmp.LLDP_MAN: man, snmp.IF_STACK: stack}))
        self.assertEqual(lldp['rem'], [[5, 4, '704ca593c340', 3, '704ca593c340', 'eth0', 'FortiAP-221E', ['192.168.1.100']]])
        self.assertEqual(st, {'5': [10], '1': [19]})                      # 0 = top of the stack: left out

    def test_no_lldp_is_not_an_error(self):
        lldp, st = snmp._lldp(FakeSession({}))
        self.assertIsNone(lldp)
        self.assertEqual(st, {})

    def test_local_table(self):
        loc = '\n'.join(['.1.0.8802.1.1.2.1.3.1.0 = INTEGER: 4', '.1.0.8802.1.1.2.1.3.2.0 = Hex-STRING: 00 11 22 33 44 55 ',
                         '.1.0.8802.1.1.2.1.3.3.0 = Hex-STRING: 70 31 ', '.1.0.8802.1.1.2.1.3.7.1.2.3 = INTEGER: 5',
                         '.1.0.8802.1.1.2.1.3.7.1.3.3 = Hex-STRING: 47 69 30 2F 30 2F 31 ', '.1.0.8802.1.1.2.1.3.7.1.4.3 = Hex-STRING: 75 70 6C 69 6E 6B '])
        lldp, _ = snmp._lldp(FakeSession({snmp.LLDP_LOC: loc}))
        self.assertEqual(lldp['chassis'], [4, '001122334455'])
        self.assertEqual(lldp['name'], 'p1')
        self.assertEqual(lldp['ports'], {'3': [5, hx('Gi0/0/1'), 'uplink']})


# a Cisco P router: LLDP port 3 = Gi0/0/1 (ifIndex 7), Po1 (20) over it, Po1.2111 (21) over Po1
CISCO = {'sys': {'name': 'p1.example.net'}, 'ifs': {'7': {'name': 'Gi0/0/1', 'descr': 'GigabitEthernet0/0/1'}, '20': {'name': 'Po1'},
                                                    '21': {'name': 'Po1.2111'}, '3': {'name': 'Gi0/0/0'}},
         'stack': {'7': [20], '20': [21]},
         'lldp': {'chassis': [4, 'aa0000000001'], 'name': 'p1.example.net', 'ports': {'3': [5, hx('Gi0/0/1'), '']},
                  'rem': [[3, 4, 'bb0000000002', 7, hx('545'), 'xe-0/0/0.0', 'pe1', []]]}}
# a Juniper PE: Junos numbers LLDP ports by ifIndex and sends the ifIndex as a «local» port ID
JUNOS = {'sys': {'name': 'pe1'}, 'ifs': {'545': {'name': 'xe-0/0/0'}, '546': {'name': 'xe-0/0/0.0'}, '600': {'name': 'jsrv.1'}},
         'stack': {'545': [546]},
         'lldp': {'chassis': [4, 'bb0000000002'], 'name': 'pe1', 'ports': {'545': [7, hx('545'), 'xe-0/0/0']},
                  'rem': [[545, 4, 'aa0000000001', 5, hx('Gi0/0/1'), 'to-pe1', 'p1', []]]}}


class Resolve(unittest.TestCase):
    cfg = {P1: {'name': 'P1'}, PE: {'name': 'PE1'}}
    on = {P1: {'enabled': True}, PE: {'enabled': True}}

    def test_cisco_port_number_is_not_the_ifindex(self):
        self.assertEqual(N.local_if(CISCO, 3), 7)                           # by the port ID name, not «ifIndex 3»
        self.assertEqual(N.local_if(JUNOS, 545), 545)

    def test_names_short_and_long(self):
        self.assertEqual(N._norm('GigabitEthernet0/0/1'), N._norm('Gi0/0/1'))
        self.assertEqual(N._norm('Port-channel1.2111'), 'po1.2111')
        self.assertEqual(N.remote_if(CISCO, 5, hx('GigabitEthernet0/0/1'), ''), 7)

    def test_one_link_from_both_ends_with_stacked_candidates(self):
        ls = N.lldp_links(self.cfg, {P1: CISCO, PE: JUNOS}, self.on)
        self.assertEqual(len(ls), 1)
        lk = ls[0]
        ends = {lk['a']: lk['a_ifs'], lk['b']: lk['b_ifs']}
        self.assertEqual(ends[P1], [7, 20, 21])
        self.assertEqual(ends[PE], [545, 546])
        self.assertEqual(lk['how'], 'lldp')

    def test_matched_by_name_or_management_address_when_no_chassis(self):
        j = json.loads(json.dumps(JUNOS))
        j['lldp']['chassis'] = [4, '']
        c = json.loads(json.dumps(CISCO))
        c['lldp']['rem'][0][2] = 'ffffffffffff'                              # unknown chassis: the name «pe1» decides
        self.assertEqual(len(N.lldp_links(self.cfg, {P1: c, PE: j}, self.on)), 1)
        c['lldp']['rem'][0][6] = 'unknown'
        c['lldp']['rem'][0][7] = [PE]                                        # nor the name: the management address
        j['lldp']['rem'] = []
        self.assertEqual(len(N.lldp_links(self.cfg, {P1: c, PE: j}, self.on)), 1)

    def test_snmp_off_and_unknown_neighbours(self):
        self.assertEqual(N.lldp_links(self.cfg, {P1: CISCO, PE: JUNOS}, {}), [])
        # the far end needs no SNMP of its own: P1's table names it (its interface stays unknown)
        ls = N.lldp_links(self.cfg, {P1: CISCO, PE: JUNOS}, {P1: {'enabled': True}})
        self.assertEqual([(lk['a_ifs'], lk['b_ifs'], lk['b_port']) for lk in ls], [([7, 20, 21], [], 'xe-0/0/0.0')])
        self.assertEqual(N.lldp_links({P1: {}}, {P1: CISCO}, self.on), [])  # a FortiAP, a server: not a device here

    def test_manual_beats_lldp_and_follows_a_moved_device(self):
        cfg = {P1: {'name': 'P1', 'links': {'21': ['198.51.100.7', 546]}}, PE: {'name': 'PE1', 'aliases': ['198.51.100.7']}}
        ls = N.fixed(cfg, {P1: CISCO, PE: JUNOS}, self.on)
        self.assertEqual([(lk['how'], lk['a'], lk['a_ifs'], lk['b'], lk['b_ifs']) for lk in ls], [('manual', P1, [21], PE, [546])])


class Build(unittest.TestCase):
    def test_issue_11_shared_juniper_addresses_make_no_links(self):
        """gorip96's River: every MX has jsrv.1 128.0.0.127/2 and em2.32768 192.168.1.1/24 — before 2.9.0 each pair of
        MX was a «subnet» link, so the PE stood one hop from the border, beside the P routers"""
        cfg = {ASBR: {'wan_ifs': [1], 'if_addrs': {'600': ['128.0.0.127/2'], '601': ['192.168.1.1/24'], '5': ['10.2.3.1/24']}},
               P1: {'if_addrs': {'7': ['10.2.3.2/24']}},
               PE: {'if_addrs': {'600': ['128.0.0.127/2'], '601': ['192.168.1.1/24']}}}
        t = T.build(cfg, [], [iface(ASBR, 1, 10, 10)], {ASBR, P1, PE})
        self.assertNotIn(frozenset((ASBR, PE)), links(t))
        self.assertIn(frozenset((ASBR, P1)), links(t))
        self.assertEqual(T.shared_addrs(cfg), {'128.0.0.127', '192.168.1.1'})
        # nor does the first MX own a quarter of the internet (128.0.0.0/2): a public address on a CE's interface
        # made that MX its neighbour
        t2 = T.build(cfg, [{'exporter': CE, 'iface': 9, 'addr': '140.82.1.1', 'records': 50}], [], {ASBR, P1, PE, CE})
        self.assertFalse([lk for lk in t2['links'] if CE in (lk['a'], lk['b'])])

    def test_management_role_makes_no_link(self):
        cfg = {ASBR: {'if_addrs': {'2': ['192.168.9.241/24']}, 'mgmt_ifs': [2]}, PE: {'if_addrs': {'3': ['192.168.9.248/24']}, 'mgmt_ifs': [3]}}
        self.assertEqual(T.build(cfg, [], [], {ASBR, PE})['links'], [])
        cfg[PE]['mgmt_ifs'] = []
        self.assertEqual(T.build(cfg, [], [], {ASBR, PE})['links'], [])     # one end is management: still no link

    def test_lldp_link_takes_the_busy_unit_and_river_gets_the_levels(self):
        cfg = {ASBR: {'wan_ifs': [1], 'if_addrs': {'5': ['10.2.3.1/30']}}, P1: {'if_addrs': {'3': ['10.2.3.2/30']}}, PE: {}, CE: {}}
        fixed = [{'a': P1, 'b': PE, 'a_ifs': [7, 20, 21], 'b_ifs': [545, 546], 'how': 'lldp', 'a_port': 'Gi0/0/1', 'b_port': 'xe-0/0/0'},
                 {'a': PE, 'b': CE, 'a_ifs': [550], 'b_ifs': [], 'how': 'manual', 'a_port': '', 'b_port': ''}]
        ifs = [iface(ASBR, 1, 9, 9), iface(P1, 21, 5000, 4000), iface(P1, 7, 0, 0), iface(PE, 546, 4000, 5000), iface(PE, 550, 10, 10), iface(CE, 2, 10, 10)]
        t = T.build(cfg, [], ifs, {ASBR, P1, PE, CE}, fixed=fixed)
        lk = links(t)[frozenset((P1, PE))]
        self.assertEqual({lk['a']: lk['a_if'], lk['b']: lk['b_if']}, {P1: 21, PE: 546})
        self.assertEqual(lk['evidence'], 'lldp')
        self.assertEqual(lk['state'], 'observed')
        self.assertEqual(links(t)[frozenset((PE, CE))]['evidence'], 'manual')
        self.assertEqual(hops(t), {T.INTERNET: 0, ASBR: 1, P1: 2, PE: 3, CE: 4})

    def test_only_the_far_interface_known(self):
        t = T.build({}, [], [iface(PE, 546, 10, 10)], {P1, PE}, fixed=[{'a': P1, 'b': PE, 'a_ifs': [], 'b_ifs': [546], 'how': 'lldp', 'a_port': '', 'b_port': ''}])
        lk = links(t)[frozenset((P1, PE))]
        self.assertEqual((lk['a'], lk['a_if'], lk['b_if']), (PE, 546, None))
        self.assertEqual(lk['state'], 'one_sided')


DEPLOY = {}


class Api(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        real_load = common.load_json
        for target, attr, val in ((common, 'UI_EXPORTERS', d + '/ui_exporters.json'), (snmp, 'SETTINGS', d + '/snmp.json'),
                                  (snmp, 'DATA', d + '/snmp_data.json'),
                                  (common, 'load_json', lambda name, default: {} if name == 'exporters.json' else real_load(name, default))):
            pt = mock.patch.object(target, attr, val)
            pt.start()
            self.addCleanup(pt.stop)
        for ip, name in ((P1, 'P1'), (PE, 'PE1'), (CE, 'CE1')):
            common.save_ui_exporter(ip, {'name': name, 'if_caps': {'7': [100.0, 100.0]}, 'aliases': ['198.51.100.' + ip[-1]]})

    def save_ifs(self, ip, items):
        return api.post_device_interfaces({'ip': ip, 'interfaces': items}, 'admin')

    def test_management_role_and_link_stored_once(self):
        self.save_ifs(P1, [{'index': 21, 'role': 'lan', 'peer': {'device': PE, 'index': '546'}}, {'index': 2, 'role': 'mgmt'}])
        c = common.load_exporters()
        self.assertEqual(c[P1]['links'], {'21': [PE, 546]})
        self.assertEqual(c[P1]['mgmt_ifs'], [2])
        # set again from the other end (to another interface): P1 forgets its copy of the link to PE 546
        self.save_ifs(PE, [{'index': 546, 'role': 'lan', 'peer': {'device': P1, 'index': '7'}}])
        c = common.load_exporters()
        self.assertEqual(c[PE]['links'], {'546': [P1, 7]})
        self.assertEqual(c[P1]['links'], {})
        # Settings → Devices shows it on both ends
        nb = api.device_neighbours({}, {})
        self.assertEqual(nb[P1][7][0]['peer'], PE)
        self.assertEqual(nb[PE][546][0]['peer_name'], 'P1')

    def test_refused(self):
        for peer in ({'device': P1, 'index': 1}, {'device': '203.0.113.9', 'index': 1}, {'device': PE, 'index': 'x'}):
            with self.assertRaises(api.BadRequest):
                self.save_ifs(P1, [{'index': 21, 'role': 'lan', 'peer': peer}])
        with self.assertRaises(api.BadRequest):
            self.save_ifs(P1, [{'index': 21, 'role': 'boss'}])

    def test_device_dialog_keeps_capacities_aliases_and_links(self):
        """before 2.9.0 saving the device dialog dropped the interface capacities and the earlier addresses"""
        self.save_ifs(P1, [{'index': 7, 'role': 'mgmt', 'cap_in': 100, 'cap_out': 100, 'peer': {'device': PE, 'index': ''}}])
        api.post_device_save({'ip': P1, 'name': 'P1 renamed'}, 'admin')
        c = common.load_exporters()[P1]
        self.assertEqual(c['name'], 'P1 renamed')
        self.assertEqual(c['if_caps'], {'7': [100.0, 100.0]})
        self.assertEqual(c['aliases'], ['198.51.100.2'])
        self.assertEqual(c['links'], {'7': [PE, None]})
        self.assertEqual(c['mgmt_ifs'], [7])

    def test_export_import_carry_roles_and_links(self):
        self.save_ifs(P1, [{'index': 2, 'role': 'mgmt', 'peer': {'device': PE, 'index': 546}}])
        ex = api.get_devices_export()['devices'][P1]
        self.assertEqual((ex['mgmt_ifs'], ex['links']), ([2], {'2': [PE, 546]}))
        self.assertEqual(api._device_extra(P1, ex)['links'], {'2': [PE, 546]})
        with self.assertRaises(api.BadRequest):
            api._device_extra(P1, {'links': {'2': ['not an address', 1]}})


if __name__ == '__main__':
    unittest.main()
