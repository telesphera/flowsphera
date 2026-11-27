"""2.12.6: the code review of 2.12.5 (SNMP multi-line texts, «Local / unknown» on Events, LLDP port names and port
subtypes, the browser cache after an upgrade — forum #102). Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import api  # noqa: E402
import neighbours  # noqa: E402
import snmp  # noqa: E402

hx = lambda t: t.encode().hex()
spaced = lambda b: ' '.join(f'{c:02X}' for c in b)


class SnmpText(unittest.TestCase):
    def test_multi_line_sysdescr_is_text(self):
        v = snmp.value('Hex-STRING', spaced(b'Cisco IOS Software, C900\r\nTechnical Support: x\r\nCopyright\r\n'))
        self.assertEqual(v, 'Cisco IOS Software, C900\nTechnical Support: x\nCopyright')

    def test_alias_with_tab_and_newline(self):
        self.assertEqual(snmp.value('Hex-STRING', spaced('uplink\tдо офісу\n'.encode())), 'uplink\tдо офісу')

    def test_binary_stays_hex(self):
        self.assertEqual(snmp.value('Hex-STRING', '00 1A 2B 3C 4D 5E'), '001a2b3c4d5e')
        self.assertEqual(snmp.value('Hex-STRING', spaced(b'ab\x01cd')), '6162016364')


class EventsUnknownCountry(unittest.TestCase):
    def test_unknown_matches_events_without_a_country(self):
        for v in ('unknown', '--', 'Unknown'):
            self.assertTrue(api._event_match({'country': ''}, {'k': 'country', 'v': v}))
            self.assertTrue(api._event_match({}, {'k': 'country', 'v': v}))
            self.assertFalse(api._event_match({'country': 'DE'}, {'k': 'country', 'v': v}))
        self.assertTrue(api._event_match({'country': 'DE'}, {'k': 'country', 'v': 'DE'}))


class LldpNames(unittest.TestCase):
    def test_cisco_forms_fold(self):
        for a, b in [('TenGigE0/0/0/1', 'Te0/0/0/1'), ('FortyGigE0/0/0/2', 'Fo0/0/0/2'), ('Serial0/1/0', 'Se0/1/0'),
                     ('Management1', 'Ma1'), ('Dialer1', 'Di1'), ('Multilink1', 'Mu1'), ('Virtual-Template1', 'Vt1'),
                     ('Bundle-Ether10', 'BE10')]:
            self.assertEqual(neighbours._norm(a), neighbours._norm(b), (a, b))

    def test_kept_apart(self):
        self.assertNotEqual(neighbours._norm('TwoGigabitEthernet1/0/1'), neighbours._norm('TwentyFiveGigE1/0/1'))
        self.assertNotEqual(neighbours._norm('sfp1'), neighbours._norm('sfp-sfpplus1'))


class LldpPortSubtypes(unittest.TestCase):
    IFS = {'7': {'name': 'port7', 'descr': 'Port 7'}, '8': {'name': 'port8', 'descr': 'Port 8'}}

    def dev(self, sub, pid, desc='to core'):
        return {'ifs': self.IFS, 'lldp': {'ports': {'7': [sub, hx(pid), desc]}}}

    def test_network_address_subtype_falls_back_to_the_port_number(self):
        # subtype 4 (network address) with ports numbered by ifIndex: 2.12.5 gave up (None)
        self.assertEqual(neighbours.local_if(self.dev(4, '\x01\xc0\x00\x02\x07'), 7), 7)
        self.assertEqual(neighbours.local_if(self.dev(2, 'slot1/7'), 7), 7)

    def test_a_name_that_is_no_interface_stays_unknown(self):
        # Cisco IOS: port ID = a name (5), port number ≠ ifIndex → unknown, not a guess
        self.assertIsNone(neighbours.local_if(self.dev(5, 'Gi1/0/9'), 7))
        self.assertIsNone(neighbours.local_if(self.dev(7, 'Gi1/0/9'), 7))
        self.assertEqual(neighbours.local_if(self.dev(5, 'port8'), 7), 8)


class FrontEndCache(unittest.TestCase):
    def test_index_names_the_stamp(self):
        body = b'<link rel="stylesheet" href="app.css">\n<script src="brand.js"></script>\n<script src="boot.js"></script>'
        out = api.stamp_index(body, '2.12.6.0-abc').decode()
        for f in ('app.css', 'brand.js', 'boot.js'):
            self.assertIn(f'"{f}?v=2.12.6.0-abc"', out)

    def test_real_index_gets_every_stamp(self):
        out = api.stamp_index(open(os.path.join(ROOT, 'web/index.html'), 'rb').read(), 'S').decode()
        self.assertEqual(out.count('?v=S'), 3)

    def test_stamp_follows_the_files(self):
        self.assertTrue(api.front_stamp().startswith(f'{api.VERSION}.{api.BUILD}-'))

    def test_boot_passes_it_to_app_js(self):
        js = open(os.path.join(ROOT, 'web/boot.js')).read()
        self.assertIn("'app.js' + (v ? '?v='", js)

    def test_front_end_revalidates(self):
        for ext in ('.html', '.js', '.css', '.json'):
            self.assertIn(ext, api.REVALIDATE)


if __name__ == '__main__':
    unittest.main()
