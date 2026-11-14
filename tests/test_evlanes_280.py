"""2.8.0 (GitHub #9): the Events page's «By host» lanes — detect.lanes and /api/alerts?hosts=N.
Run: python -m unittest discover -s tests"""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import detect  # noqa: E402

T1 = int(datetime.datetime(2026, 11, 14, 12, tzinfo=datetime.timezone.utc).timestamp())
T0 = T1 - 86400


def at(h, m=0):
    return (datetime.datetime(2026, 11, 14, h, m, tzinfo=datetime.timezone.utc)).strftime('%Y-%m-%d %H:%M:%S')


def ev(ip, kind, sev, first, last=None, hits=1, **kw):
    return {'ip': ip, 'kind': kind, 'sev': sev, 'first': first, 'last': last or first, 'when': last or first, 'hits': hits, **kw}


class Lanes(unittest.TestCase):
    def test_spans_per_host_and_kind_joined_when_close(self):
        out = [ev('10.0.0.5', 'malware_contact', 'crit', at(8), at(9), 3), ev('10.0.0.5', 'malware_contact', 'crit', at(9, 2), at(10), 2),
               ev('10.0.0.5', 'burst', 'info', at(9, 30)), ev('10.0.0.5', 'malware_contact', 'crit', at(11))]
        r = detect.lanes(out, T0, T1)
        h, = r['rows']
        self.assertEqual((h['ip'], h['n'], h['sev'], h['kinds']), ('10.0.0.5', 4, 'crit', {'malware_contact': 3, 'burst': 1}))
        mc = [s for s in h['spans'] if s[2] == 'malware_contact']
        # 08:00–09:00 and 09:02–10:00 are one stretch (2 min < period/300 = 288 s), 11:00 stands alone
        self.assertEqual([(s[3], s[4]) for s in mc], [(2, 5), (1, 1)])
        self.assertEqual(mc[0][0:2], [T1 - 4 * 3600, T1 - 2 * 3600])
        self.assertEqual(h['spans'], sorted(h['spans']))

    def test_order_top_and_all(self):
        out = [ev(f'81.20.30.{i}', 'port_scan', 'warn', at(10)) for i in range(1, 4) for _ in range(i)]
        out += [ev('10.0.0.9', 'listed_contact', 'crit', at(10))] * 3
        r = detect.lanes(out, T0, T1, top=2)
        # most events first; equal counts: the higher priority first
        self.assertEqual([h['ip'] for h in r['rows']], ['10.0.0.9', '81.20.30.3'])
        self.assertEqual(r['hosts'], 4)
        self.assertEqual(len(detect.lanes(out, T0, T1, top=0)['rows']), 4)
        many = [ev(f'81.20.{i // 250}.{i % 250}', 'port_scan', 'warn', at(10)) for i in range(detect.LANES_MAX + 30)]
        r = detect.lanes(many, T0, T1, top=0)
        self.assertEqual((len(r['rows']), r['hosts']), (detect.LANES_MAX, detect.LANES_MAX + 30))

    def test_left_out_and_cut_to_the_period(self):
        out = [{'kind': 'export_loss', 'sev': 'warn', 'device': '10.1.1.1', 'when': 'last hour'},        # no host
               {'kind': 'new_country', 'sev': 'info', 'ip': '10.0.0.7', 'when': 'last hour'},             # no time
               ev('10.0.0.8', 'burst', 'info', '2026-11-13 10:00:00', at(1)),                             # began before
               ev('10.0.0.6', 'burst', 'info', '2026-11-12 01:00:00', '2026-11-12 02:00:00')]             # all before
        r = detect.lanes(out, T0, T1)
        self.assertEqual([h['ip'] for h in r['rows']], ['10.0.0.8'])
        self.assertEqual(r['rows'][0]['spans'][0][0], T0)

    def test_country_only_for_outside_hosts(self):
        out = [ev('10.0.0.5', 'malware_contact', 'crit', at(8), country='US', org='X'),
               ev('81.20.30.5', 'port_scan', 'warn', at(8), country='NL', org='Y')]
        r = {h['ip']: h for h in detect.lanes(out, T0, T1)['rows']}
        self.assertEqual((r['10.0.0.5']['country'], r['81.20.30.5']['country'], r['81.20.30.5']['org']), ('', 'NL', 'Y'))


