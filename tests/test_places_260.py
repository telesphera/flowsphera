"""2.6.0: City + Country put a device on the map without coordinates — the place index is made from the DB-IP Lite
City database FlowSphera already has (deploy/geoip-places.py), read by common.Places, used by /api/meta and offered
by /api/geo/places in the device form.
Run: python -m unittest discover -s tests"""
import importlib.util
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True), os.makedirs(TMP + '/geo', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import api  # noqa: E402
import common  # noqa: E402

spec = importlib.util.spec_from_file_location('geoip_places', os.path.join(ROOT, 'deploy', 'geoip-places.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def rec(cc, city, lat, lon, reg=''):
    return {'country': {'iso_code': cc}, 'city': {'names': {'en': city}}, 'location': {'latitude': lat, 'longitude': lon},
            'subdivisions': [{'names': {'en': reg}}] if reg else []}


RANGES = ([rec('BE', 'Brussels', 50.8476, 4.35717, 'Brussels Capital')] * 5 + [rec('BE', 'Brussels', 50.9, 4.4, 'Brussels Capital')]
          + [rec('BE', 'Brussels', 50.8322, 4.327, 'Wallonia')] + [rec('BE', 'Liège', 50.6337, 5.5675, 'Wallonia')] * 2
          + [rec('US', 'Springfield', 39.78, -89.65, 'Illinois')] * 3 + [rec('US', 'Springfield', 37.2, -93.29, 'Missouri')] * 2
          + [rec('US', 'Spring', 30.1, -95.44, 'Texas')] + [rec('US', 'San Francisco (Financial District)', 37.79, -122.4, 'California')]
          + [rec('', 'Nowhere', 1, 1), rec('UA', '', 1, 1), {'country': {'iso_code': 'UA'}, 'city': {'names': {'en': 'Kyiv'}}}])


def build(d):
    with mock.patch.dict(sys.modules, maxminddb=mock.Mock(open_database=lambda p: [(None, r) for r in RANGES])):
        builder.main(d)
    return os.path.join(d, 'dbip-places.tsv')


class Builder(unittest.TestCase):
    def test_index(self):
        lines = open(build(TMP + '/geo'), encoding='utf-8').read().splitlines()
        self.assertEqual(lines[0], 'BE\tbrussels\tBrussels\tBrussels Capital\t50.8476\t4.3572\t6')   # coordinates seen most
        self.assertIn('BE\tliege\tLiège\tWallonia\t50.6337\t5.5675\t2', lines)
        self.assertIn('US\tsan francisco\tSan Francisco\tCalifornia\t37.79\t-122.4\t1', lines)
        self.assertEqual(len(lines), 6)                  # no country, no city, no coordinates: skipped
        self.assertNotIn('Wallonia\t50.8322', '\n'.join(lines))      # a stray namesake 2 km away: the same place
        self.assertFalse(os.path.exists(TMP + '/geo/dbip-places.tsv.tmp'))

    def test_same_fold(self):
        self.assertEqual(builder.fold(' Liège-Ville  '), common.place_key('liege ville'))


class Lookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp()
        cls.pl = common.Places(build(d))

    def test_get(self):
        self.assertEqual(self.pl.get('be', ' BRUSSELS '), {'name': 'Brussels', 'region': 'Brussels Capital', 'lat': 50.8476, 'lon': 4.3572})
        self.assertEqual(self.pl.get('BE', 'Liege')['name'], 'Liège')
        self.assertEqual(self.pl.get('US', 'springfield')['region'], 'Illinois')      # a name used twice: the bigger
        self.assertIsNone(self.pl.get('BE', 'Leuven'))
        self.assertIsNone(self.pl.get('', 'Brussels'))
        self.assertIsNone(self.pl.get('BE', ''))

    def test_find(self):
        self.assertEqual([(x['name'], x['region']) for x in self.pl.find('US', 'spring')],
                         [('Springfield', 'Illinois'), ('Springfield', 'Missouri'), ('Spring', 'Texas')])
        self.assertEqual([x['name'] for x in self.pl.find('US', 'field')], ['Springfield', 'Springfield'])   # holding it
        self.assertEqual(len(self.pl.find('US', 's', limit=2)), 2)
        self.assertEqual(self.pl.find('XX', 'a'), [])

    def test_missing_file_and_reload(self):
        d = tempfile.mkdtemp()
        pl = common.Places(os.path.join(d, 'dbip-places.tsv'))
        self.assertFalse(pl.ready())
        self.assertIsNone(pl.get('BE', 'Brussels'))
        build(d)
        pl.looked = 0                                   # the next look reads the file that appeared
        self.assertTrue(pl.ready())
        self.assertEqual(pl.get('BE', 'Brussels')['lat'], 50.8476)

    def test_device_site(self):
        with mock.patch.object(common, 'PLACES', self.pl):
            self.assertEqual(common.device_site({'city': 'Brussels', 'country': 'BE'}), (50.8476, 4.3572, 'city'))
            self.assertEqual(common.device_site({'city': 'Brussels', 'country': 'BE', 'lat': 1.5, 'lon': 2.5}), (1.5, 2.5, 'manual'))
            self.assertEqual(common.device_site({'city': 'Brussels', 'country': 'BE', 'lat': 1.5, 'lon': None}), (50.8476, 4.3572, 'city'))
            self.assertEqual(common.device_site({'city': 'Atlantis', 'country': 'BE'}), (None, None, None))
            self.assertEqual(common.device_site({}), (None, None, None))


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pl = common.Places(build(tempfile.mkdtemp()))

    def test_meta_places_the_device(self):
        exp = {'192.0.2.1': {'name': 'rb5009', 'city': 'Brussels', 'country': 'BE'}, '192.0.2.2': {'name': 'fw', 'lat': 52.37, 'lon': 4.9},
               '192.0.2.3': {'name': 'lost', 'city': 'Atlantis', 'country': 'BE'}}
        seen = [{'exporter': ip, 'last': int(time.time())} for ip in exp]

        def ch(sql, *a, **k):
            return seen if 'exporter_stats' in sql else []
        with mock.patch.object(common, 'PLACES', self.pl), mock.patch.object(api, 'exporters_cfg', return_value=exp), \
             mock.patch.object(api, 'ch', side_effect=ch), mock.patch.object(api, 'has_apps', return_value=False), \
             mock.patch.object(api, 'listen_info', return_value={}), mock.patch.object(api, 'edition_info', return_value={}):
            got = {d['ip']: (d['lat'], d['lon'], d['geo_src']) for d in api.api_meta({})['devices']}
        self.assertEqual(got, {'192.0.2.1': (50.8476, 4.3572, 'city'), '192.0.2.2': (52.37, 4.9, 'manual'), '192.0.2.3': (None, None, None)})

    def test_places_endpoint(self):
        with mock.patch.object(common, 'PLACES', self.pl):
            r = api.api_geo_places({'country': ['us'], 'q': ['Spring'], 'limit': ['1']})
            self.assertEqual((r['places'][0]['region'], len(r['places']), r['ready']), ('Illinois', 1, True))
            self.assertEqual(api.api_geo_places({'country': ['BE'], 'q': ['bru'], 'limit': ['x']})['places'][0]['name'], 'Brussels')
            self.assertEqual(api.api_geo_places({})['places'], [])
        self.assertIs(api.ROUTES['/api/geo/places'], api.api_geo_places)


class Wiring(unittest.TestCase):
    def test_update_script_builds_the_index(self):
        sh = open(os.path.join(ROOT, 'deploy', 'geoip-update.sh')).read()
        self.assertGreaterEqual(sh.count('\n  places\n') + sh.count('\n    places\n') + sh.count('\nplaces\n'), 3)
        self.assertIn('geoip-places.py', sh)

    def test_form_and_banner(self):
        js = open(os.path.join(ROOT, 'web', 'app.js')).read()
        self.assertIn('wirePlace(m.root)', js)
        self.assertIn('set City and Country (or Latitude and Longitude) in Settings → Devices', js)
        self.assertNotIn("set Latitude and Longitude in Settings → Devices'", js)


if __name__ == '__main__':
    unittest.main()


class DeviceTable(unittest.TestCase):
    def test_site_stays_text(self):         # (2.6.0) a dict under 'site' showed «[object Object]» in Settings → Devices + CSV
        src = open(api.__file__).read()
        self.assertNotIn("'site': dict(", src)
        self.assertIn("'site': ', '.join(x for x in (c.get('city', ''), c.get('country', '')) if x)", src)
