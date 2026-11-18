"""(2.11.0) New versions and «Upgrade now» (updates.py), the Overview's chosen panels (auth prefs, app.js OV_KINDS),
the upgrade files kept out of settings backups. Run: python -m unittest discover -s tests"""
import json
import os
import re
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
import auth  # noqa: E402
import updates as U  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')


class Files(unittest.TestCase):
    """Every file of updates.py in a scratch folder of its own."""
    def setUp(self):
        self.d = tempfile.mkdtemp()
        names = {'SETTINGS': 'updates.json', 'CHECKED': 'update_check.json', 'REQUEST': 'upgrade.request',
                 'STATUS': 'upgrade_status.json', 'LOG': 'upgrade.log', 'PATH_UNIT': 'flowsphera-upgrade.path', 'CLI': 'flowsphera'}
        self.p = [mock.patch.object(U, k, os.path.join(self.d, v)) for k, v in names.items()]
        self.p += [mock.patch.object(U, 'VERSION', '2.11.0'), mock.patch.object(U, 'BUILD', 1), mock.patch.dict(os.environ, {'FT_INSTALL_URL': '', 'FT_UPDATE_CHECK': ''})]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()

    def put(self, name, text):
        with open(os.path.join(self.d, name), 'w') as f:
            f.write(text if isinstance(text, str) else json.dumps(text))


class Versions(Files):
    def test_key_order(self):
        self.assertLess(U.key('2.0.0', 2), U.key('2.0.0', 3))
        self.assertLess(U.key('2.0.0', 3), U.key('2.0.1', 1))
        self.assertLess(U.key('2.9.0'), U.key('2.10.0'))            # numbers, not text
        self.assertEqual(U.key('x'), ())

    def test_check_newer(self):
        files = {'/VERSION': '2.12.0\n', '/BUILD': '1\n'}
        r = U.check(fetch=lambda url, t: files[url[url.rindex('/'):]])
        self.assertEqual((r['latest'], r['build']), ('2.12.0', 1))
        s = U.status()
        self.assertTrue(s['available'])
        self.assertEqual(s['news'], 'https://telesphera.com/news/flowsphera-2-12-0/')

    def test_same_or_older_not_offered(self):
        for v in ('2.11.0', '2.10.3'):
            U.check(fetch=lambda url, t, v=v: v if url.endswith('VERSION') else '1')
            self.assertFalse(U.status()['available'], v)

    def test_new_build_offered(self):
        U.check(fetch=lambda url, t: '2.11.0' if url.endswith('VERSION') else '2')
        self.assertTrue(U.status()['available'])

    def test_no_build_file_is_build_1(self):
        def f(url, t):
            if url.endswith('BUILD'):
                raise OSError('404')
            return '2.11.0'
        self.assertEqual(U.check(fetch=f)['build'], 1)

    def test_error_keeps_the_last_answer(self):
        U.check(fetch=lambda url, t: '2.12.0' if url.endswith('VERSION') else '1')
        def down(url, t):
            raise OSError('Network is unreachable')
        r = U.check(fetch=down)
        self.assertIn('unreachable', r['error'])
        s = U.status()
        self.assertEqual(s['latest'], '2.12.0')
        self.assertTrue(s['available'])

    def test_garbage_is_an_error(self):
        r = U.check(fetch=lambda url, t: '<html>404</html>')
        self.assertIn('unexpected VERSION', r['error'])
        self.assertFalse(U.status()['available'])

    def test_source(self):
        self.assertEqual(U.source(), 'https://raw.githubusercontent.com/telesphera/flowsphera/main')
        self.put('flowsphera', '#!/bin/sh\nREPO=someone/fork\nPREFIX=/opt/flowsphera\n')
        self.assertEqual(U.source(), 'https://raw.githubusercontent.com/someone/fork/main')
        with mock.patch.dict(os.environ, {'FT_INSTALL_URL': 'http://10.0.0.9:8000/install.sh'}):
            self.assertEqual(U.source(), 'http://10.0.0.9:8000')

    def test_switch(self):
        self.assertTrue(U.enabled())
        U.set_enabled(False)
        self.assertFalse(U.enabled())
        U.set_enabled(True)
        with mock.patch.dict(os.environ, {'FT_UPDATE_CHECK': '0'}):
            self.assertFalse(U.enabled())
            self.assertTrue(U.status()['env_off'])

    def test_checker_respects_the_switch(self):
        calls = []
        U.set_enabled(False)
        stop = mock.Mock()
        stop.wait.side_effect = [False, True]            # the first look, then stop
        with mock.patch.object(U, 'check', lambda: calls.append(1) or {}):
            U.checker(stop, log=lambda m: None)
        self.assertEqual(calls, [])
        U.set_enabled(True)
        stop.wait.side_effect = [False, True]
        with mock.patch.object(U, 'check', lambda: calls.append(1) or {'latest': '2.11.0', 'build': 1}):
            U.checker(stop, log=lambda m: None)
        self.assertEqual(calls, [1])


