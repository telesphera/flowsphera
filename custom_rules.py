"""(2.10.0, forum #58) The operator's own event rules, checked every 10 minutes in the web service.

A rule (detect.custom_rules checks it): the search box's filters (a host, a network, a service, a port, a country, a
device …) and a traffic scope, a measure — bytes, flows (records) or distinct outside addresses — above a threshold
within the last `minutes`, for everything the filters match together or for each inside host. The measure is asked
through the API's own scope() (the caller passes it in), so a rule counts exactly what the pages show for the same
filters, and long spans come from the pre-aggregated tables. A hit is stored as an event of kind 'custom' (key = rule
id, or rule id > host) with the rule's own priority, and a new one is notified like the built-in events.

Run: the web service starts Runner(api.custom_measure).run in a thread. State: STATE_DIR/custom_rules_state.json."""
import json
import os
import time

import detect
import notify
from common import STATE_DIR

STATE = os.path.join(STATE_DIR, 'custom_rules_state.json')
WINDOW, LAG = detect.WINDOW, detect.LAG
BACK = 3600              # after a stop: at most the last hour is checked again (no flood of old events)
TOP = 50                 # per-host rules: at most this many hosts per check


def threshold(rule):
    """The rule's threshold in the measure's own unit (bytes from MB)."""
    return float(rule['threshold']) * (1e6 if rule['measure'] == 'bytes' else 1)


def hits_of(rule, rows, ign=None):
    """The window's hits of one rule from its measured rows [(host or '', value)]."""
    thr, out = threshold(rule), []
    dev = next((f['v'] for f in rule['filters'] if f['k'] == 'device' and not f['neg']), '')
    for host, v in rows:
        if v < thr or (host and ign is not None and (host, 0) in ign):
            continue
        info = {k: rule[k] for k in ('name', 'sev', 'measure', 'threshold', 'minutes', 'per', 'traffic', 'filters')}
        info['rule'] = rule['id']
        out.append(detect._hit('custom', f"{rule['id']}>{host}" if host else rule['id'], {'ex': dev}, src=host, value=v, info=info))
    return out


class Runner:
    def __init__(self, measure, log=print):
        self.measure, self.log = measure, log
        self.notifier = None

    def state(self):
        try:
            with open(STATE) as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def save(self, done):
        tmp = STATE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'done': done}, f)
        os.replace(tmp, STATE)

    def tick(self, now=None):
        """Every closed window not checked yet (at most BACK); returns the number of hits stored."""
        now = int(now or time.time())
        last = (now - LAG) // WINDOW * WINDOW          # the end of the newest closed window
        done = max(int(self.state().get('done') or 0), last - BACK)
        cfg = detect.load_config()
        rules = [r for r in cfg.get('custom') or [] if r['on']]
        if not rules or not cfg['kinds']['custom']['on']:
            if done < last:
                self.save(last)
            return 0
        ign, found = detect.Ignore(cfg['ignore']), 0
        while done + WINDOW <= last:
            t1, hits = done + WINDOW, []
            for r in rules:
                try:
                    hits += hits_of(r, self.measure(r, t1 - r['minutes'] * 60, t1, TOP), ign)
                except Exception as ex:          # one rule (a filter no longer valid) never stops the others
                    self.log(f"WARN own rule «{r['name']}»: {str(ex)[:200]}")
            new = []
            if hits:
                found += detect.store(hits, done, t1, new)
            if new:
                self.notifier = self.notifier or notify.Notifier(self.log)
                self.notifier.push([{'kind': 'custom', 'row': x, 'sev': x['info'].get('sev')} for x in new], cfg['kinds'], t1)
            done = t1
            self.save(done)
        return found

    def run(self):
        while True:
            try:
                n = self.tick()
                if n:
                    self.log(f'own rules: {n} event update{"s" if n != 1 else ""}')
            except Exception as ex:
                self.log(f'WARN own rules: {str(ex)[:300]}')
            time.sleep(60)
