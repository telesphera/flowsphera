"""(2.12.4, forum #84) The services restart for another address only; an address that only went away is waited out."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import address_moved  # noqa: E402

START = ['127.0.0.1', '192.168.88.20', '::1']


class AddressMoved(unittest.TestCase):
    def test_same(self):
        self.assertFalse(address_moved(START, list(START)))

    def test_gone_is_waited_out(self):
        # the router restarting / Wi-Fi reconnecting: the interface has no address (bind_plan raises → None)
        self.assertFalse(address_moved(START, None))
        self.assertFalse(address_moved(START, []))

    def test_part_gone_is_waited_out(self):
        self.assertFalse(address_moved(START, ['127.0.0.1', '::1']))

    def test_new_address_restarts(self):
        self.assertTrue(address_moved(START, ['127.0.0.1', '192.168.88.31', '::1']))

    def test_added_address_restarts(self):
        # a second address (IPv6 from the router) must get its own socket
        self.assertTrue(address_moved(START, START + ['2001:db8::20']))

    def test_no_start(self):
        self.assertTrue(address_moved(None, START))


class WatchersUseIt(unittest.TestCase):
    """both services decide with address_moved, not with != (the 2.12.3 rule restarted on every lost address)"""
    def test_sources(self):
        root = os.path.join(os.path.dirname(__file__), '..')
        api = open(os.path.join(root, 'api.py')).read()
        col = open(os.path.join(root, 'collector.py')).read()
        self.assertIn('if address_moved(start, sig):', api)
        self.assertIn('os._exit(0)', api)
        self.assertNotIn('os._exit(3)', api)
        self.assertIn('if address_moved(self.listen_sig, sig):', col)


if __name__ == '__main__':
    unittest.main()
