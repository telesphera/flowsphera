"""2.0.0 build 4: checking a backup gives one answer. The full check counts the rows the backup HOLDS (each part's
count.txt, a differential one's kept files read from its base under the base's own names) instead of a restored copy
that ClickHouse merges and trims by TTL at once (the false «damaged» of 27–28 Oct); a quick check never clears what a
full check found; a check that could not run is not damage; the page waits by the server's clock.
Run: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
os.environ['FT_BACKUP_DIR'] = tempfile.mkdtemp()
import backup  # noqa: E402


def make(d, bid, parts, base=None, kept=(), tables=None, rows=None):
    """parts: {(table, part): rows}; kept: names stored in the base (use_base) under base_names."""
    data = os.path.join(d, bid, 'data')
    os.makedirs(data, exist_ok=True)
    files = []
    for (t, part), n in parts.items():
        name = f'data/flowsphera/{t}/{part}/count.txt'
        if name in kept:
            files.append(f'<file><name>{name}</name><size>{len(str(n))}</size><use_base>true</use_base></file>')
            continue
        p = os.path.join(data, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write(str(n))
        files.append(f'<file><name>{name}</name><size>{len(str(n))}</size></file>')
    open(os.path.join(data, '.backup'), 'w').write('<config><contents>' + ''.join(files) + '</contents></config>')
    open(os.path.join(d, bid, 'settings.tar.gz'), 'wb').write(b'x')
    m = {'id': bid, 'kind': 'diff' if base else 'full', 'base': base, 't': 1, 'db': 'flowsphera',
         'tables': tables or {}, 'settings_sha256': backup._sha256(os.path.join(d, bid, 'settings.tar.gz'))}
    if rows is not None:
        m['rows'] = rows
    json.dump(m, open(os.path.join(d, bid, 'manifest.json'), 'w'))
    return m


class Rows(unittest.TestCase):
    def test_full_and_differential_with_files_kept_in_the_base(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(backup, 'DIR', d):
            make(d, '20261101-000001', {('flows', 'p1'): 10, ('agg_geo', 'p1'): 4})
            # the base stores equal files once: agg_conv's count.txt is kept under agg_geo's name
            bx = os.path.join(d, '20261101-000001', 'data', '.backup')
            xml = open(bx).read()
            open(bx, 'w').write(xml.replace('</contents>',
                '<file><name>data/flowsphera/agg_conv/p9/count.txt</name><size>1</size><data_file>data/flowsphera/agg_geo/p1/count.txt</data_file></file></contents>'))
            self.assertEqual(backup._backup_rows('20261101-000001'), {'flows': 10, 'agg_geo': 4, 'agg_conv': 4})
            make(d, '20261102-000002', {('flows', 'p1'): 10, ('flows', 'p2'): 5, ('agg_conv', 'p9'): 4}, base='20261101-000001',
                 kept=('data/flowsphera/flows/p1/count.txt', 'data/flowsphera/agg_conv/p9/count.txt'))
            self.assertEqual(backup._backup_rows('20261102-000002'), {'flows': 15, 'agg_conv': 4})


class Deep(unittest.TestCase):
    def run_verify(self, m_kw, engines, deep=True, prev=None):
        d = tempfile.mkdtemp()
        with mock.patch.object(backup, 'DIR', d), mock.patch.object(backup, '_sys'), \
                mock.patch.object(backup, '_check_files', return_value=[]), \
                mock.patch.object(backup, 'ch', return_value=[{'name': t, 'engine': e} for t, e in engines.items()]):
            make(d, '20261101-000001', {('flows', 'p1'): 100, ('agg_geo', 'p1'): 50}, **m_kw)
            if prev:
                m = backup._manifest('20261101-000001'); m['verified'] = prev; backup._save_manifest(m)
            problems = backup.verify('20261101-000001', deep=deep)
            return problems, backup._manifest('20261101-000001')['verified']

    def test_merged_aggregates_are_no_damage(self):
        # old manifest: before/after counts of the live tables; agg_geo merged while it was made (the 28 Oct case)
        p, v = self.run_verify({'tables': {'flows': [98, 101], 'agg_geo': [55, 56]}},
                               {'flows': 'MergeTree', 'agg_geo': 'AggregatingMergeTree'})
        self.assertEqual(p, [])
        self.assertTrue(v['ok'])

    def test_plain_table_outside_its_counts_is_damage(self):
        p, _ = self.run_verify({'tables': {'flows': [120, 130], 'agg_geo': [50, 50]}},
                               {'flows': 'MergeTree', 'agg_geo': 'AggregatingMergeTree'})
        self.assertEqual(len(p), 1)
        self.assertIn('flows', p[0])

    def test_exact_rows_when_recorded(self):
        p, _ = self.run_verify({'tables': {'flows': [0, 0], 'agg_geo': [0, 0]}, 'rows': {'flows': 100, 'agg_geo': 51}},
                               {'flows': 'MergeTree', 'agg_geo': 'AggregatingMergeTree'})
        self.assertEqual(len(p), 1)
        self.assertIn('agg_geo', p[0])

    def test_table_not_restored(self):
        p, _ = self.run_verify({'tables': {'flows': [100, 100], 'agg_geo': [50, 50]}}, {'flows': 'MergeTree'})
        self.assertTrue(any('agg_geo' in x for x in p))

    def test_quick_check_keeps_what_the_full_one_found(self):
        prev = {'t': 1_790_000_000, 'ok': False, 'deep': True, 'problems': ['20261101-000001: flows has 1 rows, 2–3 expected.']}
        p, v = self.run_verify({'tables': {}}, {}, deep=False, prev=prev)
        self.assertFalse(v['ok'])
        self.assertEqual(v['problems'][0], prev['problems'][0])
        self.assertTrue(p)                                            # the CLI says damaged too
        # a full check that passes clears it
        p, v = self.run_verify({'tables': {'flows': [100, 100], 'agg_geo': [50, 50]}},
                               {'flows': 'MergeTree', 'agg_geo': 'AggregatingMergeTree'}, prev=prev)
        self.assertTrue(v['ok'])

    def test_a_check_that_cannot_run_is_not_damage(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(backup, 'DIR', d), mock.patch.object(backup, '_check_files', return_value=[]), \
                mock.patch.object(backup, '_sys', side_effect=backup.CHError('Memory limit exceeded')):
            make(d, '20261101-000001', {('flows', 'p1'): 1}, tables={'flows': [1, 1]})
            with self.assertRaises(backup.CHError):
                backup.verify('20261101-000001', deep=True)
            v = backup._manifest('20261101-000001')['verified']
        self.assertIsNone(v['ok'])
        self.assertIn('Memory', v['error'])


class ServerClock(unittest.TestCase):
    def test_request_returns_the_server_time(self):
        import api
        d = tempfile.mkdtemp()
        with mock.patch.object(backup, 'REQUEST', os.path.join(d, 'req.json')), mock.patch('time.time', lambda: 1_800_000_123.7):
            r = api._backup_request({'do': 'verify', 'id': '20261101-000001'})
        self.assertEqual(r, {'ok': True, 't': 1_800_000_123})


if __name__ == '__main__':
    unittest.main()
