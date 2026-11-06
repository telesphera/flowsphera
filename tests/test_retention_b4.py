"""2.0.0 build 4: the administrator's data retention — fewer days than the license allows (a small disk), never more;
shortening stored records only for an explicit choice (an ended license deletes nothing); fewer days need the admin's
password; the pages never show more than the choice; and the «Last 15 minutes» period.
Run: python -m unittest discover -s tests"""
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
import common  # noqa: E402
import rollups  # noqa: E402

PRO = {'name': 'pro', 'status': 'active', 'rps': None, 'retention_days': 90, 'license': {}, 'message': '', 'features': []}
COMM = dict(PRO, name='community', status='community', retention_days=30)


def clear():
    try:
        os.remove(common.RETENTION_FILE)
    except FileNotFoundError:
        pass


class KeepDays(unittest.TestCase):
    def setUp(self):
        clear()

    def test_no_choice_is_the_edition(self):
        self.assertIsNone(common.retention_choice())
        self.assertEqual(common.keep_days(PRO), 90)

    def test_fewer_days_chosen(self):
        common.save_retention(7)
        self.assertEqual(common.keep_days(PRO), 7)

    def test_a_choice_above_an_ended_license_keeps_the_edition(self):
        common.save_retention(60)                 # chosen under Pro 90, the license ended
        self.assertEqual(common.keep_days(COMM), 30)
        self.assertEqual(common.keep_days(PRO), 60)   # and comes back with it

    def test_broken_file_is_no_choice(self):
        open(common.RETENTION_FILE, 'w').write('{nope')
        self.assertIsNone(common.retention_choice())


class Post(unittest.TestCase):
    def setUp(self):
        clear()
        self.check = mock.Mock()
        self.pw = mock.patch.object(api, 'AUTH', mock.Mock(check_password=self.check))
        self.pw.start()
        self.addCleanup(self.pw.stop)
        for name, val in (('edition', lambda: PRO), ('get_retention', lambda: {'ok': 1})):
            p = mock.patch.object(api, name, val)
            p.start()
            self.addCleanup(p.stop)

    def test_more_than_the_license_is_refused(self):
        with self.assertRaises(api.BadRequest):
            api.post_retention({'days': 91}, 'admin', '1.2.3.4')
        with self.assertRaises(api.BadRequest):
            api.post_retention({'days': 0}, 'admin', '1.2.3.4')
        with self.assertRaises(api.BadRequest):
            api.post_retention({'days': 'ten'}, 'admin', '1.2.3.4')
        self.assertIsNone(common.retention_choice())

    def test_fewer_days_need_the_password(self):
        api.post_retention({'days': 14, 'password': 'x'}, 'admin', '1.2.3.4')
        self.check.assert_called_once_with('admin', 'x', '1.2.3.4')
        self.assertEqual(common.retention_choice(), 14)

    def test_wrong_password_saves_nothing(self):
        self.check.side_effect = api.BadRequest('wrong password')
        with self.assertRaises(api.BadRequest):
            api.post_retention({'days': 14, 'password': 'bad'}, 'admin', '1.2.3.4')
        self.assertIsNone(common.retention_choice())

    def test_more_days_need_no_password_and_the_most_clears_the_choice(self):
        common.save_retention(14)
        api.post_retention({'days': 30}, 'admin', '1.2.3.4')
        self.check.assert_not_called()
        self.assertEqual(common.retention_choice(), 30)
        api.post_retention({'days': 90}, 'admin', '1.2.3.4')
        self.assertIsNone(common.retention_choice())


class ViewDays(unittest.TestCase):
    def tearDown(self):
        clear()

    def test_pages_never_show_more_than_the_choice(self):
        api._stored.update(t=10 ** 12, days=120)          # records from an older, longer license still stored
        with mock.patch.object(api, 'edition', lambda: PRO):
            self.assertEqual(api.view_days(), 120)
            common.save_retention(10)
            self.assertEqual(api.view_days(), 10)


class Shorten(unittest.TestCase):
    def test_updates_longer_records_and_drops_whole_old_days(self):
        sql = []

        def ch(q, params=None, fmt=None, **kw):
            sql.append((q, params))
            if q.startswith('SELECT count()'):
                return [{'n': '5' if 'FROM flows ' in q else '0'}]
            if 'system.parts' in q:
                return [{'p': p} for p in ('20261001', '20261010') if p < params['c']] + ([{'p': 'all'}] if params['t'] == 'flows' else [])
            return []
        now = 1_793_000_000                              # 2026-10-26 UTC
        with mock.patch.object(common, 'ch', ch), mock.patch('time.time', lambda: now), \
                mock.patch.object(rollups, 'ROLLUPS', {'agg_traffic': {}}):
            n, dropped = common.flows_shorten(7)
        self.assertEqual((n, dropped), (5, 2))
        alters = [q for q, _ in sql if q.startswith('ALTER')]
        self.assertIn('ALTER TABLE flows UPDATE keep_days = 7 WHERE keep_days > 7', alters)
        self.assertIn("ALTER TABLE flows DROP PARTITION ID '20261001'", alters)
        self.assertIn("ALTER TABLE agg_traffic DROP PARTITION ID '20261010'", alters)
        self.assertFalse(any("'all'" in q for q in alters))                  # never a partition that is not a day
        self.assertFalse(any('agg_traffic UPDATE' in q for q in alters))     # nothing longer there


class Collector(unittest.TestCase):
    def run_retention(self, choice, ed):
        import collector
        c = collector.Receiver.__new__(collector.Receiver)
        calls = []
        with mock.patch.object(collector, 'keep_days', lambda: common.keep_days(ed)), \
                mock.patch.object(collector, 'retention_choice', lambda: choice), \
                mock.patch.object(collector, 'flows_keep_days', lambda d: calls.append(('raise', d)) or 0), \
                mock.patch.object(collector, 'flows_shorten', lambda d: calls.append(('shorten', d)) or (0, 0)), \
                mock.patch.object(collector, 'log', lambda *a: None), \
                mock.patch.object(common, 'retention_choice', lambda: choice):
            c.retention_ready = mock.Mock()
            c._apply_retention()
        return calls

    def test_an_ended_license_shortens_nothing(self):
        self.assertEqual(self.run_retention(None, COMM), [('raise', 30)])
        self.assertEqual(self.run_retention(60, COMM), [('raise', 30)])     # choice above the edition: no shortening

    def test_a_choice_shortens(self):
        self.assertEqual(self.run_retention(7, PRO), [('raise', 7), ('shorten', 7)])


class FifteenMinutes(unittest.TestCase):
    def test_preset(self):
        with mock.patch('time.time', lambda: 1_800_000_000), mock.patch.object(api, 'view_days', lambda: 30):
            _, p, rng, step = api.scope({'range': ['15m']})
        self.assertEqual((rng, step), (900, 60))
        self.assertEqual(p['t1'] - p['t0'], 900)


if __name__ == '__main__':
    unittest.main()
