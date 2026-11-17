"""(2.9.0, issues #11 #12) Links between devices that do not depend on addresses: the LLDP neighbours each device
reports over SNMP, and the links an operator sets by hand in Settings → Devices. An unnumbered point-to-point link
(both ends borrow a loopback address) has no subnet of its own, so topology.build() could not see it before.

A link here is {a, a_ifs, b, b_ifs, how, a_port, b_port}: a_ifs / b_ifs are the candidate interfaces of each end,
the port LLDP names first, then the logical interfaces stacked over it (IF-MIB ifStackTable: a LAG, its VLAN units),
because NetFlow reports the logical one. topology.build() picks the candidate that carries the traffic.

Matching a neighbour to a device: its LLDP chassis ID = that device's own chassis ID, else a management address that
only that device has, else its system name = the device's (with or without the domain). Matching the far port: the
port ID that device gives its own port, else the interface name (exact, then short / long Cisco forms), a numeric
«local» port ID that is an ifIndex (Junos), else the port description."""
import re

import snmp

LINK_MAX = 8            # candidate interfaces kept per end (a port, its LAG and the LAG's VLAN units)


def _norm(name):
    """'GigabitEthernet0/0/1' and 'Gi0/0/1' -> 'gi0/0/1'; 'xe-0/0/0' -> 'xe0/0/0'; 'Port-channel1.20' -> 'po1.20'"""
    n = str(name or '').strip().lower()
    m = re.match(r'([a-z][a-z-]*?)-?(\d[\w/.:-]*)$', n)
    return m[1][:2] + m[2] if m else n


def _unique(hits):
    hits = sorted(set(hits))
    return hits[0] if len(hits) == 1 else None


def _by_name(ifs, text, cols=('name', 'descr')):
    """ifIndex whose name / description is `text` (exact, any case), else the same short form; one hit only."""
    t = str(text or '').strip().lower()
    if not t:
        return None
    hit = _unique(int(k) for k, i in ifs.items() if k.isdigit() and any(str(i.get(c) or '').strip().lower() == t for c in cols))
    if hit is not None:
        return hit
    n = _norm(t)
    return _unique(int(k) for k, i in ifs.items() if k.isdigit() and any(_norm(i.get(c)) == n for c in cols if i.get(c)))


def local_if(d, port):
    """The ifIndex of LLDP local port `port` of a device (its SNMP data `d`), or None."""
    ifs, ports = d.get('ifs') or {}, ((d.get('lldp') or {}).get('ports') or {})
    p = ports.get(str(port))
    if p:
        sub, hx, desc = p
        txt = snmp._text(hx)
        if sub == 7 and txt.isdigit() and txt in ifs:             # «local»: Junos gives the ifIndex itself
            return int(txt)
        hit = _by_name(ifs, txt, ('name', 'descr', 'alias') if sub == 1 else ('name', 'descr'))
        if hit is None and desc:
            hit = _by_name(ifs, desc)
        if hit is not None:
            return hit
    return int(port) if str(port) in ifs else None              # most devices number LLDP ports by ifIndex


def remote_if(d, psub, phex, pdesc):
    """The ifIndex of the far end's port as the neighbour advertised it; d = that device's SNMP data."""
    ifs = d.get('ifs') or {}
    ports = (d.get('lldp') or {}).get('ports') or {}
    own = [k for k, p in ports.items() if phex and p[1] == phex and (not psub or not p[0] or p[0] == psub)]
    if len(own) == 1:
        hit = local_if(d, own[0])
        if hit is not None:
            return hit
    txt = snmp._text(phex) if psub != 3 else ''                 # 3 = a MAC address: no interface name in it
    if psub == 7 and txt.isdigit() and txt in ifs:
        return int(txt)
    for t in (txt, pdesc):
        hit = _by_name(ifs, t)
        if hit is not None:
            return hit
    return None


def stacked(d, idx, skip=()):
    """`idx` and every interface stacked over it (LAG, VLAN units), nearest first; management interfaces left out."""
    up = (d or {}).get('stack') or {}
    out, todo = [], [idx]
    while todo and len(out) < LINK_MAX:
        i = todo.pop(0)
        if i in out:
            continue
        if i not in skip:
            out.append(i)
        todo += [h for h in up.get(str(i), []) if h not in out]
    return out


def _addrs(c):
    for addrs in (c.get('if_addrs') or {}).values():
        for a in addrs:
            yield str(a).split('/')[0]