class Upgrade(Files):
    def test_no_unit_refused(self):
        with self.assertRaises(RuntimeError):
            U.ask_upgrade('admin')
        self.assertFalse(os.path.exists(U.REQUEST))
        self.assertFalse(U.status()['can_upgrade'])

    def test_ask_once(self):
        self.put('flowsphera-upgrade.path', '[Path]\n')
        self.assertEqual(U.ask_upgrade('admin')['state'], 'asked')
        with open(U.REQUEST) as f:
            self.assertEqual(json.load(f)['by'], 'admin')
        t = os.path.getmtime(U.REQUEST)
        time.sleep(0.01)
        U.ask_upgrade('other')                                   # waiting already: nothing new
        self.assertEqual(os.path.getmtime(U.REQUEST), t)
        os.remove(U.REQUEST)
        self.put('upgrade_status.json', {'state': 'running', 'started': int(time.time())})
        self.assertEqual(U.ask_upgrade('admin')['state'], 'running')
        self.assertFalse(os.path.exists(U.REQUEST))

    def test_stale_running_is_interrupted(self):
        self.put('upgrade_status.json', {'state': 'running', 'started': int(time.time()) - U.STALE - 5})
        self.assertEqual(U.upgrade_state()['state'], 'interrupted')
        self.put('flowsphera-upgrade.path', '[Path]\n')
        self.assertEqual(U.ask_upgrade('admin')['state'], 'asked')      # may be asked again

    def test_log_tail_clean(self):
        self.put('upgrade.log', 'start\n\x1b[1;32m✓\x1b[0m Database\n  ⠋ Starting\r  ✓ Starting FlowSphera\nend\n')
        t = U.log_tail()
        self.assertNotIn('\x1b', t)
        self.assertIn('✓ Database', t)
        self.assertIn('  ✓ Starting FlowSphera', t)
        self.assertNotIn('⠋', t)
        self.put('upgrade.log', 'x' * (U.LOG_TAIL + 500))
        self.assertEqual(len(U.log_tail()), U.LOG_TAIL)


class Api(Files):
    def test_run_needs_password(self):
        import api
        with mock.patch.object(api, 'AUTH', mock.Mock(**{'check_password.side_effect': auth.AuthError('wrong')})):
            with self.assertRaises(auth.AuthError):
                api.post_update_run({'password': 'x'}, 'admin', '127.0.0.1')
        self.assertFalse(os.path.exists(U.REQUEST))

    def test_run_without_unit_says_how(self):
        import api
        with mock.patch.object(api, 'AUTH', mock.Mock()):
            with self.assertRaises(api.BadRequest) as c:
                api.post_update_run({'password': 'x'}, 'admin', '127.0.0.1')
        self.assertIn('sudo flowsphera upgrade', str(c.exception))

    def test_run_asks(self):
        import api
        self.put('flowsphera-upgrade.path', '[Path]\n')
        with mock.patch.object(api, 'AUTH', mock.Mock()):
            r = api.post_update_run({'password': 'x'}, 'admin', '127.0.0.1')
        self.assertEqual(r['upgrade']['state'], 'asked')
        self.assertIn('log', r)

    def test_config(self):
        import api
        self.assertFalse(api.post_update_config({'check': False})['check'])
        with self.assertRaises(api.BadRequest):
            api.post_update_config({'check': 'yes'})

    def test_admin_only(self):
        import api
        self.assertIn('/api/update', api.ADMIN_GET)
        with open(os.path.join(ROOT, 'api.py')) as f:
            src = f.read()
        admin = src[src.index('admin_routes'):]
        for path in ('/api/update/config', '/api/update/check', '/api/update/run'):
            self.assertIn(f"'{path}'", admin)


