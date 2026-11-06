"""2.3.0 (core 1.9.0): FortiGate application names. The data records carry only APPLICATION_ID (95: engine 20,
Fortinet's enterprise number, the app); the names come in an options table (95 -> 96 name, 372 category), slowly.
The core names a record once its id was named; the collector keeps the names across restarts (app_names.json).
Run: python -m unittest discover -s tests"""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
import ftcore  # noqa: E402

NEW = hasattr(ftcore.Decoder, 'app_names_json')


def fs(fid, payload):
    pad = (-(len(payload) + 4)) % 4
    return struct.pack('!HH', fid, len(payload) + 4 + pad) + payload + b'\0' * pad


def v9(*sets, seq=1):
    return struct.pack('!HHIIII', 9, len(sets), 0, 0, seq, 1) + b''.join(sets)


def app_id(n):
    return bytes([20]) + struct.pack('!II', 12356, n)


# FortiOS 7.4 (our 40F): data template with 95:9, options template 257 = scope 1:2 + 95:9, 96:64, 94:64, 372:32
DATA_TPL = fs(0, struct.pack('!HH', 258, 4) + b''.join(struct.pack('!HH', t, ln) for t, ln in [(8, 4), (12, 4), (1, 4), (95, 9)]))
OPT_TPL = fs(1, struct.pack('!HHH', 257, 4, 16) + struct.pack('!HH', 1, 2) + b''.join(struct.pack('!HH', t, ln) for t, ln in [(95, 9), (96, 64), (94, 64), (372, 32)]))


def names(*apps):
    out = b''
    for n, name, cat in apps:
        out += b'\0\1' + app_id(n) + name.encode().ljust(64, b'\0') + b'desc'.ljust(64, b'\0') + cat.encode().ljust(32, b'\0')
    return fs(257, out)


def rec(n, nbytes=1000):
    return fs(258, bytes([10, 0, 0, 5, 8, 8, 8, 8]) + struct.pack('!I', nbytes) + app_id(n))


def flows(dec, pkt):
    return [(f[20], f[16]) for f in dec.packet('192.0.2.1', pkt, 1.0e9, False)]


@unittest.skipUnless(NEW, 'needs core 1.9.0 (application names)')
class FortiGate(unittest.TestCase):
    def test_named_after_the_options_and_after_a_restart(self):
        d = ftcore.Decoder(rate=0)
        self.assertEqual(flows(d, v9(DATA_TPL, OPT_TPL, rec(0xdd70))), [('', (12356 << 32) | 0xdd70)])   # no name yet
        self.assertEqual(flows(d, v9(names((0xdd70, 'Microsoft.Outlook', 'Email'), (0x3f43, 'HTTPS.BROWSER', 'Web.Client')), rec(0x3f43))),
                         [('HTTPS.BROWSER', (12356 << 32) | 0x3f43)])
        saved = json.loads(d.app_names_json())
        self.assertEqual(saved['192.0.2.1'][app_id(0xdd70).hex()], ['Microsoft.Outlook', 'Email'])
        # a restart: templates and names loaded from the files -> the next record is named at once
        d2 = ftcore.Decoder(rate=0)
        d2.load_templates('192.0.2.1', json.dumps(json.loads(d.templates_json())['192.0.2.1']))
        self.assertEqual(d2.load_app_names('192.0.2.1', json.dumps(saved['192.0.2.1'])), 2)
        self.assertEqual(flows(d2, v9(rec(0xdd70))), [('Microsoft.Outlook', (12356 << 32) | 0xdd70)])
        self.assertEqual(flows(d2, v9(rec(0))), [('', 12356 << 32)])          # not identified by the firewall

    def test_broken_saved_names_are_skipped(self):
        d = ftcore.Decoder(rate=0)
        n = d.load_app_names('192.0.2.1', json.dumps({'zz': ['x', ''], 'abc': ['odd', ''], app_id(1).hex(): ['', ''],
                                                      app_id(2).hex(): ['Good.App', 'Cat']}))
        self.assertEqual(n, 1)
        with self.assertRaises(ValueError):
            d.load_app_names('192.0.2.1', '{not json')


class Collector(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        import collector as C
        tmp = tempfile.mkdtemp()
        C.APP_NAMES_FILE = tmp + '/app_names.json'
        c = C.Collector(rate_limit=False)
        if not NEW:
            c.save_app_names(); c.load_app_names()              # an older core: both do nothing
            self.assertFalse(os.path.exists(C.APP_NAMES_FILE))
            return
        for p in (v9(DATA_TPL, OPT_TPL), v9(names((7, 'Zoom', 'Collaboration')))):
            c.dec.packet('192.0.2.1', p, 1.0e9, False)
        c.save_app_names()
        with open(C.APP_NAMES_FILE) as f:
            self.assertEqual(json.load(f)['192.0.2.1'][app_id(7).hex()], ['Zoom', 'Collaboration'])
        c2 = C.Collector(rate_limit=False)
        c2.load_app_names()
        self.assertIn(app_id(7).hex(), json.loads(c2.dec.app_names_json())['192.0.2.1'])


if __name__ == '__main__':
    unittest.main()
