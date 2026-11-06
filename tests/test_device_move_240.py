"""2.4.0 (GitHub issue #4): a device whose export moves to another address keeps everything set for it — description,
interfaces, capacities, SNMP — and its earlier address becomes an alias: device: filters, the interface filter, the
names in the browser and the device list count the old address's records as the device's own.
Run: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write(json.dumps({'192.0.2.1': {'name': 'fw-main', 'vendor': 'Fortinet', 'wan_ifs': [3],
                                                                       'if_names': {'3': 'wan1', '5': 'lan'}}}))
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import common  # noqa: E402
import snmp  # noqa: E402


DEPLOY = {'192.0.2.1': {'name': 'fw-main', 'vendor': 'Fortinet', 'wan_ifs': [3], 'if_names': {'3': 'wan1', '5': 'lan'}}}


class Move(unittest.TestCase):
    def setUp(self):
        # own files whatever directories other test modules set common / snmp to
        d = tempfile.mkdtemp()
        real_load = common.load_json
        for target, attr, val in ((common, 'UI_EXPORTERS', d + '/ui_exporters.json'), (snmp, 'SETTINGS', d + '/snmp.json'),
                                  (common, 'load_json', lambda name, default: json.loads(json.dumps(DEPLOY)) if name == 'exporters.json' else real_load(name, default))):
            pt = mock.patch.object(target, attr, val)
            pt.start()
            self.addCleanup(pt.stop)
        snmp.save_settings('192.0.2.1', {'enabled': True, 'version': '2c', 'community': 'secret'})
        api.NAMES.reload()
        self.addCleanup(api.NAMES.reload)

    def move(self, old, new):
        return api.post_device_move({'ip': old, 'new_ip': new}, 'admin')

    def test_everything_moves_and_the_old_address_is_an_alias(self):
        self.assertEqual(self.move('192.0.2.1', '192.0.2.9'), {'ok': True, 'ip': '192.0.2.9'})
        cfg = common.load_exporters()
        self.assertNotIn('192.0.2.1', cfg)                                   # the deployment entry is hidden
        self.assertEqual(cfg['192.0.2.9']['name'], 'fw-main')
        self.assertEqual(cfg['192.0.2.9']['if_names'], {'3': 'wan1', '5': 'lan'})
        self.assertEqual(cfg['192.0.2.9']['aliases'], ['192.0.2.1'])
        self.assertEqual(snmp.load_settings().get('192.0.2.9', {}).get('community'), 'secret')
        self.assertNotIn('192.0.2.1', snmp.load_settings())
        self.assertEqual(common.device_aliases(), {'192.0.2.1': '192.0.2.9'})
        # and again: both earlier addresses stay the device's
        self.move('192.0.2.9', '192.0.2.10')
        self.assertEqual(common.load_exporters()['192.0.2.10']['aliases'], ['192.0.2.9', '192.0.2.1'])
        self.assertEqual(api.device_ips('192.0.2.10'), ['192.0.2.10', '192.0.2.9', '192.0.2.1'])

    def test_refused(self):
        with self.assertRaises(api.BadRequest):
            self.move('192.0.2.77', '192.0.2.9')                             # not configured
        with self.assertRaises(api.BadRequest):
            self.move('192.0.2.1', '192.0.2.1')                              # the same address
        with self.assertRaises(api.BadRequest):
            self.move('192.0.2.1', 'not-an-ip')
        common.save_ui_exporter('192.0.2.5', {'name': 'other'}); api.NAMES.reload()
        with self.assertRaises(api.BadRequest):
            self.move('192.0.2.1', '192.0.2.5')                              # already a device of its own
        self.assertEqual(common.load_exporters()['192.0.2.1']['name'], 'fw-main')

    def test_device_filter_takes_the_old_address_too(self):
        self.move('192.0.2.1', '192.0.2.9')
        with mock.patch.object(api, 'view_days', lambda: 30):
            _, p, _, _ = api.scope({'range': ['24h'], 'f': [json.dumps([{'k': 'device', 'v': '192.0.2.9'}])]})
            _, p2, _, _ = api.scope({'range': ['24h'], 'f': [json.dumps([{'k': 'device', 'v': '192.0.2.5'}])]})
        self.assertIn('exporter IN', p['_filt'])
        self.assertEqual(p['f0a'], ['192.0.2.9', '192.0.2.1'])
        self.assertIn('exporter = {f0:String}', p2['_filt'])                # a device without aliases: as before


class ExportImport(Move):
    def imp(self, data, password='pw'):
        return api.post_devices_import({'data': data, 'password': password}, 'admin', '1.2.3.4')

    def test_export_has_the_devices_and_no_secrets(self):
        d = api.get_devices_export()
        self.assertEqual(d['format'], 'flowsphera-devices')
        self.assertEqual(d['devices']['192.0.2.1']['if_names'], {'3': 'wan1', '5': 'lan'})
        self.assertNotIn('secret', json.dumps(d))                         # SNMP community stays on the server

    def test_import_adds_and_replaces_only_what_is_listed(self):
        common.save_ui_exporter('192.0.2.50', {'name': 'keep-me'}); api.NAMES.reload()
        d = api.get_devices_export()
        d['devices']['192.0.2.1']['name'] = 'fw-renamed'
        d['devices']['192.0.2.1']['if_caps'] = {'3': [300, 50]}
        d['devices']['192.0.2.7'] = {'name': 'branch', 'vendor': 'MikroTik', 'wan_ifs': [1], 'if_names': {'1': 'ether1'}}
        del d['devices']['192.0.2.50']
        self.assertEqual(self.imp(d), {'ok': True, 'added': 1, 'updated': 1})
        cfg = common.load_exporters()
        self.assertEqual((cfg['192.0.2.1']['name'], cfg['192.0.2.1']['if_caps'], cfg['192.0.2.1']['if_names']['5']), ('fw-renamed', {'3': [300.0, 50.0]}, 'lan'))
        self.assertEqual(cfg['192.0.2.7']['if_names'], {'1': 'ether1'})
        self.assertEqual(cfg['192.0.2.50']['name'], 'keep-me')            # not in the file: as it was

    def test_nothing_changes_on_a_bad_file_a_wrong_password_or_one_bad_device(self):
        with self.assertRaises(api.BadRequest):
            self.imp({'devices': {}})                                       # not our format
        good = {'format': 'flowsphera-devices', 'devices': {'192.0.2.7': {'name': 'branch'}}}
        self.check.side_effect = api.BadRequest('Wrong password')
        with self.assertRaises(api.BadRequest):
            self.imp(good, 'bad')
        self.check.side_effect = None
        bad = {'format': 'flowsphera-devices', 'devices': {'192.0.2.7': {'name': 'branch'}, '192.0.2.8': {'name': 'x', 'if_caps': {'1': ['lots', 1]}}}}
        with self.assertRaises(api.BadRequest):
            self.imp(bad)
        self.assertNotIn('192.0.2.7', common.load_exporters())             # all or nothing

    def setUp(self):
        super().setUp()
        self.check = mock.Mock()
        pt = mock.patch.object(api, 'AUTH', mock.Mock(check_password=self.check))
        pt.start()
        self.addCleanup(pt.stop)


class Ignore(Move):
    def test_ignore_and_stop(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(common, 'IGNORED_SOURCES', d + '/ignored.json'):
            self.assertEqual(api.post_device_ignore({'ip': '198.51.100.7'}, 'admin')['ignored'], ['198.51.100.7'])
            self.assertEqual(common.load_ignored(), {'198.51.100.7'})
            with self.assertRaises(api.BadRequest):
                api.post_device_ignore({'ip': '192.0.2.1'}, 'admin')     # a configured device: delete it instead
            self.assertEqual(api.post_device_ignore({'ip': '198.51.100.7', 'stop': True}, 'admin')['ignored'], [])

    def test_the_receiver_drops_an_ignored_source(self):
        import collector as C
        d = tempfile.mkdtemp()
        with mock.patch.object(common, 'IGNORED_SOURCES', d + '/ignored.json'), mock.patch.object(C, 'load_ignored', common.load_ignored):
            common.save_ignored({'198.51.100.7'})
            self.assertIn('198.51.100.7', C.load_ignored())


if __name__ == '__main__':
    unittest.main()
