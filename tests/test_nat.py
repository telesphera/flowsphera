"""Records arriving through destination NAT: the inside host is the translated destination (MikroTik's replies to
masqueraded hosts, a FortiGate VIP), the public address goes to nat_ip — as for outgoing records.
Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
os.environ['FT_GEOIP_DIR'] = tempfile.mkdtemp()          # no GeoIP needed here
import collector as C  # noqa: E402

PUB, HOST, PEER = '81.20.30.5', '10.20.0.5', '198.51.100.7'


def rec(src, dst, in_if, out_if, nat_src='0.0.0.0', nat_sport=0, nat_dst='0.0.0.0', nat_dport=0):
    # (src, dst, bytes, packets, proto, sport, dport, in_if, out_if, obs, nat_src, nat_sport, nat_dst, nat_dport, start, end, app_tag, rate)
    return (src, dst, 1000, 2, 6, 443 if src == PEER else 50000, 50000 if src == PEER else 443, in_if, out_if, 0,
            nat_src, nat_sport, nat_dst, nat_dport, 1_700_000_000, 1_700_000_001, 0, 1)


class DestinationNat(unittest.TestCase):
    def setUp(self):
        self.c = C.Collector(accounting=False, rate_limit=False)
        self.e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [PUB]})

    def row(self, f):
        self.c.buf = []
        self.c.store(self.e, f)
        r = self.c.buf[0]
        return r['dir'], r['int_ip'], r['int_port'], r['ext_ip'], r['nat_ip'], r['nat_port']

    def test_reply_to_masqueraded_host(self):
        # in on WAN to the router's public address, translated to the inside host
        self.assertEqual(self.row(rec(PEER, PUB, 2, 7, nat_dst=HOST, nat_dport=50001)), ('down', HOST, 50001, PEER, PUB, 50000))

    def test_outgoing_unchanged(self):
        self.assertEqual(self.row(rec(HOST, PEER, 7, 2, nat_src=PUB, nat_sport=50000)), ('up', HOST, 50000, PEER, PUB, 50000))

    def test_already_inside_destination_unchanged(self):
        # FortiGate style: the reply's destination is the inside host already, the public one in the NAT field
        self.assertEqual(self.row(rec(PEER, HOST, 2, 7, nat_dst=PUB, nat_dport=50000)), ('down', HOST, 50000, PEER, PUB, 50000))

    def test_traffic_to_the_router_itself(self):
        self.assertEqual(self.row(rec(PEER, PUB, 2, 0, nat_dst=PUB, nat_dport=50000)), ('down', PUB, 50000, PEER, PUB, 50000))


class NatBehindProvider(unittest.TestCase):
    """(2.12.1, forum #71) a WAN behind the provider's NAT: the router's WAN address is private (192.168.4.2). MikroTik's
    reply to a masqueraded host arrives to that address with the inside host in the NAT field: the inside host gets the
    download, not the router. FortiGate's reply already names the inside host: unchanged."""
    WAN_ADDR, ISP_NAT = '192.168.4.2', '100.64.7.9'

    def row(self, e, f):
        c = C.Collector(accounting=False, rate_limit=False)
        c.buf = []
        c.store(e, f)
        r = c.buf[0]
        return r['dir'], r['int_ip'], r['int_port'], r['ext_ip'], r['nat_ip'], r['nat_port']

    def test_reply_to_masqueraded_host_through_a_private_wan(self):
        for cfg in ({'wan_ifs': [2], 'public_ips': [self.WAN_ADDR]},             # named as its own address
                    {'wan_ifs': [2], 'if_addrs': {'2': [self.WAN_ADDR + '/24']}},  # typed for the WAN interface
                    {'wan_ifs': [2]}):                                             # the address it exports from
            e = C.Exporter(self.WAN_ADDR if cfg == {'wan_ifs': [2]} else '192.0.2.1', cfg)
            self.assertEqual(self.row(e, rec(PEER, self.WAN_ADDR, 2, 7, nat_dst=HOST, nat_dport=50001)),
                             ('down', HOST, 50001, PEER, self.WAN_ADDR, 50000), cfg)

    def test_cgnat_wan_address(self):
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [self.ISP_NAT]})
        self.assertEqual(self.row(e, rec(PEER, self.ISP_NAT, 2, 7, nat_dst=HOST, nat_dport=50001)), ('down', HOST, 50001, PEER, self.ISP_NAT, 50000))

    def test_fortigate_reply_naming_the_inside_host_unchanged(self):
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [self.WAN_ADDR]})
        self.assertEqual(self.row(e, rec(PEER, HOST, 2, 7, nat_dst=self.WAN_ADDR, nat_dport=50000)), ('down', HOST, 50000, PEER, self.WAN_ADDR, 50000))

    def test_router_own_traffic_stays_the_router(self):
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [self.WAN_ADDR]})
        self.assertEqual(self.row(e, rec(PEER, self.WAN_ADDR, 2, 0)), ('down', self.WAN_ADDR, 50000, PEER, '', 0))

    def test_masquerade_address_learned_from_outgoing_records(self):
        # (2.12.1) nobody told FlowSphera the router's WAN address: its outgoing records show it (the translated source)
        c = C.Collector(accounting=False, rate_limit=False)
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2]})
        c.buf = []
        c.store(e, rec(PEER, self.WAN_ADDR, 2, 7, nat_dst=HOST, nat_dport=50001))      # before anything was learned
        self.assertEqual(c.buf[-1]['int_ip'], self.WAN_ADDR)
        c.store(e, rec(HOST, PEER, 7, 2, nat_src=self.WAN_ADDR, nat_sport=50001))      # the inside host's upload
        c.store(e, rec(PEER, self.WAN_ADDR, 2, 7, nat_dst=HOST, nat_dport=50001))
        self.assertEqual((c.buf[-1]['dir'], c.buf[-1]['int_ip'], c.buf[-1]['nat_ip']), ('down', HOST, self.WAN_ADDR))

    def test_learned_address_keeps_the_fortigate_case(self):
        c = C.Collector(accounting=False, rate_limit=False)
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2]})
        c.buf = []
        c.store(e, rec(HOST, PEER, 7, 2, nat_src=self.WAN_ADDR, nat_sport=50000))
        c.store(e, rec(PEER, HOST, 2, 7, nat_dst=self.WAN_ADDR, nat_dport=50000))       # destination already the host
        self.assertEqual((c.buf[-1]['int_ip'], c.buf[-1]['nat_ip']), (HOST, self.WAN_ADDR))

    def test_private_destination_not_the_router_unchanged(self):
        # an inside host as the destination and another inside address in the NAT field: not ours to swap
        e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [self.WAN_ADDR]})
        self.assertEqual(self.row(e, rec(PEER, '10.20.0.9', 2, 7, nat_dst=HOST, nat_dport=50001)), ('down', '10.20.0.9', 50000, PEER, HOST, 50001))