def identities(cfg, data):
    """{chassis key: device}, {address: device}, {name: device} — keys that name exactly one device."""
    chassis, addr, name = {}, {}, {}

    def put(m, k, dev):
        if k:
            m.setdefault(k, set()).add(dev)
    for dev, c in cfg.items():
        d = data.get(dev) or {}
        lp = d.get('lldp') or {}
        ch = lp.get('chassis') or ['', '']
        if ch[1]:
            put(chassis, (ch[0], ch[1]), dev)
        for a in [dev, *(c.get('aliases') or []), *(c.get('public_ips') or []), *_addrs(c)]:
            put(addr, a, dev)
        for n in (lp.get('name'), (d.get('sys') or {}).get('name'), c.get('name')):
            n = str(n or '').strip().lower()
            if n and n != dev:
                put(name, n, dev)
                put(name, n.split('.')[0], dev)
    one = lambda m: {k: next(iter(v)) for k, v in m.items() if len(v) == 1}
    return one(chassis), one(addr), one(name)


def lldp_links(cfg, data, settings=None):
    """The links between known devices that their LLDP tables show (each seen from one or both ends)."""
    settings = snmp.load_settings() if settings is None else settings
    data = {dev: d for dev, d in data.items() if dev in cfg and settings.get(dev, {}).get('enabled')}
    by_chassis, by_addr, by_name = identities(cfg, data)
    links = {}
    for a, d in data.items():
        mg = set(cfg.get(a, {}).get('mgmt_ifs') or [])
        for port, csub, chex, psub, phex, pdesc, sysname, maddrs in (d.get('lldp') or {}).get('rem') or []:
            b = by_chassis.get((csub, chex)) if chex else None
            if not b:
                b = _unique(by_addr[m] for m in maddrs if m in by_addr)
            if not b:
                n = str(sysname or '').strip().lower()
                b = by_name.get(n) or by_name.get(n.split('.')[0])
            if not b or b == a:
                continue
            x = local_if(d, port)
            y = remote_if(data.get(b) or {}, psub, phex, pdesc)
            if x in mg or (y is not None and y in set(cfg.get(b, {}).get('mgmt_ifs') or [])):
                continue                                 # a management port: no part of the paths traffic takes
            ends = {a: (x, snmp._text(((d.get('lldp') or {}).get('ports') or {}).get(str(port), [0, '', ''])[1]) or str(port)),
                    b: (y, (pdesc or snmp._text(phex)) if psub != 3 else pdesc)}
            key = tuple(sorted((a, b)))
            lk = links.setdefault(key, {'a': key[0], 'b': key[1], 'a_ifs': [], 'b_ifs': [], 'how': 'lldp', 'a_port': '', 'b_port': ''})
            for e, dev in (('a', key[0]), ('b', key[1])):
                idx, port_name = ends[dev]
                if idx is not None:
                    for i in stacked(data.get(dev), idx, set(cfg.get(dev, {}).get('mgmt_ifs') or [])):
                        if i not in lk[e + '_ifs'] and len(lk[e + '_ifs']) < LINK_MAX:
                            lk[e + '_ifs'].append(i)
                if not lk[e + '_port'] and port_name:
                    lk[e + '_port'] = port_name
    return list(links.values())


def current(cfg):
    """address (current or earlier) -> the device's current address"""
    out = {}
    for dev, c in cfg.items():
        for a in c.get('aliases') or []:
            out.setdefault(a, dev)
    for dev in cfg:
        out[dev] = dev
    return out


def manual_links(cfg):
    """The links set by hand: device entry `links` {interface: [other device, its interface or None]}."""
    now, out, seen = current(cfg), [], set()
    for a, c in cfg.items():
        for x, peer in (c.get('links') or {}).items():
            try:
                b, y = now.get(peer[0]), (None if peer[1] in (None, '') else int(peer[1]))
                x = int(x)
            except (TypeError, ValueError, IndexError):
                continue
            if not b or b == a or (a, x) in seen:
                continue
            seen.add((a, x))
            if y is not None:
                seen.add((b, y))
            out.append({'a': a, 'b': b, 'a_ifs': [x], 'b_ifs': [] if y is None else [y], 'how': 'manual', 'a_port': '', 'b_port': ''})
    return out


def fixed(cfg, data=None, settings=None):
    """Every link known without the records: by hand first, then LLDP for the pairs of devices not set by hand."""
    data = snmp.load_data() if data is None else data
    man = manual_links(cfg)
    pairs = {frozenset((m['a'], m['b'])) for m in man}
    return man + [lk for lk in lldp_links(cfg, data, settings) if frozenset((lk['a'], lk['b'])) not in pairs]


def by_interface(links):
    """{(device, ifIndex): [{peer, peer_if, port, peer_port, how}]} — what Settings → Devices shows per interface."""
    out = {}
    for lk in links:
        for e, o in (('a', 'b'), ('b', 'a')):
            for i in lk[e + '_ifs']:
                out.setdefault((lk[e], i), []).append({'peer': lk[o], 'peer_if': lk[o + '_ifs'][0] if lk[o + '_ifs'] else None,
                                                      'port': lk[e + '_port'], 'peer_port': lk[o + '_port'], 'how': lk['how']})
    return out
