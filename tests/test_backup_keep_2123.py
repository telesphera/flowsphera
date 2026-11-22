"""(2.12.3, Yegor 22.11) Keeping backups: the newest `keep_full` full backups; of the newest chain also its 3 newest
changes; older chains keep only their full one. A change already half the size of its full one → the next backup is a
full one. Prod had 16 backups for «keep 4» (9 changes on one full, schedule off)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import backup  # noqa: E402


def man(bid, kind='full', base=None, data_size=100):
    return {'id': bid, 'kind': kind, 'base': base, 't': 0, 'size': data_size, 'data_size': data_size,
            'places': {'local': 'ok'}, 'errors': {}}


F27, F28, F29, F06 = '20261027-140219', '20261028-112952', '20261029-141500', '20261106-100035'
PROD = [man(F27), man(F28), man(F29)] + [man(x, 'diff', F29) for x in ('20261030-084533', '20261031-154355', '20261106-091210')] \
    + [man(F06)] + [man(x, 'diff', F06) for x in ('20261106-175729', '20261106-185702', '20261106-190337', '20261107-133943',
                                                    '20261118-075407', '20261119-105158', '20261121-184645', '20261121-200243', '20261121-224713')]


def folder(ms):
    d = tempfile.mkdtemp()
    for m in ms:
        os.makedirs(os.path.join(d, m['id']))
        with open(os.path.join(d, m['id'], 'manifest.json'), 'w') as f:
            json.dump(m, f)
    return d


class Keep(unittest.TestCase):
    def test_prod_picture(self):
        k = backup.kept_ids(PROD, 4)
        self.assertEqual(sorted(k), sorted([F27, F28, F29, F06, '20261121-184645', '20261121-200243', '20261121-224713']))

    def test_prune_prod_folder(self):
        d = folder(PROD)
        cfg = backup.defaults(); cfg['keep_full'] = 4
        with mock.patch.object(backup, 'DIR', d):
            gone = backup.prune(cfg, log=lambda *a: None)
        self.assertEqual(len(gone), 9)
        self.assertEqual(len(os.listdir(d)), 7)

    def test_fewer_changes_all_kept(self):
        ms = [man('20261201-030000'), man('20261202-030000', 'diff', '20261201-030000')]
        self.assertEqual(backup.kept_ids(ms, 4), {'20261201-030000', '20261202-030000'})

    def test_orphan_change_is_a_chain_of_its_own_and_kept(self):
        # chains(): a change whose full one is gone is a chain of its own (counts towards keep_full), unchanged since 1.8
        ms = [man('20261210-030000'), man('20261205-030000', 'diff', '20261101-000000'), man('20261204-030000', 'diff', '20261101-000000')]
        self.assertEqual(backup.kept_ids(ms, 4), {'20261210-030000', '20261205-030000', '20261204-030000'})
        self.assertEqual(backup.kept_ids(ms, 2), {'20261210-030000', '20261205-030000'})

    def test_a_place_loses_the_trimmed_changes_too(self):
        d = folder(PROD)
        names = [m['id'] + ext for m in PROD for ext in ('.ftbk', '.json')]
        place = mock.Mock(); place.list.return_value = names
        cfg = backup.defaults(); cfg['keep_full'], cfg['sftp']['on'] = 4, True
        with mock.patch.object(backup, 'DIR', d), mock.patch.object(backup, 'open_dest', return_value=place):
            backup.prune(cfg, log=lambda *a: None)
        deleted = {c.args[0].split('.')[0] for c in place.delete.call_args_list}
        self.assertEqual(len(deleted), 9)
        self.assertIn('20261030-084533', deleted)          # a change of an older chain, newer than the oldest full kept
        self.assertNotIn(F27, deleted)

    def test_another_servers_newer_copy_is_left(self):
        d = folder([man('20261201-030000')])
        place = mock.Mock(); place.list.return_value = ['20261201-030000.ftbk', '20261215-030000.ftbk']
        cfg = backup.defaults(); cfg['keep_full'], cfg['sftp']['on'] = 4, True
        with mock.patch.object(backup, 'DIR', d), mock.patch.object(backup, 'open_dest', return_value=place):
            backup.prune(cfg, log=lambda *a: None)
        place.delete.assert_not_called()


class AutoFull(unittest.TestCase):
    def test_half_the_size_makes_a_full_one(self):
        base = man(F06, data_size=850)
        self.assertTrue(backup._changes_too_big([man('20261121-224713', 'diff', F06, 457), base], base))
        self.assertFalse(backup._changes_too_big([man('20261121-224713', 'diff', F06, 300), base], base))
        self.assertFalse(backup._changes_too_big([base], base))
        self.assertFalse(backup._changes_too_big([man('20261121-224713', 'diff', F06, 457), man(F06, data_size=0)], man(F06, data_size=0)))


if __name__ == '__main__':
    unittest.main()
