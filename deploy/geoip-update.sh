#!/bin/sh
# Refresh the DB-IP Lite databases (free, CC BY 4.0). flowsphera-geoip.timer runs this daily; it downloads only
# when a newer monthly edition than the installed one is published, so a failed or early attempt is simply
# retried the next day. FT_GEOIP_FORCE=1 downloads regardless.
set -eu
DIR=${FT_GEOIP_DIR:-/opt/flowsphera/geoip}
STAMP="$DIR/edition"                     # YYYY-MM of the installed databases
mkdir -p "$DIR"
# (2.6.0) the place index «country + city -> coordinates» (geoip-places.py) is made from the city database; a missing
# or older one is made again. It is only a convenience: failing it never fails the refresh.
H=$(cd "$(dirname "$0")" && pwd)
PY=${FT_PY:-$H/../../venv/bin/python}
places() {
  [ -s "$DIR/dbip-city.mmdb" ] || return 0
  [ -s "$DIR/dbip-places.tsv" ] && [ ! "$DIR/dbip-places.tsv" -ot "$DIR/dbip-city.mmdb" ] && return 0
  nice -n 10 "$PY" "$H/geoip-places.py" "$DIR" || echo "geoip: could not build the place index" >&2
}
cur=$(date +%Y-%m)
prev=$(date -d "$(date +%Y-%m-01) -1 day" +%Y-%m 2>/dev/null || echo "$cur")
have=$(cat "$STAMP" 2>/dev/null || true)
[ -s "$DIR/dbip-city.mmdb" ] && [ -s "$DIR/dbip-asn.mmdb" ] || have=""
if [ "$have" = "$cur" ] && [ -z "${FT_GEOIP_FORCE:-}" ]; then
  places
  exit 0                                 # already up to date
fi

# both files of one edition, or nothing
fetch() {
  for f in city asn; do
    curl -fsSL --retry 2 --max-time 600 "https://download.db-ip.com/free/dbip-$f-lite-$1.mmdb.gz" \
      | gunzip > "$DIR/dbip-$f.mmdb.tmp" 2>/dev/null && [ -s "$DIR/dbip-$f.mmdb.tmp" ] || return 1
  done
}
cleanup() { rm -f "$DIR/dbip-city.mmdb.tmp" "$DIR/dbip-asn.mmdb.tmp"; }
trap cleanup EXIT

got=""
if fetch "$cur"; then
  got=$cur
elif [ "$have" != "$prev" ] && fetch "$prev"; then
  got=$prev                              # early in the month the new edition may not be out yet
fi
if [ -z "$got" ]; then
  if [ -n "$have" ]; then
    echo "geoip: no newer edition available yet (installed: $have); will retry tomorrow"
    places
    exit 0
  fi
  echo "geoip: could not download the DB-IP databases" >&2
  exit 1
fi
for f in city asn; do mv "$DIR/dbip-$f.mmdb.tmp" "$DIR/dbip-$f.mmdb"; done
chmod 644 "$DIR"/dbip-*.mmdb
echo "$got" > "$STAMP"
echo "geoip: installed DB-IP Lite $got (was: ${have:-none})"
places
# the collector caches lookups; restart it so new data is used
systemctl try-restart flowsphera-collector.service 2>/dev/null || true