if __name__ == '__main__':
    unittest.main()


class TunnelOwnPackets(unittest.TestCase):
    """(1.15.2) hap_ac2 (RouterOS) on prod: the outer GRE packets it sends to the far end of a tunnel were recorded as
    entering through the tunnel interface (in_if 11 → ether1, proto 47, from its own public address) — the tunnel's
    «in» was 167 % of its counters. They come from the device itself now."""
    def setUp(self):
        self.c = C.Collector(accounting=False, rate_limit=False)
        self.e = C.Exporter('192.0.2.1', {'wan_ifs': [2], 'public_ips': [PUB], 'local_if': 9})   # hap_ac2: bridge as «local»

    def store(self, src, dst, in_if, out_if, proto):
        self.c.buf = []
        self.c.store(self.e, (src, dst, 5000, 4, proto, 0, 0, in_if, out_if, 0, '0.0.0.0', 0, '0.0.0.0', 0, 1_700_000_000, 1_700_000_001, 0, 1))
        r = self.c.buf[0]
        return r['in_if'], r['out_if'], r['dir']

    def test_own_gre_comes_from_the_device(self):
        self.assertEqual(self.store(PUB, PEER, 11, 2, 47), (0, 2, 'up'))
        self.assertEqual(self.store(PUB, PEER, 11, 2, 50), (0, 2, 'up'))            # IPsec ESP too

    def test_others_unchanged(self):
        self.assertEqual(self.store(PEER, PUB, 2, 0, 47), (2, 0, 'down'))           # the far end's GRE arriving
        self.assertEqual(self.store(HOST, PEER, 11, 2, 47), (11, 2, 'up'))          # an inside host's GRE, routed
        self.assertEqual(self.store(PUB, PEER, 11, 2, 6), (11, 2, 'up'))            # not a tunnel protocol
