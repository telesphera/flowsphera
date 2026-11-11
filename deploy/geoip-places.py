#!/usr/bin/env python3
"""(2.6.0) Build the place index «country + city → coordinates» from the DB-IP Lite City database FlowSphera already
has (CC BY 4.0, https://db-ip.com), so a device described by City + Country lands on the map without coordinates.
Every IP range carries a country, a city and its coordinates; the index keeps each (country, city, region) once with
the coordinates seen most and the number of ranges (bigger places have more: a name used twice goes to the bigger).
Usage: geoip-places.py DIR  (reads DIR/dbip-city.mmdb, writes DIR/dbip-places.tsv atomically; ~2 min, run by
geoip-update.sh after a new edition or when the index is missing).
Line: CC <tab> key <tab> name <tab> region <tab> lat <tab> lon <tab> ranges — sorted by country, then ranges."""
import collections
import os
import sys
import unicodedata

NEAR = 0.5                 # degrees (≈ 35–55 km): a namesake closer than this is the same place


def fold(s):
    """The form names are compared in: no accents, no case, single spaces («Liège» = «liege»)."""
    s = unicodedata.normalize('NFKD', s or '')
    return ' '.join(''.join(ch for ch in s if not unicodedata.combining(ch)).casefold().replace('-', ' ').split())


def main(d):
    import maxminddb
    r = maxminddb.open_database(os.path.join(d, 'dbip-city.mmdb'))
    seen = collections.defaultdict(collections.Counter)          # (cc, name, region) -> Counter of (lat, lon)
    for _net, rec in r:
        cc = (rec.get('country') or {}).get('iso_code') or ''
        name = (((rec.get('city') or {}).get('names') or {}).get('en') or '').split(' (')[0].strip()
        loc = rec.get('location') or {}
        if len(cc) != 2 or not name or loc.get('latitude') is None or loc.get('longitude') is None:
            continue
        reg = (((rec.get('subdivisions') or [{}])[0].get('names') or {}).get('en') or '').strip()
        seen[(cc, name, reg)][(round(loc['latitude'], 4), round(loc['longitude'], 4))] += 1
    rows = []
    for (cc, name, reg), ll in seen.items():
        (lat, lon), _ = ll.most_common(1)[0]
        clean = lambda s: s.replace('\t', ' ').replace('\n', ' ')      # noqa: E731
        rows.append((cc, -sum(ll.values()), fold(name), clean(name), clean(reg), lat, lon))
    rows.sort()
    # the same name again close to a bigger one (a stray region on a few ranges: «Brussels, Wallonia» 2 km from
    # Brussels) is that place: dropped, so only real namesakes (Springfield, Illinois / Missouri) remain
    kept, near = [], collections.defaultdict(list)
    for row in rows:
        cc, _n, key, _name, _reg, lat, lon = row
        if any(abs(lat - a) < NEAR and abs(lon - b) < NEAR for a, b in near[(cc, key)]):
            continue
        near[(cc, key)].append((lat, lon))
        kept.append(row)
    rows = kept
    tmp = os.path.join(d, 'dbip-places.tsv.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        for cc, n, key, name, reg, lat, lon in rows:
            f.write(f'{cc}\t{key}\t{name}\t{reg}\t{lat}\t{lon}\t{-n}\n')
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(d, 'dbip-places.tsv'))
    print(f'geoip: place index built: {len(rows)} places')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/opt/flowsphera/geoip')
