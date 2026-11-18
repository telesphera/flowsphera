"""(2.11.0) New versions and the upgrade from the web interface.

The web service looks every 12 hours (CHECK_EVERY) at the VERSION and BUILD files of the published FlowSphera — the
same two files `flowsphera upgrade` compares — and remembers the answer in STATE_DIR/update_check.json. Nothing is
sent but the request itself (a User-Agent with the running version); the administrator can turn it off (offline
servers) in Settings → General, FT_UPDATE_CHECK=0 turns it off for good.

«Upgrade now» cannot run in the web service (user flowsphera, NoNewPrivileges, a read-only system): the web interface
writes STATE_DIR/upgrade.request and the root unit flowsphera-upgrade.path starts flowsphera-upgrade.service, which
runs `flowsphera web-upgrade` = `flowsphera upgrade` with its output in STATE_DIR/upgrade.log and its state in
STATE_DIR/upgrade_status.json — the same pattern as the backups (backup.request). The upgrade restarts the web service;
the page keeps asking until the new version answers.
"""
import json
import os
import re
import threading
import time
import urllib.request

from common import BUILD, STATE_DIR, VERSION

SETTINGS = os.path.join(STATE_DIR, 'updates.json')            # {check: bool} — the administrator's choice
CHECKED = os.path.join(STATE_DIR, 'update_check.json')        # the last look: {checked, latest, build, error}
REQUEST = os.path.join(STATE_DIR, 'upgrade.request')          # the web interface asks the root unit
STATUS = os.path.join(STATE_DIR, 'upgrade_status.json')       # written by `flowsphera web-upgrade` (root)
LOG = os.path.join(STATE_DIR, 'upgrade.log')
PATH_UNIT = os.environ.get('FT_UPGRADE_UNIT', '/etc/systemd/system/flowsphera-upgrade.path')
CLI = '/usr/local/bin/flowsphera'
REPO = 'telesphera/flowsphera'
CHECK_EVERY = 12 * 3600
FIRST_AFTER = 120               # the first look after the start: not in the same second as everything else
STALE = 45 * 60                 # «running» for longer = the upgrade was cut off (a reboot, a killed unit)
LOG_TAIL = 16000
NEWS = 'https://telesphera.com/news/flowsphera-{v}/'
_ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-Z0-9]')
_lock = threading.Lock()


def source():
    """Where the published version is read: the folder of the installer `flowsphera upgrade` uses (FT_INSTALL_URL in
    the env, else the REPO the installer wrote into /usr/local/bin/flowsphera, else the official repository)."""
    url = os.environ.get('FT_INSTALL_URL', '').strip()
    if url:
        return url.rsplit('/', 1)[0]
    repo = REPO
    try:
        with open(CLI) as f:
            m = re.search(r'^REPO=([\w.-]+/[\w.-]+)\s*$', f.read(), re.M)
        if m:
            repo = m.group(1)
    except OSError:
        pass
    return f'https://raw.githubusercontent.com/{repo}/main'


def key(version, build=1):
    """A version + build as a comparable tuple: 2.0.0 build 2 < 2.0.0 build 3 < 2.0.1 (as `sort -V` in the CLI)."""
    try:
        return tuple(int(x) for x in str(version).split('.')) + (int(build or 1),)
    except (TypeError, ValueError):
        return ()


def _read(path, default):
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else default
    except (OSError, ValueError):
        return default


def _write(path, d):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f)
    os.replace(tmp, path)


def env_off():
    return os.environ.get('FT_UPDATE_CHECK', '').strip().lower() in ('0', 'no', 'off', 'false')


def enabled():
    return not env_off() and _read(SETTINGS, {}).get('check', True) is not False


def set_enabled(on):
    _write(SETTINGS, {'check': bool(on)})


