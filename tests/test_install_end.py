"""(2.4.1) The end of install.sh, run for real under the installer's own shell options: 2.1–2.4 stopped there with exit 1
(no BUILD file + pipefail), after everything was installed, and the summary with the generated password never came"""
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')
PRELUDE = r'''
set -Eeuo pipefail
trap 'echo STOPPED; exit 1' ERR
G= B= N= D= R= Y= C=
t() { printf '%%s' "$1"; }
say() { printf '%%s\n' "$*"; }
runuser() { return 1; }
bind_ips() { %(bind_ips)s; }
PREFIX=%(prefix)s STATE=%(prefix)s TLS_DIR=%(prefix)s
MODE=%(mode)s WEB_BIND=0.0.0.0 NF_BIND=0.0.0.0 NF_PORT=2055 WEB_PORT=3030 SF_PORT=0 PROTO=https USE_TLS=no VENDOR=MikroTik
LAN_IP=192.0.2.1 ADMIN_PW=secret-made-here ADMIN_PW_MADE=1
'''


def end_of_installer():
    text = open(os.path.join(ROOT, 'install.sh'), encoding='utf-8').read()
    start = text.index('# ------------------------------------------------------------------ done')
    end = text.index('\nuninstall() {', start)
    return text[start:end].rstrip()[:-1]     # without the } that closes main()


class End(unittest.TestCase):
    def run_end(self, mode, build=None, bind_ips='echo 192.0.2.1'):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'app'))
            with open(os.path.join(d, 'app', 'VERSION'), 'w') as f:
                f.write('9.9.9')
            if build:
                with open(os.path.join(d, 'app', 'BUILD'), 'w') as f:
                    f.write(build)
            script = PRELUDE % {'prefix': d, 'mode': mode, 'bind_ips': bind_ips} + end_of_installer()
            return subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=30)

    def test_no_build_file_upgrade(self):
        r = self.run_end('upgrade')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('FlowSphera 9.9.9 is running.', r.stdout)
        self.assertIn('your existing users', r.stdout)
        self.assertNotIn('STOPPED', r.stdout)

    def test_no_build_file_fresh_shows_generated_password(self):
        r = self.run_end('fresh')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('FlowSphera 9.9.9 is running.', r.stdout)
        self.assertIn('secret-made-here', r.stdout)
        self.assertIn('flowsphera status', r.stdout)

    def test_build_is_still_shown(self):
        r = self.run_end('upgrade', build='3')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('FlowSphera 9.9.9 build 3 is running.', r.stdout)

    def test_a_failure_while_printing_is_no_failed_install(self):
        r = self.run_end('fresh', bind_ips='return 1')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('flowsphera status', r.stdout)


if __name__ == '__main__':
    unittest.main()