class OverviewPanels(unittest.TestCase):
    def test_pref(self):
        ok = auth.Auth.PREFS['overview_panels']
        self.assertTrue(ok('services,hosts,trend,conv,recent'))
        self.assertTrue(ok('countries,hosts,trend,asn,recent'))
        for bad in ('services,services,trend,conv,recent', 'evil,hosts,trend,conv,recent', 'services,hosts,trend,conv', 5, None,
                    'services,hosts,trend,conv,recent,countries'):
            self.assertFalse(ok(bad), bad)

    def test_set_prefs(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(auth, 'USERS_FILE', os.path.join(d, 'u.json')), mock.patch.object(auth, 'SESSIONS_FILE', os.path.join(d, 's.json')):
            a = auth.Auth()
            a.create_user('nocscreen', 'viewer', 'a-long-password-1') if hasattr(a, 'create_user') else a.update_user('nocscreen', 'viewer', password='a-long-password-1')
            self.assertEqual(a.set_prefs('nocscreen', {'overview_panels': 'countries,hosts,trend,conv,recent'})['prefs']['overview_panels'],
                             'countries,hosts,trend,conv,recent')
            with self.assertRaises(auth.AuthError):
                a.set_prefs('nocscreen', {'overview_panels': 'countries,countries,trend,conv,recent'})
            with self.assertRaises(auth.AuthError):
                a.set_prefs('nocscreen', {'path_view': 'nope'})       # the other prefs still checked as before

    def test_same_kinds_as_the_page(self):
        with open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        body = js[js.index('const OV_KINDS = () => ({'):js.index('const ovOk')]
        kinds = re.findall(r'^\s+(\w+):\{ic:', body, re.M)
        self.assertEqual(sorted(kinds), sorted(auth.OV_PANELS))
        default = re.search(r"const OV_DEFAULT = \[([^\]]+)\]", js).group(1)
        self.assertTrue(auth.Auth.PREFS['overview_panels'](','.join(re.findall(r"'(\w+)'", default))))


class Backups(unittest.TestCase):
    def test_upgrade_files_never_restored(self):
        import backup
        for n in ('upgrade.request', 'upgrade_status.json', 'upgrade.log', 'update_check.json'):
            self.assertIn(f'{backup._S}/{n}', backup.SKIP_RESTORE)

    def test_units_installed_and_removed(self):
        with open(os.path.join(ROOT, 'install.sh')) as f:
            sh = f.read()
        self.assertIn('deploy/flowsphera-upgrade.path', sh)
        self.assertIn('/etc/systemd/system/flowsphera-upgrade.path', sh)
        self.assertRegex(sh, r'systemctl start [^\n]*flowsphera-upgrade\.path')
        with open(os.path.join(ROOT, 'deploy', 'flowsphera-upgrade.path')) as f:
            self.assertIn('PathExists=/var/lib/flowsphera/upgrade.request', f.read())
        with open(os.path.join(ROOT, 'deploy', 'flowsphera')) as f:
            cli = f.read()
        self.assertIn('web-upgrade)', cli)
        self.assertIn('rm -f "$S/upgrade.request"', cli)


if __name__ == '__main__':
    unittest.main()
