"""2.12.0 (forum #54): Settings → Host names → Names from DNS — /api/hosts/dns lists what reverse DNS answered,
searchable and paged, with the own name that wins; an own name made from one goes through /api/hosts/names/add.
Run: python -m unittest discover -s tests"""
import os
import re
import sys
import tempfile
import time
import unittest

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def q(**kw):
    return {k: [str(v)] for k, v in kw.items()}


class DnsNames(unittest.TestCase):
    def setUp(self):
        now = time.time()
        with api.NAMES.lock:
            self.saved = dict(api.NAMES.cache)
            api.NAMES.cache = {'10.0.0.10': ('nas.office.lan', now), '10.0.0.2': ('gw.office.lan', now),
                               '10.0.0.3': ('', now),            # asked, no answer: not listed
                               '2001:db8::5': ('printer.office.lan', now)}
        api.post_host_names({'items': [{'ip': '10.0.0.2', 'name': 'Router'}]})

    def tearDown(self):
        api.post_host_names({'items': []})
        with api.NAMES.lock:
            api.NAMES.cache = self.saved

    def test_lists_answers_by_address_with_the_own_name(self):
        d = api.api_hosts_dns({})
        self.assertEqual([x['ip'] for x in d['items']], ['10.0.0.2', '10.0.0.10', '2001:db8::5'])   # numeric order, v4 first
        self.assertEqual(d['total'], 3)
        self.assertEqual(d['items'][0]['own'], 'Router')
        self.assertEqual(d['items'][1]['own'], '')
        self.assertIn(d['mode'], ('off', 'shown', 'background'))

    def test_search_and_pages(self):
        self.assertEqual([x['ip'] for x in api.api_hosts_dns(q(q='PRINTER'))['items']], ['2001:db8::5'])
        self.assertEqual([x['ip'] for x in api.api_hosts_dns(q(q='10.0.0.1'))['items']], ['10.0.0.10'])
        page = api.api_hosts_dns(q(offset=1, limit=1))
        self.assertEqual(([x['ip'] for x in page['items']], page['total']), (['10.0.0.10'], 3))
        with self.assertRaises(api.BadRequest):
            api.api_hosts_dns(q(limit='many'))

    def test_making_a_dns_name_ones_own(self):
        api.post_names_add('hosts', {'items': [{'ip': '10.0.0.10', 'name': 'NAS in the office'}]})
        d = {x['ip']: x for x in api.api_hosts_dns({})['items']}
        self.assertEqual(d['10.0.0.10']['own'], 'NAS in the office')
        self.assertEqual(api.NAMES.get('10.0.0.10', lookup=False), 'NAS in the office')     # the own name wins
        self.assertEqual(d['10.0.0.2']['own'], 'Router')                                     # the rest stays

    def test_route_is_readable(self):
        self.assertIs(api.ROUTES['/api/hosts/dns'], api.api_hosts_dns)


class WebParts(unittest.TestCase):
    """The browser side of 2.12.0, as text: the pieces must stay wired."""
    @classmethod
    def setUpClass(cls):
        cls.js = open(os.path.join(ROOT, 'web/app.js')).read()

    def test_full_screen_lists_fill_the_height(self):
        for box in ('hostBox', 'convBox', 'ccBox', 'asBox', 'recentBox'):
            self.assertIn(f"limit:lim('{box}', ", self.js)
        self.assertIn('fitRows(document.getElementById(id))', self.js)
        self.assertRegex(self.js, r"function fitLimit\(id\)")

    def test_a_city_is_a_filter(self):
        self.assertRegex(self.js, r"e\.seriesId === 'remotes' && e\.data\) placeFilter\(e\.data\.city, e\.data\.cc\)")
        self.assertIn("closest('.gl-lbl.place')", self.js)
        body = re.search(r"function placeFilter\(city, cc\)\{(.*)\}", self.js).group(1)
        self.assertIn("putFilter({k:'country', v:cc})", body)

    def test_version_card_tells_the_update_state(self):
        self.assertIn('<span id="verState">', self.js)
        body = self.js[self.js.index("const vs = document.getElementById('verState')"):][:900]
        self.assertIn('u.available', body)
        self.assertIn("scrollIntoView", body)

    def test_classic_keeps_a_link_without_the_selected_traffic(self):
        # (2.12.0) Path analysis → Classic drew nothing for a link with 0 of the selected traffic (Internet over the
        # GRE link between two firewalls): every branch now draws a quiet line, and the tooltip says what else it carries
        self.assertEqual(self.js.count("else if (!w && !thin()) quiet(curve(0));"), 3)
        self.assertIn("+ linkIdle(l) + linkHints(", self.js)

    def test_dns_panel(self):
        self.assertIn("api('hosts/dns'", self.js)
        self.assertIn("apiPost('hosts/names/add'", self.js)


if __name__ == '__main__':
    unittest.main()
