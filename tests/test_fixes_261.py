"""2.6.1: the device list at the top (issue #8) — a device deleted from the settings no longer stays in it while its old
statistics are kept; a source nobody described shows only while it sends (15 minutes), an ignored one never.
Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import common  # noqa: E402


def meta(exp, seen, ignored=()):
    def ch(sql, *a, **k):
        return seen if 'exporter_stats' in sql else []
    with mock.patch.object(api, 'exporters_cfg', return_value=exp), mock.patch.object(api, 'ch', side_effect=ch), \
         mock.patch.object(common, 'load_ignored', return_value=set(ignored)), mock.patch.object(api, 'has_apps', return_value=False), \
         mock.patch.object(api, 'listen_info', return_value={}), mock.patch.object(api, 'edition_info', return_value={}):
        return [d['ip'] for d in api.api_meta({})['devices']]


class GhostDevice(unittest.TestCase):
    def test_issue_8(self):
        now = int(time.time())
        row = lambda ip, ago: {'exporter': ip, 'last': '2026-11-11 10:00:00', 'lu': now - ago}      # noqa: E731
        exp = {'192.0.2.1': {'name': 'fw'}, '192.0.2.2': {'name': 'rb', 'aliases': ['192.0.2.9']}}
        seen = [row('192.0.2.1', 30), row('192.0.2.2', 86400 * 3),        # described: always, even quiet for days
                row('192.0.2.3', 86400),                                    # deleted from the settings a day ago: gone
                row('192.0.2.4', 120),                                      # not described, sending now: shown
                row('192.0.2.5', 60),                                       # ignored: never
                row('192.0.2.9', 60)]                                       # an alias: the device's own
        self.assertEqual(meta(exp, seen, ignored=['192.0.2.5']), ['192.0.2.1', '192.0.2.2', '192.0.2.4'])
        self.assertEqual(meta(exp, [row('192.0.2.4', api.UNDESCRIBED_FOR + 5)]), [])


if __name__ == '__main__':
    unittest.main()
