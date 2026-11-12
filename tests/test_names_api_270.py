"""2.7.0 (GitHub issue #7): the name tables a row at a time and all at once — /api/hosts/names/add|delete,
/api/networks/add|delete, /api/ports/add|delete. Run: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import threading
import unittest

TMP = tempfile.mkdtemp()
os.makedirs(TMP + '/cfg', exist_ok=True), os.makedirs(TMP + '/state', exist_ok=True)
open(TMP + '/cfg/exporters.json', 'w').write('{}')
os.environ.update(FT_CONFIG_DIR=TMP + '/cfg', FT_STATE_DIR=TMP + '/state')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api  # noqa: E402
import common  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Hosts(unittest.TestCase):
    def setUp(self):
        api.post_host_names({'items': [{'ip': '10.0.0.1', 'name': 'Router'}, {'ip': '10.0.0.2', 'name': 'NAS'}]})

    def tearDown(self):
        api.post_host_names({'items': []})

    def names(self):
        return {x['ip']: x['name'] for x in api.api_host_names({})['items']}

    def test_add_keeps_the_rest_and_replaces_the_same_address(self):
        out = api.post_names_add('hosts', {'items': [{'ip': '10.0.0.2', 'name': 'Backup NAS'}, {'ip': '10.0.0.3', 'name': 'Printer'}]})
        self.assertEqual((out['added'], out['changed']), (1, 1))
        self.assertEqual(self.names(), {'10.0.0.1': 'Router', '10.0.0.2': 'Backup NAS', '10.0.0.3': 'Printer'})

    def test_add_is_all_or_nothing(self):
        with self.assertRaises(api.BadRequest):
            api.post_names_add('hosts', {'items': [{'ip': '10.0.0.9', 'name': 'Good'}, {'ip': 'nope', 'name': 'Bad'}]})
        with self.assertRaises(api.BadRequest):
            api.post_names_add('hosts', {'items': [{'ip': '10.0.0.9', 'name': ''}]})
        self.assertEqual(self.names(), {'10.0.0.1': 'Router', '10.0.0.2': 'NAS'})

    def test_delete_some_and_all(self):
        out = api.post_names_delete('hosts', {'items': ['10.0.0.1', '10.0.0.77']})
        self.assertEqual((out['removed'], out['missing']), (1, ['10.0.0.77']))
        self.assertEqual(self.names(), {'10.0.0.2': 'NAS'})
        out = api.post_names_delete('hosts', {'all': True})
        self.assertEqual((out['removed'], out['items']), (1, []))

    def test_delete_needs_to_say_what(self):
        for bad in ({}, {'all': 'yes'}, {'items': []}, {'names': ['NAS']}, {'items': ['not an ip']}):
            with self.assertRaises(api.BadRequest):
                api.post_names_delete('hosts', bad)
        self.assertEqual(len(self.names()), 2)

    def test_parallel_adds_lose_nothing(self):
        ts = [threading.Thread(target=api.post_names_add, args=('hosts', {'items': [{'ip': f'10.1.0.{i}', 'name': f'H{i}'}]}))
              for i in range(1, 21)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(self.names()), 22)


class Networks(unittest.TestCase):
    def setUp(self):
        api.post_networks({'items': [{'net': '10.0.0.0/24', 'name': 'Office'}, {'net': '10.0.1.0/24', 'name': 'Office'},
                                     {'net': '10.9.0.0/16', 'name': 'Lab'}]})

    def tearDown(self):
        api.post_networks({'items': []})

    def test_add_normalises_and_replaces(self):
        out = api.post_names_add('networks', {'items': [{'net': '10.9.3.4/16', 'name': 'Lab 2'}, {'net': '192.168.5.0/24', 'name': 'Home'}]})
        self.assertEqual((out['added'], out['changed']), (1, 1))
        self.assertIn({'net': '10.9.0.0/16', 'name': 'Lab 2'}, out['items'])
        self.assertEqual(len(out['items']), 4)

    def test_delete_by_network_and_by_name(self):
        out = api.post_names_delete('networks', {'items': ['10.9.1.1/16']})
        self.assertEqual(out['removed'], 1)
        out = api.post_names_delete('networks', {'names': ['office', 'Nowhere']})
        self.assertEqual((out['removed'], out['missing'], out['items']), (2, ['nowhere'], []))


class Ports(unittest.TestCase):
    def setUp(self):
        api.post_ports({'items': [{'proto': 'tcp', 'port': 8443, 'name': 'Mgmt'}, {'proto': 'udp', 'port': 5000, 'name': 'Camera'}]})

    def tearDown(self):
        api.post_ports({'items': []})
        common.PORT_NAMES.clear()

    def test_add_without_protocol_is_tcp(self):
        out = api.post_names_add('ports', {'items': [{'port': 8443, 'name': 'HTTPS management'}, {'proto': 'UDP', 'port': 53, 'name': 'Our DNS'}]})
        self.assertEqual((out['added'], out['changed']), (1, 1))
        self.assertEqual({(x['proto'], x['port']): x['name'] for x in out['items']},
                         {('tcp', 8443): 'HTTPS management', ('udp', 5000): 'Camera', ('udp', 53): 'Our DNS'})

    def test_delete_by_spec(self):
        out = api.post_names_delete('ports', {'items': ['5000/udp', {'proto': 'tcp', 'port': 8443}, 'tcp/9']})
        self.assertEqual((out['removed'], out['missing'], out['items']), (2, ['tcp/9'], []))
        with self.assertRaises(api.BadRequest):
            api.post_names_delete('ports', {'items': ['icmp/1']})


class Wiring(unittest.TestCase):
    def test_routes_are_admin_posts_open_to_write_tokens(self):
        with open(os.path.join(ROOT, 'api.py')) as f:
            src = f.read()
        for t in ('hosts/names', 'networks', 'ports'):
            for op in ('add', 'delete'):
                self.assertIn(f"'/api/{t}/{op}': lambda: post_names_{op}(", src)
                self.assertNotIn(f'/api/{t}/{op}', api.TOKEN_DENY)

    def test_ui_has_delete_all_for_each_table(self):
        with open(os.path.join(ROOT, 'web', 'app.js')) as f:
            js = f.read()
        for path in ('ports/delete', 'hosts/names/delete', 'networks/delete'):
            self.assertIn(f"del:'{path}'", js)


if __name__ == '__main__':
    unittest.main()
