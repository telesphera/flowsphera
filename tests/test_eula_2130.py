"""(2.13.0) The FlowSphera License Agreement: every acceptance is kept on the installation (version, time, who, how);
entering a license needs it — web (accept_eula), CLI (--accept-eula), installer (asked on a new install and with
--license, --yes needs --accept-eula); an online activation sends it to the license server; removing a license and
upgrades are not asked. Run: python -m unittest discover -s tests"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FT_STATE_DIR', tempfile.mkdtemp())
os.environ.setdefault('FT_CONFIG_DIR', tempfile.mkdtemp())
import common  # noqa: E402
import licensing  # noqa: E402
import api  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')


class Record(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        p = mock.patch.object(common, 'EULA_FILE', os.path.join(self.d, 'eula.json'))
        p.start()
        self.addCleanup(p.stop)

    def test_no_record_before_acceptance(self):
        self.assertIsNone(common.eula_record())

    def test_every_acceptance_is_kept(self):
        a = common.accept_eula('root', 'install')
        b = common.accept_eula('admin', 'web')
        self.assertEqual((a['version'], a['by'], a['how']), (common.EULA_VERSION, 'root', 'install'))
        self.assertEqual(common.eula_record(), b)
        with open(common.EULA_FILE) as f:
            self.assertEqual([r['how'] for r in json.load(f)['accepted']], ['install', 'web'])
        self.assertEqual(oct(os.stat(common.EULA_FILE).st_mode & 0o777), '0o640')

    def test_broken_file_reads_as_none(self):
        with open(common.EULA_FILE, 'w') as f:
            f.write('{nope')
        self.assertIsNone(common.eula_record())
        common.accept_eula('root', 'cli')                  # and is replaced by a good one
        self.assertEqual(common.eula_record()['how'], 'cli')

    def test_save_license_records_before_activating(self):
        with mock.patch.object(licensing, 'activate_key', side_effect=licensing.ServerError('no', 'unreachable')) as act:
            with self.assertRaises(licensing.ServerError):
                common.save_license('FTK-AAAAA-BBBBB', accept=('anna', 'web'))
        self.assertEqual(common.eula_record()['by'], 'anna')
        self.assertEqual(act.call_args[0][1]['by'], 'anna')          # the record goes with the activation

    def test_removing_a_license_records_nothing(self):
        common.save_license('', accept=('anna', 'web'))
        self.assertIsNone(common.eula_record())

    def test_activation_sends_the_acceptance(self):
        sent = {}

        def post(path, body, timeout=20):
            sent.update(body)
            return {'license': 'FTL-X', 'lease': 'FTS-X'}
        with mock.patch.object(licensing, '_post', post), mock.patch.object(licensing.ftcore, 'save_lease'), \
                mock.patch.object(licensing, '_record'):
            licensing.activate_key('FTK-AAAAA', {'version': '1.0', 'ts': 5, 'by': 'anna', 'how': 'web', 'extra': 1})
        self.assertEqual(sent['eula'], {'version': '1.0', 'ts': 5, 'by': 'anna', 'how': 'web'})
        sent.clear()
        with mock.patch.object(licensing, '_post', post), mock.patch.object(licensing.ftcore, 'save_lease'), \
                mock.patch.object(licensing, '_record'):
            licensing.activate_key('FTK-AAAAA')                       # an old caller: no field at all
        self.assertNotIn('eula', sent)


class Web(unittest.TestCase):
    def test_activation_needs_the_checkbox(self):
        with mock.patch.object(api, 'save_license') as save:
            for body in ({'key': 'FTK-A'}, {'key': 'FTK-A', 'accept_eula': 'yes'}, {'key': 'FTK-A', 'accept_eula': False}):
                with self.assertRaises(api.BadRequest):
                    api.post_license(body, 'anna')
            save.assert_not_called()
            with mock.patch.object(api, 'edition_info', return_value={}):
                api.post_license({'key': ' FTK-A ', 'accept_eula': True}, 'anna')
                save.assert_called_with('FTK-A', accept=('anna', 'web'))
                api.post_license({'key': ''}, 'anna')                 # removing: no agreement needed
                save.assert_called_with('', accept=None)

    def test_ui_sends_it_and_has_the_texts(self):
        with open(os.path.join(ROOT, 'web', 'app.js'), encoding='utf-8') as f:
            js = f.read()
        self.assertIn("apiPost('license', {key:k, accept_eula:true})", js)
        self.assertIn('id="eulaOk"', js)
        with open(os.path.join(ROOT, 'web', 'i18n', 'uk.json'), encoding='utf-8') as f:
            uk = json.load(f)
        for t in ('I accept the', 'FlowSphera License Agreement', 'Accept the License Agreement first',
                  'Accepted here: version {v}, {when}, {who} {how}', 'Accept the FlowSphera License Agreement to activate a license'):
            self.assertIn(t, uk)

    def test_urls_are_the_published_ones(self):
        self.assertEqual(common.EULA_URL, {'uk': 'https://telesphera.net/legal/eula/', 'en': 'https://telesphera.net/legal/eula/en/'})


class Cli(unittest.TestCase):
    def test_activate_needs_the_flag(self):
        with mock.patch.object(common, 'save_license') as save, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                licensing._cli(['licensing.py', 'activate', 'FTL-AAAAA'])
            self.assertIn('--accept-eula', str(e.exception.code))
            save.assert_not_called()

    def test_activate_with_the_flag(self):
        ed = {'license': {'customer': 'T', 'expires': 0}}
        with mock.patch.object(common, 'save_license', return_value=ed) as save, mock.patch.dict(os.environ, {'FT_BY': 'yegor'}), \
                redirect_stderr(io.StringIO()), mock.patch('sys.stdout', io.StringIO()):
            licensing._cli(['licensing.py', 'activate', 'FTL-AAAAA', '--accept-eula'])
        save.assert_called_with('FTL-AAAAA', accept=('yegor', 'cli'))


class Installer(unittest.TestCase):
    with open(os.path.join(ROOT, 'install.sh'), encoding='utf-8') as f:
        sh = f.read()

    def test_versions_match(self):
        self.assertIn(f'EULA_VERSION={common.EULA_VERSION}\n', self.sh)
        self.assertIn(f"EULA_URL_UK={common.EULA_URL['uk']}\n", self.sh)
        self.assertIn(f"EULA_URL_EN={common.EULA_URL['en']}\n", self.sh)

    def test_asked_only_for_new_installs_and_licenses(self):
        self.assertIn('if { [ "$EXISTING" = 0 ] || [ -n "$LIC_KEY" ]; } && [ "$MODE" != uninstall ]; then', self.sh)
        # before anything is installed, and --yes without --accept-eula stops
        self.assertLess(self.sh.index('# ---- license agreement (2.13.0)'.replace('----', '-' * 66)), self.sh.index('pkg_install() {'))
        block = self.sh[self.sh.index('license agreement (2.13.0)'):self.sh.index('pkg_install() {')]
        self.assertRegex(block, re.compile(r'elif \[ "\$YES" = 1 \]; then\s+die'))
        self.assertIn('--accept-eula) ACCEPT_EULA=1 ;;', self.sh)

    def test_recorded_and_passed_with_the_license(self):
        self.assertIn('common.accept_eula(os.environ["FT_BY"], "install")', self.sh)
        self.assertIn('common.save_license(sys.stdin.read(), accept=(os.environ["FT_BY"], "install"))', self.sh)
        self.assertIn('run activate - \\$acc < "\\$src"', self.sh)      # the flowsphera-license wrapper
        # (Lab #181) dash quits on a failed redirection of ':' in braces: the terminal check must be a subshell
        self.assertIn('( : < /dev/tty ) 2>/dev/null; then', self.sh)
        self.assertNotIn('"\\$acc" ] && { : < /dev/tty; }', self.sh)


if __name__ == '__main__':
    unittest.main()
