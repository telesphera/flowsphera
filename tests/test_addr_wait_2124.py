"""(2.12.4, forum #84) The services restart for another address only; an address that only went away is waited out."""
import errno
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import common  # noqa: E402
from common import address_gone, address_moved  # noqa: E402

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
        self.assertIn('if address_moved(start, sig, ready):', api)
        self.assertIn('start=bound_signature(LISTENERS)', api)
        self.assertIn('os._exit(0)', api)
        self.assertNotIn('os._exit(3)', api)
        self.assertIn('if address_moved(self.listen_sig, sig, lambda a: bindable(a, PORT, socket.SOCK_DGRAM)):', col)
        self.assertIn('self.listen_sig = bound_signature(self.listeners)', col)


class LateAddress(unittest.TestCase):
    """the forum #84 log: Wi-Fi with IPv4 + global IPv6; one address refused with Errno 99 for minutes → 68 restarts"""
    PLAN = [('192.168.88.20', 'wlx0'), ('2600:db8::20', 'wlx0'), ('127.0.0.1', None), ('::1', None)]

    class Sock:
        def __init__(self, host): self.host = host; self.closed = False
        def close(self): self.closed = True
        def getsockname(self): return (self.host, 3030)

    def bound(self, refuse):
        def f(host, port, socktype, configure):
            if host in refuse:
                raise OSError(errno.EADDRNOTAVAIL, 'Cannot assign requested address')
            return self.Sock(host)
        return f

    def test_starts_on_the_addresses_that_bind(self):
        logs = []
        with mock.patch.object(common, 'bind_plan', return_value=self.PLAN), mock.patch.object(common, '_bound', self.bound({'2600:db8::20'})), \
                mock.patch.object(common.time, 'sleep'):
            out = common.open_listeners('wlx0', 3030, 1, log=logs.append, settle=0)
        self.assertEqual([s.host for s, _ in out], ['192.168.88.20', '127.0.0.1', '::1'])
        self.assertTrue(any('listening without 2600:db8::20' in m for m in logs), logs)
        self.assertEqual(common.bound_signature(out), sorted({'192.168.88.20', '127.0.0.1', '::1'}))

    def test_retries_before_settling(self):
        calls = []
        def bound(host, port, socktype, configure):
            calls.append(host)
            if host == '2600:db8::20' and calls.count(host) < 3:
                raise OSError(errno.EADDRNOTAVAIL, 'not yet')
            return self.Sock(host)
        with mock.patch.object(common, 'bind_plan', return_value=self.PLAN), mock.patch.object(common, '_bound', bound), \
                mock.patch.object(common.time, 'sleep'):
            out = common.open_listeners('wlx0', 3030, 1, log=lambda m: None, settle=60)
        self.assertIn('2600:db8::20', [s.host for s, _ in out])

    def test_no_interface_address_at_all_is_an_error_after_the_wait(self):
        with mock.patch.object(common, 'bind_plan', return_value=self.PLAN), \
                mock.patch.object(common, '_bound', self.bound({'192.168.88.20', '2600:db8::20'})), mock.patch.object(common.time, 'sleep'):
            with self.assertRaises(OSError) as cm:
                common.open_listeners('wlx0', 3030, 1, log=lambda m: None, wait=0, settle=0)
        self.assertEqual(cm.exception.errno, errno.EADDRNOTAVAIL)

    def test_other_errors_still_raise(self):
        def bound(host, port, socktype, configure):
            raise OSError(errno.EADDRINUSE, 'in use')
        with mock.patch.object(common, 'bind_plan', return_value=self.PLAN), mock.patch.object(common, '_bound', bound):
            with self.assertRaises(OSError) as cm:
                common.open_listeners('wlx0', 3030, 1, log=lambda m: None)
        self.assertEqual(cm.exception.errno, errno.EADDRINUSE)

    def test_tentative_and_dadfailed_are_left_out(self):
        out = json.dumps([{'addr_info': [
            {'family': 'inet', 'local': '192.168.88.20', 'scope': 'global'},
            {'family': 'inet6', 'local': '2600:db8::1', 'scope': 'global', 'tentative': True},
            {'family': 'inet6', 'local': '2600:db8::2', 'scope': 'global', 'dadfailed': True, 'tentative': True},
            {'family': 'inet6', 'local': '2600:db8::3', 'scope': 'global', 'deprecated': True},
            {'family': 'inet6', 'local': 'fe80::1', 'scope': 'link'}]}])
        with mock.patch.object(common.subprocess, 'run', return_value=mock.Mock(stdout=out)):
            self.assertEqual(common.iface_addrs('wlx0'), ['192.168.88.20', '2600:db8::3'])

    def test_watcher_waits_for_a_bindable_new_address(self):
        start = ['127.0.0.1', '192.168.88.20', '::1']
        now = start + ['2600:db8::20']
        self.assertFalse(address_moved(start, now, lambda a: False))     # still refused: no restart loop
        self.assertTrue(address_moved(start, now, lambda a: True))       # ready: restart and listen on it too

    def test_gone(self):
        start = ['127.0.0.1', '192.168.88.20', '::1']
        self.assertTrue(address_gone(start, None))
        self.assertTrue(address_gone(start, ['127.0.0.1', '::1']))
        self.assertFalse(address_gone(start, start + ['2600:db8::20']))
        self.assertFalse(address_gone(['127.0.0.1', '::1'], None))


if __name__ == '__main__':
    unittest.main()
