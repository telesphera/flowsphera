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


if __name__ == '__main__':
    unittest.main()
