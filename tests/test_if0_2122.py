"""(2.12.2, forum) NetFlow / IPFIX index 0 is the device itself (RouterOS, FortiOS, Cisco: traffic to and from the
router). Without a setting of its own it shows as «local», not as an unknown «if 0»."""
import os
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import api  # noqa: E402


class Index0(unittest.TestCase):
    def test_zero_is_the_device_itself_by_default(self):
        i = api.iface({}, 0, 100, 0, (), None)
        self.assertEqual((i['role'], i['name']), ('local', 'local'))

    def test_own_setting_wins(self):
        i = api.iface({'local_if': 9}, 0, 100, 0, (), None)      # another index set as «the device itself»
        self.assertEqual((i['role'], i['name']), ('lan', 'if 0'))
        self.assertEqual(api.iface({'local_if': 9}, 9, 1, 0, (), None)['role'], 'local')
        self.assertEqual(api.iface({'wan_ifs': [0]}, 0, 1, 0, (), None)['role'], 'wan')
        self.assertEqual(api.iface({'if_names': {'0': 'cpu'}}, 0, 1, 0, (), None)['name'], 'cpu')

    def test_snmp_interface_zero_is_left_alone(self):
        i = api.iface({}, 0, 1, 0, (), {'ifs': {'0': {'name': 'sw0'}}})
        self.assertEqual((i['role'], i['name']), ('lan', 'sw0'))

    def test_other_indexes_unchanged(self):
        self.assertEqual(api.iface({}, 3, 1, 0, (), None)['name'], 'if 3')


if __name__ == '__main__':
    unittest.main()
