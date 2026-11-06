"""2.0.0 build 4: /api/ingest — records/s per device over the period from the per-minute exporter_stats, the step
chosen from the period's length, partial steps divided by the seconds they cover, the device filter only, the busiest
minute and the steps where the license limit dropped records. Run: python -m unittest discover -s tests"""
import json
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

NOW = 1_800_000_000 // 3600 * 3600 + 1800          # half past an hour


class Fake:
    def __init__(self):
        self.sql = []

    def __call__(self, sql, params=None, fmt=None, **kw):
        self.sql.append((sql, params))
        if 'collector_stats' in sql:
            return [{'t': str(NOW - 3600), 'n': '120'}]
        if 'toStartOfMinute' in sql:
            return [{'t': str(NOW - 3600), 'r': '6000'}]
        return [{'t': str(NOW - 3600), 'exporter': '192.0.2.1', 'r': '180000'},     # a whole 5-min step: 600/s
                {'t': str(NOW - 300), 'exporter': '192.0.2.1', 'r': '6000'}]          # running for 300 s here


class Ingest(unittest.TestCase):
    def run_api(self, q, rps=5000):
        ch = Fake()
        with mock.patch.object(api, 'ch', ch), mock.patch('time.time', lambda: NOW), \
                mock.patch.object(api.common, 'edition', lambda: {'rps': rps}):
            return api.api_ingest(q), ch

    def test_step_rates_peak_drops_and_limit(self):
        d, _ = self.run_api({'range': ['24h']})
        self.assertEqual(d['step'], 300)                                  # 288 points for a day
        self.assertEqual(d['rows'][0], [NOW - 3600, '192.0.2.1', 600.0])
        self.assertEqual(d['rows'][1][2], 20.0)                           # 6000 over the 300 s it ran
        self.assertEqual(d['peak'], [[NOW - 3600, 100.0]])                # the busiest minute, per second
        self.assertEqual(d['drops'], [[NOW - 3600, 120]])
        self.assertEqual(d['limit'], 5000)

    def test_hour_has_minute_steps_and_month_hourly(self):
        self.assertEqual(self.run_api({'range': ['1h']})[0]['step'], 60)
        self.assertEqual(self.run_api({'range': ['30d']})[0]['step'], 10800)

    def test_only_the_device_filter_applies(self):
        f = json.dumps([{'k': 'device', 'v': '192.0.2.1'}, {'k': 'device', 'v': '192.0.2.9', 'neg': True},
                        {'k': 'ip', 'v': '10.0.0.5'}])
        _, ch = self.run_api({'range': ['24h'], 'f': [f]})
        sql, p = ch.sql[0]
        self.assertIn('exporter IN', sql)
        self.assertIn('exporter NOT IN', sql)
        self.assertEqual((p['inc'], p['exc']), (['192.0.2.1'], ['192.0.2.9']))
        self.assertNotIn('10.0.0.5', json.dumps(p))

    def test_unlimited_edition(self):
        self.assertIsNone(self.run_api({'range': ['6h']}, rps=None)[0]['limit'])


if __name__ == '__main__':
    unittest.main()