class Api(unittest.TestCase):
    def setUp(self):
        self.out = [ev('10.0.0.5', 'malware_contact', 'crit', at(8)), ev('81.20.30.5', 'port_scan', 'warn', at(9)),
                    ev('81.20.30.5', 'port_scan', 'warn', at(10))]
        self.patches = [mock.patch.object(api, '_alerts_now_cached', return_value=[]),
                        mock.patch.object(detect, 'recent', side_effect=lambda cfg, t0, t1, meta: [dict(a) for a in self.out]),
                        mock.patch.object(api, 'period', return_value=(T0, T1, False))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_lanes_follow_priority_and_kind(self):
        r = api.api_alerts({'limit': ['30'], 'hosts': ['10']})
        self.assertEqual([h['ip'] for h in r['lanes']['rows']], ['81.20.30.5', '10.0.0.5'])
        self.assertEqual([h['inside'] for h in r['lanes']['rows']], [False, True])
        self.assertTrue(all('name' in h for h in r['lanes']['rows']))
        r = api.api_alerts({'limit': ['30'], 'hosts': ['10'], 'sev': ['crit']})
        self.assertEqual([h['ip'] for h in r['lanes']['rows']], ['10.0.0.5'])
        r = api.api_alerts({'limit': ['30'], 'hosts': ['10'], 'kind': ['port_scan']})
        self.assertEqual([h['ip'] for h in r['lanes']['rows']], ['81.20.30.5'])

    def test_without_hosts_no_lanes_and_bad_value(self):
        self.assertNotIn('lanes', api.api_alerts({'limit': ['30']}))
        with self.assertRaises(api.BadRequest):
            api.api_alerts({'limit': ['30'], 'hosts': ['x']})


class Report(unittest.TestCase):
    """The PDF report's events section gets the lanes of the ten busiest hosts (one /api/alerts call, hosts=10)."""
    def test_collect_asks_for_lanes_once(self):
        import reports
        calls = []

        def call(path, q):
            calls.append((path, q))
            if path == '/api/alerts':
                return {'alerts': [], 'lanes': {'rows': [], 'hosts': 0}}
            return {'rows': [], 'total': 0, 'devices': [], 'series': {'step': 300, 'rows': []}}
        d = reports.collect({'f': [], 't': 'internet', 'tz': 'UTC', 'sections': ['events']}, T0, T1, call)
        al = [q for p, q in calls if p == '/api/alerts']
        self.assertEqual(len(al), 1)
        self.assertEqual(al[0]['hosts'], ['10'])
        self.assertEqual(d['event_lanes'], {'rows': [], 'hosts': 0})

    def test_drawing_has_a_lane_per_host_and_a_bar_per_stretch(self):
        import reports
        from reportlab.graphics.shapes import Drawing, Rect, String
        from reportlab.lib import colors
        reports._register()
        ln = {'hosts': 12, 'rows': [
            {'ip': '10.0.0.5', 'name': 'nas', 'country': '', 'spans': [[T0 + 3600, T0 + 7200, 'malware_contact', 2, 5], [T1 - 60, T1 - 60, 'burst', 1, 1]]},
            {'ip': '81.20.30.5', 'name': '', 'country': 'NL', 'spans': [[T0 + 600, T0 + 600, 'port_scan', 1, 1]]}]}
        out = reports.events_lanes(ln, T0, T1, 180 * 2.835, datetime.timezone.utc)
        d = next(x for x in out if isinstance(x, Drawing))
        texts = [x.text for x in d.contents if isinstance(x, String)]
        self.assertIn('nas', texts)
        self.assertIn('81.20.30.5', texts)
        self.assertIn('NL', texts)
        bars = [x for x in d.contents if isinstance(x, Rect) and x.fillColor != colors.HexColor(reports.PANEL)]
        self.assertEqual(len(bars), 3)
        self.assertTrue(all(b.width >= 1.4 for b in bars))       # a moment is still a visible bar
        self.assertIn('OF 12', out[0].text)                       # «the 2 … of 12» in the title
        self.assertEqual(reports.events_lanes({'rows': [], 'hosts': 0}, T0, T1, 500, datetime.timezone.utc), [])


class Page(unittest.TestCase):
    def test_events_page_asks_for_lanes_and_draws_them(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        body = js[js.index('function vThreats(){'):js.index('function vEvents(){')]
        self.assertIn("evQuery({limit:30, hosts:state.evLanes ?? 10})", body)
        self.assertIn("seg('evLaneN'", body)
        # visual first: the lanes come before the list of events
        self.assertLess(body.index('id="evLanes"'), body.index('id="alBox"'))


if __name__ == '__main__':
    unittest.main()
