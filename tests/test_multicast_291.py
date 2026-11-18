"""(2.9.1, forum #55) Records to a multicast group or the broadcast are not Internet traffic: from an inside sender they
are 'internal' (the local network: mDNS, SSDP), from an outside one 'transit' (an ISP's IPTV), with or without WAN
interfaces marked. Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
os.environ['FT_GEOIP_DIR'] = tempfile.mkdtemp()
import collector as C  # noqa: E402
from common import is_group  # noqa: E402


def rec(src, dst, sport, dport, in_if=7, out_if=8, proto=17):
    return (src, dst, 1000, 2, proto, sport, dport, in_if, out_if, 0, '0.0.0.0', 0, '0.0.0.0', 0, 1_700_000_000, 1_700_000_001, 0, 1)


class Groups(unittest.TestCase):
    def test_is_group(self):
        for ip in ('224.0.0.251', '239.255.255.250', '233.1.2.3', 'ff02::fb', '255.255.255.255'):
            self.assertTrue(is_group(ip), ip)
        for ip in ('192.168.1.255', '8.8.8.8', '10.0.0.1', '2001:db8::1', 'junk', ''):
            self.assertFalse(is_group(ip), ip)


class Direction(unittest.TestCase):
    def row(self, f, wan=()):
        c = C.Collector(accounting=False, rate_limit=False)
        c.buf = []
        c.store(C.Exporter('192.0.2.1', {'wan_ifs': list(wan)}), f)
        r = c.buf[0]
        return r['dir'], r['int_ip'], r['ext_ip']

    def test_inside_sender_is_local(self):
        self.assertEqual(self.row(rec('192.168.1.5', '224.0.0.251', 5353, 5353)), ('internal', '192.168.1.5', '224.0.0.251'))
        self.assertEqual(self.row(rec('fe80::1', 'ff02::fb', 5353, 5353)), ('internal', 'fe80::1', 'ff02::fb'))
        self.assertEqual(self.row(rec('10.0.0.9', '255.255.255.255', 68, 67)), ('internal', '10.0.0.9', '255.255.255.255'))

    def test_out_through_wan_is_not_upload(self):
        # before 2.9.1: out_if in WAN made it 'up', so 224.x showed under Internet
        self.assertEqual(self.row(rec('192.168.1.5', '239.255.255.250', 1900, 1900, in_if=7, out_if=1), wan=[1])[0], 'internal')

    def test_outside_sender_is_transit(self):
        self.assertEqual(self.row(rec('80.81.82.83', '233.1.2.3', 1234, 5000, in_if=1, out_if=7), wan=[1]), ('transit', '80.81.82.83', '233.1.2.3'))
        self.assertEqual(self.row(rec('80.81.82.83', '233.1.2.3', 1234, 5000))[0], 'transit')

    def test_unicast_unchanged(self):
        self.assertEqual(self.row(rec('192.168.1.5', '8.8.8.8', 50000, 53))[0], 'up')
        self.assertEqual(self.row(rec('8.8.8.8', '192.168.1.5', 53, 50000), wan=[7])[0], 'down')


if __name__ == '__main__':
    unittest.main()