def _fetch(url, timeout):
    req = urllib.request.Request(f'{url}?{int(time.time())}', headers={'User-Agent': f'FlowSphera/{VERSION}'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(64).decode('ascii', 'replace').strip()


def check(timeout=10, fetch=None):
    """Read the published VERSION and BUILD now; the answer (or the error) is kept for the page."""
    fetch = fetch or _fetch
    base, out = source(), {'checked': int(time.time())}
    try:
        v = fetch(f'{base}/VERSION', timeout).strip()
        if not re.fullmatch(r'\d+(\.\d+){1,3}', v):
            raise ValueError(f'unexpected VERSION {v[:20]!r}')
        try:
            b = re.sub(r'\D', '', fetch(f'{base}/BUILD', timeout)) or '1'
        except Exception:       # noqa: BLE001 — no BUILD file = build 1, as in the CLI
            b = '1'
        out.update(latest=v, build=int(b))
    except Exception as e:      # noqa: BLE001 — offline, DNS, proxy: shown, never raised
        old = _read(CHECKED, {})
        out.update({k: old[k] for k in ('latest', 'build') if k in old}, error=str(e)[:200])
    with _lock:
        _write(CHECKED, out)
    return out


def upgrade_state(now=None):
    """The root unit's state: {state: running|done|failed|interrupted, from, to, started, ended, rc} or {}."""
    st = _read(STATUS, {})
    now = now or time.time()
    if st.get('state') == 'running' and now - (st.get('started') or 0) > STALE:
        st['state'] = 'interrupted'
    if os.path.exists(REQUEST) and st.get('state') != 'running':
        st = {'state': 'asked', 'asked': int(os.path.getmtime(REQUEST))}
    return st


def log_tail(n=LOG_TAIL):
    try:
        with open(LOG, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            text = f.read().decode('utf-8', 'replace')
    except OSError:
        return ''
    text = _ANSI.sub('', text)
    # a spinner rewrites its line with \r: keep what the line says last
    return '\n'.join(line.rsplit('\r', 1)[-1] for line in text.split('\n'))[-n:]


def status(with_log=False):
    last = _read(CHECKED, {})
    latest, build = last.get('latest'), last.get('build', 1)
    out = {'version': VERSION, 'build': BUILD, 'check': enabled(), 'env_off': env_off(), 'every_h': CHECK_EVERY // 3600,
           'checked': last.get('checked'), 'latest': latest, 'latest_build': build, 'error': last.get('error'),
           'available': bool(latest) and key(latest, build) > key(VERSION, BUILD),
           'news': NEWS.format(v=latest.replace('.', '-')) if latest else None,
           'can_upgrade': os.path.exists(PATH_UNIT), 'upgrade': upgrade_state()}
    if with_log:
        out['log'] = log_tail()
    return out


def ask_upgrade(who):
    """Hand the upgrade to the root unit (once: a second ask while one is waiting or running changes nothing)."""
    if not os.path.exists(PATH_UNIT):
        raise RuntimeError('no-unit')
    st = upgrade_state()
    if st.get('state') in ('asked', 'running'):
        return st
    with open(REQUEST + '.tmp', 'w') as f:
        json.dump({'asked': int(time.time()), 'by': who, 'from': VERSION, 'build': BUILD}, f)
    os.replace(REQUEST + '.tmp', REQUEST)
    return upgrade_state()


def checker(stop=None, log=print):
    """The web service's thread: a look every CHECK_EVERY seconds while the administrator lets it."""
    stop = stop or threading.Event()
    if stop.wait(FIRST_AFTER):
        return
    while True:
        if enabled() and time.time() - (_read(CHECKED, {}).get('checked') or 0) >= CHECK_EVERY - 60:
            r = check()
            if r.get('error'):
                log(f'new version check: {r["error"]}')
            elif key(r['latest'], r['build']) > key(VERSION, BUILD):
                log(f'FlowSphera {r["latest"]} (build {r["build"]}) is published; this is {VERSION} (build {BUILD})')
        if stop.wait(600):
            return
