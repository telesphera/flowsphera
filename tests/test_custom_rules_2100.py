"""(2.10.0, forum #58) Own event rules: validation, hits above the threshold, the runner's windows and notifications,
the measure's SQL over scope() + src(), texts. Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
os.environ['FT_GEOIP_DIR'] = tempfile.mkdtemp()
import api  # noqa: E402
import custom_rules as CR  # noqa: E402
import detect  # noqa: E402

RULE = {'name': 'Backup server upload', 'sev': 'crit', 'filters': [{'k': 'ip', 'v': '10.0.0.5'}, {'k': 'device', 'v': '192.0.2.1'}],
        'measure': 'bytes', 'per': 'all', 'threshold': 500, 'minutes': 30}


class Validate(unittest.TestCase):
    def test_good(self):
        r = detect.custom_rules([RULE])[0]
        self.assertRegex(r['id'], r'^[0-9a-f]{8}$')
        self.assertEqual((r['on'], r['sev'], r['traffic'], r['threshold'], r['minutes']), (True, 'crit', 'internet', 500.0, 30))
        self.assertEqual(r['filters'][0], {'k': 'ip', 'v': '10.0.0.5', 'neg': False})
        again = detect.custom_rules([r])[0]
        self.assertEqual(again['id'], r['id'])                  # an id is kept

    def test_duplicate_id_renewed(self):
        a = detect.custom_rules([dict(RULE, id='abcdef01'), dict(RULE, id='abcdef01')])
        self.assertNotEqual(a[0]['id'], a[1]['id'])

    def test_bad(self):
        for bad in ({**RULE, 'name': ' '}, {**RULE, 'threshold': 0}, {**RULE, 'threshold': 'x'}, {**RULE, 'minutes': 15},
                    {**RULE, 'minutes': 2000}, {**RULE, 'measure': 'packets'}, {**RULE, 'per': 'country'},
                    {**RULE, 'filters': [{'k': 'nope', 'v': '1'}]}, {**RULE, 'filters': [{'k': 'ip', 'v': ''}]},
                    {**RULE, 'filters': [{'k': 'port', 'v': '1'}] * 11}):
            with self.assertRaises(ValueError, msg=str(bad)):
                detect.custom_rules([bad])
        with self.assertRaises(ValueError):
            detect.custom_rules([RULE] * (detect.CUSTOM_MAX + 1))

    def test_config_keeps_rules(self):
        cfg = detect.validate({'custom': [RULE]})
        self.assertEqual(len(cfg['custom']), 1)
        self.assertEqual(detect.validate({})['custom'], [])
        self.assertIn('custom', detect.KINDS)


class Hits(unittest.TestCase):
    def test_threshold_and_ignore(self):
        r = detect.custom_rules([dict(RULE, per='host', measure='flows', threshold=100)])[0]
        ign = detect.Ignore(['10.0.0.9'])
        h = CR.hits_of(r, [('10.0.0.7', 150.0), ('10.0.0.9', 900.0), ('10.0.0.8', 99.0)], ign)
        self.assertEqual([(x['key'], x['src'], x['value']) for x in h], [(f"{r['id']}>10.0.0.7", '10.0.0.7', 150.0)])
        self.assertEqual(h[0]['exporter'], '192.0.2.1')              # the rule's device
        self.assertEqual(h[0]['info']['sev'], 'crit')

    def test_bytes_in_mb(self):
        r = detect.custom_rules([RULE])[0]
        self.assertEqual(CR.hits_of(r, [('', 499e6)]), [])
        self.assertEqual(len(CR.hits_of(r, [('', 500e6)])), 1)


class Text(unittest.TestCase):
    def row(self, src='', value=7.5e8, measure='bytes'):
        r = detect.custom_rules([dict(RULE, measure=measure)])[0]
        return {'kind': 'custom', 'src': src, 'dst': '', 'port': 0, 'value': value, 'exporter': '192.0.2.1', 'hits': 1,
                'info': CR.hits_of(r, [(src, value)])[0]['info']}

    def test_describe(self):
        t, x = detect.describe(self.row())
        self.assertEqual(t, 'Backup server upload')
        self.assertIn('750.0 MB in 30 min', x)
        self.assertIn('500.0 MB', x)
        t, x = detect.describe(self.row('10.0.0.7', 1234, 'flows'))
        self.assertTrue(x.startswith('10.0.0.7: 1,234 flows'), x)

    def test_filter_of(self):
        self.assertEqual(detect._filter_of(self.row('10.0.0.7')), ('ip', '10.0.0.7'))
        self.assertEqual(detect._filter_of(self.row()), ('ip', '10.0.0.5'))


class Runner(unittest.TestCase):
    def setUp(self):
        CR.STATE = os.path.join(tempfile.mkdtemp(), 'st.json')

    def cfg(self, rules, on=True):
        c = detect.defaults()
        c['custom'] = detect.custom_rules(rules)
        c['kinds']['custom']['on'] = on
        return c

    def test_windows_store_and_notify(self):
        now = 1_800_000_000
        calls, stored = [], []
        meas = lambda r, t0, t1, top: (calls.append((t0, t1)), [('', 6e8)])[1]       # noqa: E731

        def store(hits, t0, t1, new):
            stored.append((t0, t1, hits))
            new += [{'kind': 'custom', 'info': hits[0]['info']}] if t0 == stored[0][0] else []
            return len(hits)
        run = CR.Runner(meas, log=lambda m: None)
        push = mock.MagicMock()
        run.notifier = mock.MagicMock(push=push)
        with mock.patch.object(detect, 'load_config', return_value=self.cfg([RULE])), mock.patch.object(detect, 'store', store):
            n = run.tick(now)
        last = (now - CR.LAG) // CR.WINDOW * CR.WINDOW
        self.assertEqual(n, CR.BACK // CR.WINDOW)                    # an hour back at the first start
        self.assertEqual(calls[-1], (last - 1800, last))              # the rule's 30 minutes up to the window's end
        self.assertEqual(run.state()['done'], last)
        push.assert_called_once()
        self.assertEqual(push.call_args[0][0][0]['sev'], 'crit')
        with mock.patch.object(detect, 'load_config', return_value=self.cfg([RULE])), mock.patch.object(detect, 'store', store):
            self.assertEqual(run.tick(now + 60), 0)                 # nothing new to check

    def test_off_moves_on(self):
        run = CR.Runner(lambda *a: self.fail('measured while off'), log=lambda m: None)
        with mock.patch.object(detect, 'load_config', return_value=self.cfg([RULE], on=False)):
            self.assertEqual(run.tick(1_800_000_000), 0)
        self.assertTrue(run.state()['done'])

    def test_bad_rule_does_not_stop_others(self):
        logs = []

        def meas(r, t0, t1, top):
            if r['name'] == 'bad':
                raise api.BadRequest('no network named x')
            return [('', 6e8)]
        run = CR.Runner(meas, log=logs.append)
        with mock.patch.object(detect, 'load_config', return_value=self.cfg([dict(RULE, name='bad'), RULE])), \
                mock.patch.object(detect, 'store', lambda h, a, b, new: len(h)):
            self.assertEqual(run.tick(1_800_000_000), CR.BACK // CR.WINDOW)
        self.assertTrue(any('bad' in m for m in logs))


class Measure(unittest.TestCase):
    def sql(self, **kw):
        r = detect.custom_rules([dict(RULE, **kw)])[0]
        seen = {}

        def ch(sql, p, fmt=None, settings=None):
            seen['sql'], seen['p'] = sql, p
            return [{'h': '10.0.0.7', 'v': '7'}]
        with mock.patch.object(api, 'ch', ch):
            t1 = int(api.time.time()) // 600 * 600
            out = api.custom_measure(r, t1 - 1800, t1)
        return seen['sql'], out

    def test_all(self):
        sql, out = self.sql()
        self.assertRegex(sql, r"^SELECT '' AS h, sum\(bytes\) AS v FROM .* WHERE ")
        self.assertEqual(out, [('10.0.0.7', 7.0)])

    def test_per_host_addresses(self):
        sql, _ = self.sql(per='host', measure='addresses', filters=[{'k': 'country', 'v': 'RU'}])
        self.assertRegex(sql, r'^SELECT int_ip AS h, uniqExact\(ext_ip\) AS v FROM .* GROUP BY h ORDER BY v DESC LIMIT 50$')


if __name__ == '__main__':
    unittest.main()
