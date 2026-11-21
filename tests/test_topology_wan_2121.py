"""(2.12.1, GitHub issue #17) Path analysis: a WAN interface leads to the internet — the records never make it face
another device; and a conversation recorded by two devices never links an interface whose neighbour is already known
(shared subnet, LLDP, by hand) to some other device. Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import topology as T  # noqa: E402

ASBR, PE, P = '192.0.2.10', '192.0.2.20', '192.0.2.30'
WAN, CORE = 10, 11            # ASBR: the exchange-point interface (role WAN), the core interface
CUST, UP = 5, 6               # PE: a customer interface, the core interface


def near(dev, iface, addr, n=50):
    return {'exporter': dev, 'iface': iface, 'addr': addr, 'records': n}


def iface(dev, i, out=1000, inb=1000):
    return {'exporter': dev, 'iface': i, 'out_bytes': out, 'in_bytes': inb, 'up': 0, 'down': 0, 'internal': 0}


def pair(n=100):
    # one download: enters the ASBR from the exchange point, leaves it to the core; enters the PE from the core and
    # leaves it to the customer (the P router between them exports nothing of it)
    return {'a': ASBR, 'ai': WAN, 'ao': CORE, 'b': PE, 'bi': UP, 'bo': CUST, 'n': n}


def links(topo):
    return {(frozenset((lk['a'], lk['b']))): lk for lk in topo['links']}


def ends(lk):
    return {lk['a']: lk['a_if'], lk['b']: lk['b_if']}


class WanInterface(unittest.TestCase):
    def cfg(self, **asbr):
        return {ASBR: {'name': 'asbr', 'wan_ifs': [WAN], 'public_ips': ['203.0.113.1'], **asbr},
                PE: {'name': 'pe', 'public_ips': ['198.51.100.1']}, P: {'name': 'p'}}

    ifs = [iface(ASBR, WAN), iface(ASBR, CORE), iface(PE, UP), iface(PE, CUST)]
    # the PE's own address arrives over the internet at the ASBR's exchange-point interface
    seen = [near(ASBR, WAN, '198.51.100.1')]

    def test_own_address_over_the_internet_is_no_neighbour(self):
        t = T.build(self.cfg(), self.seen, self.ifs, {ASBR, PE})
        ls = links(t)
        self.assertNotIn(frozenset((ASBR, PE)), ls)
        self.assertEqual(ls[frozenset((ASBR, T.INTERNET))]['a_if'], WAN)

    def test_shared_conversation_never_ties_the_wan_interface(self):
        t = T.build(self.cfg(), self.seen, self.ifs, {ASBR, PE}, [pair()])
        lk = links(t).get(frozenset((ASBR, PE)))
        if lk is not None:      # the core reading may stay; never the exchange point nor the customer interface
            self.assertEqual(ends(lk), {ASBR: CORE, PE: UP})
        self.assertIn(frozenset((ASBR, T.INTERNET)), links(t))

    def test_interface_already_linked_by_hand_takes_no_other_neighbour(self):
        fixed = [{'a': ASBR, 'b': P, 'a_ifs': [CORE], 'b_ifs': [1], 'how': 'manual'},
                 {'a': PE, 'b': P, 'a_ifs': [UP], 'b_ifs': [2], 'how': 'manual'}]
        t = T.build(self.cfg(), self.seen, self.ifs, {ASBR, PE, P}, [pair()], fixed=fixed)
        ls = links(t)
        self.assertNotIn(frozenset((ASBR, PE)), ls)
        self.assertEqual(ends(ls[frozenset((ASBR, P))])[ASBR], CORE)
        self.assertEqual(ends(ls[frozenset((PE, P))])[PE], UP)

    def test_wan_interface_facing_a_device_by_subnet_still_links(self):
        cfg = self.cfg(if_addrs={str(WAN): ['10.9.9.1/30']})
        cfg[PE]['if_addrs'] = {str(UP): ['10.9.9.2/30']}
        ls = links(T.build(cfg, [], self.ifs, {ASBR, PE}))
        self.assertEqual(ends(ls[frozenset((ASBR, PE))]), {ASBR: WAN, PE: UP})
        self.assertNotIn(frozenset((ASBR, T.INTERNET)), ls)    # the internet is beyond the PE


if __name__ == '__main__':
    unittest.main()
