# Configuration

[← FlowSphera](../README.md) · [Install](install.md) · [Exporters](exporters.md) · [Features](features.md) · [Editions](editions.md) · [Backups](backups.md) · [Configuration](configuration.md) · [API](api.md) · [Security](security.md) · [Performance](performance.md)

`/etc/flowsphera/env`:

| Variable | Default | Meaning |
|---|---|---|
| `FT_BIND`, `FT_PORT` | interface of the default route, `2055` | where NetFlow/IPFIX is received: interface name(s) and/or IP address(es), comma-separated, or `0.0.0.0` for all |
| `FT_SFLOW_PORT` | `6343` | UDP port for sFlow on the same addresses (`0` = off; sFlow sent to `FT_PORT` is taken as well) |
| `FT_EXPORTERS` | *(empty = any)* | allowed exporter IPs, comma-separated; devices added in the UI are allowed automatically |
| `FT_MAX_NEW_EXPORTERS` | `16` | with `FT_EXPORTERS` empty: how many sources not yet configured are tracked at once (they show in Settings → Devices to be set up; one idle for 15 min makes room) — a bound against packets with forged sender addresses |
| `FT_FORWARD` | *(empty)* | `host:port,…` — copy every datagram unchanged to other collectors |
| `FT_WORKERS` | `auto` | decoding processes; `auto` = half the CPU threads, at most 4 |
| `FT_RCVBUF` | `33554432` | UDP receive buffer in bytes (capped by `net.core.rmem_max`, which the installer raises to 32 MB) |
| `FT_WEB_BIND`, `FT_WEB_PORT` | interface of the default route, `3030` | web UI and API, same syntax — e.g. NetFlow on the external interface, the web UI only on the internal one. With specific interfaces in `FT_BIND` or `FT_WEB_BIND`, both services also answer on localhost (health checks, `ssh -L`, a local reverse proxy) and restart themselves when an interface's address changes (DHCP) |
| `FT_TLS_CERT`, `FT_TLS_KEY` | `/etc/flowsphera/tls/*.pem` | HTTPS certificate and key; empty = plain HTTP |
| `FT_CH_URL`, `FT_CH_USER`, `FT_CH_PASSWORD`, `FT_CH_DB` | | ClickHouse connection |
| `FT_CH_FSYNC` | `0` | `1` = the parts of flows, events and the rollups' state are written to the disk before they count (fsync): fewer records lost at a power cut, but inserts about 10× slower (measured 868 vs 79 ms at 5,000 records/s). Without it the database recovers by itself after a power cut too and reports it as an event (2.0.0 build 3); a UPS is the real cure |
| `FT_DNS_RATE` | *(empty = 20)* | (2.6.0) the default for *Settings → General → Host names from DNS*: `0` or `off` = no reverse DNS, `shown` = only the hosts a page shows, `5` / `20` / `50` = also the inside hosts of the week in the background, at most that many lookups a second; a choice saved in the settings wins |
| `FT_BACKUP_DIR` | `/var/backups/flowsphera` | where backups are kept on the server; change it with `sudo flowsphera upgrade --force --backup-dir DIR` (ClickHouse sees it as `/backups`) |

Devices are best described from the UI (*Settings → Devices → Connect device*, admins only; the collector picks
changes up within a minute). Those are kept in `/var/lib/flowsphera/exporters.json`. `/etc/flowsphera/exporters.json`
is for a deployment that brings its devices along (configuration management): empty (`{}`) on a normal install, and
an entry made in the UI overrides the same device there. *Export* / *Import…* on that page save every device to a
JSON file and bring it back (another server, or many devices edited by hand; SNMP secrets are not in the file).
A device whose export moves to another address: *Edit → Change address…* — everything set for it moves, and the old
address stays an alias, so its records keep counting as that device's. A source that sends but is not described shows
as «not described» and leaves the list 15 minutes after it stops; *Ignore* drops what it sends.

A device as either file (or an export) describes it:

```json
{
  "192.0.2.1": {
    "name": "fw-main", "vendor": "Fortinet", "model": "FortiGate 100F",
    "wan_ifs": [3], "local_if": 0, "public_ips": ["198.51.100.10"],
    "city": "Amsterdam", "country": "NL", "lat": 52.37, "lon": 4.9,
    "if_names": {"3": "wan1", "0": "local"}, "if_caps": {"3": [300, 50]}, "sampling": "1:1"
  }
}
```

`wan_ifs` are the exporter's interface indexes (`INPUT_SNMP`/`OUTPUT_SNMP`); `public_ips` mark traffic
the device itself originates; coordinates place the site on the map — (2.6.0) without them `city` + `country` do,
from the place list of the GeoIP data (see Features → How to put a device on the map).
`if_caps` (1.12) is an interface's capacity in Mbit/s, in and out — e.g. an ISP contract of 300 / 50 on a faster port;
without it the port speed read over SNMP (or sent in sFlow counters) is used for the interface load and the
*Link near capacity* event.
