"""(2.11.1) an interface named in FT_BIND / FT_WEB_BIND without its address yet (after a power cut the router comes up
after the server) is waited for, instead of the service exiting and systemd starting it again every 3 s."""
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402


class BindWait(unittest.TestCase):
    def setUp(self):
        self.old = common.iface_addrs, common.time.sleep
        common.time.sleep = lambda s: None
        self.addCleanup(self.restore)

    def restore(self):
        common.iface_addrs, common.time.sleep = self.old

    def addresses_after(self, n):
        calls = []

        def iface_addrs(dev):
            calls.append(dev)
            return [] if len(calls) <= n else ['127.0.0.2']
        common.iface_addrs = iface_addrs
        return calls

    def test_waits_for_the_address_then_listens(self):
        calls, logs, ticks = self.addresses_after(3), [], []
        out = common.open_listeners('lo', 0, socket.SOCK_DGRAM, log=logs.append, wait=60, tick=lambda: ticks.append(1))
        try:
            self.assertIn(('127.0.0.2', 'lo'), [(s.getsockname()[0], d) for s, d in out])
        finally:
            for s, _ in out:
                s.close()
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(ticks), 3)
        # said once while waiting, once when it is there — not a line per try
        self.assertEqual(len(logs), 2, logs)
        self.assertIn('lo has no IP address yet: waiting up to 60 s', logs[0])
        self.assertIn('lo: address there', logs[1])

    def test_gives_up_after_the_wait(self):
        self.addresses_after(10 ** 6)
        with self.assertRaises(common.NoAddress) as c:
            common.open_listeners('lo', 0, socket.SOCK_DGRAM, log=lambda m: None, wait=0)
        self.assertIsInstance(c.exception, OSError)      # callers catch OSError as before

    def test_no_wait_when_the_address_is_there(self):
        logs = []
        self.addresses_after(0)
        out = common.open_listeners('lo', 0, socket.SOCK_DGRAM, log=logs.append)
        for s, _ in out:
            s.close()
        self.assertEqual(logs, [])

    def test_listen_signature_still_none_without_address(self):
        self.addresses_after(10 ** 6)
        self.assertIsNone(common.listen_signature('lo'))


if __name__ == '__main__':
    unittest.main()
