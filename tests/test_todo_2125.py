"""2.12.5: defects found in the IP Sphera copy review (2026-11-24) — interface names that collided after shortening
(TwoGigabitEthernet / TwentyFiveGigE on a Catalyst 9300, MikroTik sfp1 / sfp-sfpplus1), an LLDP port number taken as
an ifIndex although the device names its ports, SNMP Hex-STRING values decoded as text when they are bytes, a walk the
device broke part way passed as whole, and an unreadable INTEGER read as 0. Run: python -m unittest discover -s tests"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ifcounters  # noqa: E402
import neighbours as N  # noqa: E402
import snmp  # noqa: E402

hx = lambda t: t.encode().hex()


def ifs(*names):
    return {str(i + 1): {'name': n} for i, n in enumerate(names)}


class Names(unittest.TestCase):
    def test_25g_and_2_5g_ports_stay_apart(self):
        self.assertNotEqual(N._norm('TwoGigabitEthernet1/0/1'), N._norm('TwentyFiveGigE1/0/1'))
        d = ifs('TwoGigabitEthernet1/0/1', 'TwentyFiveGigE1/0/1')
        self.assertEqual(N._by_name(d, 'Tw1/0/1'), 1)
        self.assertEqual(N._by_name(d, 'Twe1/0/1'), 2)
        self.assertEqual(N._by_name(d, 'twentyfivegige1/0/1'), 2)

    def test_short_and_long_cisco_forms(self):
        for a, b in (('GigabitEthernet0/0/1', 'Gi0/0/1'), ('TenGigabitEthernet1/1/1', 'Te1/1/1'),
                     ('Port-channel1.2111', 'Po1.2111'), ('Ethernet 1', 'Ethernet1'), ('Ethernet1/1', 'Eth1/1'),
                     ('HundredGigE1/0/49', 'Hu1/0/49')):
            self.assertEqual(N._norm(a), N._norm(b), (a, b))

    def test_mikrotik_names_are_kept_whole(self):
        self.assertNotEqual(N._norm('sfp1'), N._norm('sfp-sfpplus1'))
        d = ifs('sfp1', 'sfp-sfpplus1', 'ether1')
        self.assertEqual(N._by_name(d, 'sfp-sfpplus1'), 2)
        self.assertEqual(N._by_name(d, 'sfp1'), 1)
        self.assertEqual(N._norm('xe-0/0/0'), N._norm('xe0/0/0'))


class LocalPort(unittest.TestCase):
    def dev(self, ports):
        return {'ifs': ifs('Gi1/0/1', 'Gi1/0/2', 'Gi1/0/3', 'Gi1/0/4', 'Gi1/0/5'), 'lldp': {'ports': ports}}

    def test_named_port_without_an_interface_is_not_guessed_by_number(self):
        """Cisco IOS: LLDP port 3 named «Gi1/0/9» (no such interface here) is NOT ifIndex 3"""
        self.assertIsNone(N.local_if(self.dev({'3': [5, hx('Gi1/0/9'), '']}), 3))

    def test_named_port_found_by_name(self):
        self.assertEqual(N.local_if(self.dev({'3': [5, hx('GigabitEthernet1/0/5'), '']}), 3), 5)

    def test_no_entry_keeps_the_number(self):
        """FortiOS has no lldpLocPortTable: its LLDP port 5 is ifIndex 5 (a FortiWiFi 40F, 24.11)"""
        self.assertEqual(N.local_if(self.dev({}), 5), 5)

    def test_mac_only_entry_keeps_the_number(self):
        self.assertEqual(N.local_if(self.dev({'4': [3, '704ca593c340', '']}), 4), 4)


class Values(unittest.TestCase):
    def test_mac_stays_hex(self):
        self.assertEqual(snmp.value('Hex-STRING', '70 4C A5 93 C3 40'), '704ca593c340')
        self.assertEqual(snmp.value('Hex-STRING', '00 11 22 33 44 55'), '001122334455')

    def test_non_ascii_text_is_decoded(self):
        h = ' '.join(f'{b:02X}' for b in 'Аплінк до ядра'.encode())
        self.assertEqual(snmp.value('Hex-STRING', h), 'Аплінк до ядра')

    def test_raw_unchanged(self):
        self.assertEqual(snmp.value('Hex-STRING', '70 4C A5', raw=True), '704ca5')

    def test_unreadable_integer_is_none(self):
        self.assertIsNone(snmp.value('INTEGER', 'garbage'))
        self.assertEqual(snmp.value('INTEGER', '0'), 0)
        self.assertEqual(snmp.value('INTEGER', 'up(1)'), 1)

    def test_counters_without_a_value_are_not_rows(self):
        found = {1: {'in_octets': None, 'out_octets': 5}, 2: {'in_octets': 7, 'out_octets': 9}}
        self.assertEqual([r['if_index'] for r in ifcounters.rows('192.0.2.1', found, 0)], [2])


class BrokenWalk(unittest.TestCase):
    def session(self):
        s = snmp.Session.__new__(snmp.Session)
        s.target, s.raw, s.env, s.partial = 'udp:192.0.2.1:161', False, {}, []
        return s

    def test_rows_then_error_is_kept_and_reported(self):
        out = '.1.3.6.1.2.1.4.24.4.1.1.1 = INTEGER: 1\n.1.3.6.1.2.1.4.24.4.1.1.2 = INTEGER: 2\n'
        r = subprocess.CompletedProcess([], 1, out, 'Error: OID not increasing: .1.3.6.1.2.1.4.24.4.1.1.2\n')
        s = self.session()
        with mock.patch.object(snmp.subprocess, 'run', return_value=r), mock.patch('builtins.print') as pr:
            rows = s.run('snmpbulkwalk', [], ['1.3.6.1.2.1.4.24.4'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(s.partial, ['1.3.6.1.2.1.4.24.4'])
        self.assertIn('incomplete', pr.call_args[0][0])

    def test_clean_walk_is_not_partial(self):
        r = subprocess.CompletedProcess([], 0, '.1.3.6.1.2.1.1.5.0 = STRING: "x"\n', '')
        s = self.session()
        with mock.patch.object(snmp.subprocess, 'run', return_value=r):
            s.run('snmpget', [], ['1.3.6.1.2.1.1.5.0'])
        self.assertEqual(s.partial, [])


if __name__ == '__main__':
    unittest.main()
