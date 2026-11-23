"""(2.12.4, forum #89) Through device: the outside addresses are the biggest few of EACH WAN port (as the inside hosts
are of each inside port) — one limit for all ports left a quieter WAN with its dot alone."""
import os
import re
import unittest

SRC = open(os.path.join(os.path.dirname(__file__), '..', 'api.py')).read()
BODY = SRC[SRC.index('def api_devmap('):SRC.index('\ndef ', SRC.index('def api_devmap(') + 10)]


class PerPort(unittest.TestCase):
    def test_outside_limited_by_port(self):
        q = BODY[BODY.index('outside = ch('):]
        q = q[:q.index('fmt=')]
        self.assertRegex(q, r'ORDER BY v DESC LIMIT \{\{n:UInt8\}\} BY iface LIMIT \d+')

    def test_inside_limited_by_port(self):
        self.assertTrue(re.search(r'LIMIT \{\{n:UInt8\}\} BY iface LIMIT \d+', BODY[BODY.index('inside = ch('):BODY.index('outside = ch(')]))


if __name__ == '__main__':
    unittest.main()
