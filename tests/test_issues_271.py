"""2.7.1: GitHub #13 (an exclusion of a target port alone, e.g. STUN 3478 from every inside host) and #14 (the search
box offers user names by a part of the name). Run: python -m unittest discover -s tests"""
import os
import re
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PortOnlyExclusion(unittest.TestCase):
    def test_a_port_alone_is_a_rule(self):
        r = detect.exclusions([{'src': '', 'dst': '', 'port': '3478', 'dir': 'up'}])
        self.assertEqual(r, [{'src': '', 'dst': '', 'port': 3478, 'dir': 'up'}])

    def test_a_rule_of_nothing_is_refused(self):
        for bad in ({'dir': 'up'}, {'src': '', 'dst': '', 'port': 0, 'dir': 'any'}):
            with self.assertRaises(ValueError):
                detect.exclusions([bad])

    def test_it_hides_the_stun_scan_of_any_inside_host(self):
        ex = detect.Exclude(detect.exclusions([{'src': '', 'dst': '', 'port': 3478, 'dir': 'up'}]))
        # the event «inside host scans the internet» by hosts: src = the host, no target, port = the port called
        self.assertTrue(ex('inside_scan', '10.0.0.5', '', 3478))
        self.assertTrue(ex('inside_scan', '10.0.7.9', '', 3478))
        self.assertFalse(ex('inside_scan', '10.0.0.5', '', 443))        # another port
        self.assertFalse(ex('port_scan', '198.51.100.9', '10.0.0.5', 3478))   # the other direction

    def test_link_load_is_never_excluded_by_a_port(self):
        # its «port» is an interface index: a rule for port 7 must not hide the load of interface 7
        ex = detect.Exclude(detect.exclusions([{'src': '', 'dst': '', 'port': 7, 'dir': 'any'}]))
        self.assertFalse(ex('link_load', '', '', 7))

    def test_the_form_allows_it(self):
        with open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn("if (!r.src && !r.dst && !r.port) return", js)
        self.assertNotIn('A source or a target is needed', js)


class UserSearch(unittest.TestCase):
    NAMES = ['corp\\anna', 'carl@corp.example', 'myname@domain.something', 'bob@corp.example', 'Anna.K@corp.example']

    def setUp(self):
        api._users.update(t=0.0, names=[])

    def test_a_part_of_the_name_finds_it_any_case(self):
        with mock.patch.object(api, 'user_names', return_value=self.NAMES):
            self.assertEqual(api.find_users('myna'), ['myname@domain.something'])
            self.assertEqual(api.find_users('DOMAIN'), ['myname@domain.something'])
            # names that begin with the text first, then in the order given (the busiest first)
            self.assertEqual(api.find_users('anna'), ['Anna.K@corp.example', 'corp\\anna'])
            self.assertEqual(api.find_users('corp', limit=2), ['corp\\anna', 'carl@corp.example'])
            self.assertEqual(api.find_users('  '), [])

    def test_endpoint_and_cache(self):
        calls = []

        def fake_ch(sql, *a, **k):
            calls.append(sql)
            return [{'u': n} for n in self.NAMES]
        with mock.patch.object(api, 'ch', fake_ch):
            self.assertEqual(api.api_users_find({'q': ['bob'], 'limit': ['3']}), {'users': ['bob@corp.example']})
            api.api_users_find({'q': ['anna']})
        self.assertEqual(len(calls), 1)                    # kept USER_TTL seconds
        # the FROM part is rollups.source's subquery (no WHERE of its own): the condition must start one
        self.assertRegex(calls[0], r"FROM \(SELECT .*\) WHERE user_name != ''")
        self.assertIn('/api/users/find', api.ROUTES)

    def test_the_search_box_asks_for_users(self):
        with open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn('api/users/find?q=', js)
        self.assertTrue(re.search(r"key === 'user' && val\) \{ userFind\(val", js))



class OverviewRefresh(unittest.TestCase):
    """(2.7.1, #10) Overview's cards, trend and lists reload by themselves (the browser check overview_refresh_check.js
    drives the clock); here: the timer exists in vOverview, skips a custom period and reloads every panel."""
    def test_overview_reloads_its_panels(self):
        with open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        body = js[js.index('function vOverview(){'):js.index('function selFilters(')]
        m = re.search(r"if \(!isCustom\(\)\) every\(rangeSecs\(\) <= 86400 \? 60000 : 300000, \(\) => \{(.*?)\}\);", body)
        self.assertTrue(m, 'no refresh timer in vOverview')
        for part in ("section('kpis', kpiCards)", 'Object.values(loaders).forEach(f => f())'):
            self.assertIn(part, m.group(1))
        # (2.11.0) the trend is one of the chosen panels: a loader like the lists, reloaded with them
        self.assertRegex(body, r"cTrend:\(\) => api\('series'\)")


if __name__ == '__main__':
    unittest.main()
