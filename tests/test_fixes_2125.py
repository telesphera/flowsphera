"""2.12.5: «Local / unknown» in a countries list filters (forum #98); the Cisco IOS-XE commands (a customer's Catalyst 9000).
Run: python -m unittest discover -s tests"""
import json
import os
import re
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


def scope(flt, t='all'):
    return api.scope({'f': [json.dumps(flt)], 'range': ['24h'], 't': [t]})


class UnknownCountry(unittest.TestCase):
    def test_unknown_is_no_country(self):
        for v in ('unknown', 'Unknown', '--'):
            where, p, _, _ = scope([{'k': 'country', 'v': v}])
            self.assertIn("country = ''", where, v)
            self.assertIn('country', p['_fcols'])

    def test_left_out(self):
        where, _, _, _ = scope([{'k': 'country', 'v': 'unknown', 'neg': True}])
        self.assertIn("NOT (country = '')", where)

    def test_a_country_stays_a_country(self):
        where, p, _, _ = scope([{'k': 'country', 'v': 'UA'}])
        self.assertIn('country = {f0:String}', where)
        self.assertEqual(p['f0'], 'UA')


class CiscoCommands(unittest.TestCase):
    """the IOS-XE lines a Catalyst 9000 on IOS-XE 17 takes: a record per direction, absolute times"""
    def test_snippet(self):
        js = open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8').read()
        a = js.index('const fnfRec =')
        b = js.index('\nconst juniper', a)
        code = js[a:b]
        self.assertNotIn('collect timestamp sys-uptime', code)   # (2.12.6) the IOS 15 hint names it, the commands do not
        self.assertIn('collect timestamp absolute first', code)
        self.assertIn("fnfRec('FT-REC', 'input', 'output')", code)
        self.assertIn("fnfRec('FT-REC-OUT', 'output', 'input')", code)
        self.assertTrue(re.search(r'ip flow monitor FT-MON-OUT\$\{smp\} output', code))
        self.assertTrue(re.search(r'ip flow monitor FT-MON\$\{smp\} input', code))


if __name__ == '__main__':
    unittest.main()
