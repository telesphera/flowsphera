# Features in detail

[← FlowSphera](../README.md) · [Install](install.md) · [Exporters](exporters.md) · [Features](features.md) · [Editions](editions.md) · [Backups](backups.md) · [Configuration](configuration.md) · [API](api.md) · [Security](security.md) · [Performance](performance.md)

**New in 1.16**
- **QoS (DSCP)**: the class each record carried on the way in (and on the way out where the device says, e.g.
  FortiGate) — classes over time, their shares, the class mix of each interface, what the devices re-mark, the
  services of each class; the filter `dscp:` (EF, AF41, CS1 … or 0–63) on every page.

**New in 1.15**
- **Usage**: what each host downloaded and uploaded this month, last month or the last 7 – 365 days (as far as the
  edition keeps data), against the same time before it; day by day, who uses most, the biggest changes, by network,
  every host as CSV. Everything FlowSphera keeps is shown somewhere and kept as long as the license says: the hourly
  per-host totals kept for 3 years whatever the edition (shown nowhere) are gone.

**New in 1.14**
- **Interface counters over SNMP** every minute: Capacity uses the device's own counters (every byte, the busiest
  minute) and shows how much of each link the flows see.

**New in 1.13**
- **Capacity**: a page for planning the links — each interface day by day (busy hours = 95th percentile, busiest 5
  minutes) against its capacity, the trend a month and the date it reaches 85 %, the load by weekday and hour, and
  the hosts and services that drive it; the same as *Link capacity* in the reports.

**New in 1.12**
- **Sign-in through Active Directory / LDAP**: the sign-in page offers «Local account» or your directory; roles from
  groups (nested in AD), LDAPS / STARTTLS, a *Check* that shows the user's groups and role before you switch it on.
- **Interface load**: peak / 95th percentile / average of every interface against its capacity (port speed or your
  own figures, in and out), and the event *Link near capacity*.

**New in 1.11**
- **API tokens** (*Settings → API*) for scripts and monitoring — read only, or read and change — and **webhooks**
  (FlowSphera JSON, Slack / Mattermost / Rocket.Chat, Discord; signed with HMAC-SHA256) next to Telegram and e-mail.
- **SIEM / syslog export**: every event as RFC 5424 syslog over UDP / TCP / TLS, in CEF or JSON, for Splunk, QRadar,
  ArcSight, Sentinel, Elastic, Graylog, Wazuh.

**New in 1.10**
- **Scheduled reports** (*Settings → Reports*): a PDF of the last day, week or month e-mailed at its hour — totals
  against the period before, traffic over time, the busiest hosts, outside networks, conversations, applications
  (categories, users, new ones), services, countries, ports, named networks, usage by host, traffic classes (DSCP),
  interfaces, link capacity, security events and devices (records/s over the period); English or Ukrainian, any time zone, on the weekday / day of the month you
  choose, narrowed by filters if you like; a period not fully collected yet is shown with a note, never as zeros.
  *Download PDF* and *Send now* any time.
- **Report for a period**: the report button in the top bar turns the period and filters on screen (an incident
  zoomed into) into the same PDF at once, or any *from – to*; administrators can e-mail it.
- *Settings → General → Mail server*: one SMTP server, tested from there, for the reports and the e-mail notifications.

**New in 1.8 – 1.9**
- *Path analysis* comes alive: five map views — **Classic**, **Lines**, **Stars**, **Metro** and **River** — with the
  traffic moving along every link in the direction it really goes, as dense and as fast as its rate. Each user keeps
  their own default view (the lamp), and every view opens full screen for a wall display.
- Honest link states: a **gap** only when one end sends real traffic towards the other, gets nothing back and the
  other end's interface records nothing; a silent interface on a working link is **One end silent** (NetFlow is off
  there); ends that simply differ (a big download one way, asymmetric routing, tunnels) are explained in hints.
- **Named networks** (172.16.0.0/24 → *Office*): filter with `net:Office`, and *Top hosts → Networks* shows the
  traffic, trend and main services of each network. (2.6.0) Without names the networks are found from the devices'
  interface addresses (SNMP or typed), with their own masks; an address in none of them falls into its /24, marked as
  a guess. Such a network is a filter by its address: `net:10.10.0.0/16`.
- Filters typed in the search box with a guide (every key with an example, suggestions, errors before applying);
  networks in `ip:` / `dst:`; several values of one key.
- (2.5.0) **Hosts by name** in the search box: part of a name offers every host whose name holds it — names you set,
  device addresses and reverse DNS; the reverse DNS names of the week's inside hosts are looked up in the background.
- **Full screen** for every Overview panel (lists show more rows, the Graph shows as many pairs as the screen holds),
  a **Copy** button on every ready-made configuration and command.
- Waiting that shows the work: sketches of the map assemble while the database reads, tables decode and then settle
  row by row, with real progress and *Cancel*.
- Settings → Flow configuration: your own names of ports, hosts and networks; the roles of your services.
- Backups you can delete from the web (confirmed with your password), keeping that reports what it could not delete.

**Collection**
- NetFlow v5, NetFlow v9, IPFIX and sFlow v5 from exporters on IPv4 or IPv6 (the collector and the web
  interface listen on both). Templates are tracked per exporter and per observation domain / source ID
  (line cards and virtual systems of one device may reuse template ids), and saved, so a collector restart
  does not drop the first minutes of data while waiting for the exporter to resend them.
- The protocol of every packet is recognised by itself. *Settings → Devices → Connect a device* gives ready
  configuration for Fortinet, Cisco, MikroTik, Juniper, Palo Alto, Check Point, SonicWall, Huawei, Arista,
  VyOS / EdgeOS, pfSense / OPNsense, HPE Aruba, Linux (pmacct, softflowd, hsflowd) and any other exporter, per export protocol the
  vendor offers (recommended one marked); the Devices page warns when a device sends another protocol than its
  description expects.
- sFlow v5 (switches, firewalls, Linux hosts) on UDP 6343 — or on the NetFlow port, it is recognised there too. The
  headers of the sampled packets (Ethernet, VLAN tags, IPv4 / IPv6 with extension headers, TCP / UDP / ICMP) are
  decoded in the compiled core and summed per minute into flows scaled by the sampling rate; lost datagrams are
  counted from their sequence numbers. The interface counters the agent sends are kept too: Settings → Devices →
  Interfaces shows each port's in / out load (and its share of the speed), speed, state, errors and discards —
  also for ports without sampled traffic. Detections that count sessions (scans, password guessing) see only the
  sampled part of the traffic; floods, bursts and IP reputation work as with NetFlow. On a router or firewall that
  does NAT, sample the LAN-side interfaces in both directions, not the WAN (there the packets carry the public address). Wi-Fi through FortiAPs in tunnel mode shows in sFlow
  as the access point's CAPWAP traffic, not as its clients — on such a FortiGate use NetFlow v9.
- Correct accounting of delta counters. FortiOS (like NetFlow v9/IPFIX in general) re-exports a long
  session every `active-flow-timeout`, and each export covers only its own interval — the next export's
  `FIRST_SWITCHED` equals the previous `LAST_SWITCHED`. Traffic is therefore the plain sum of records.
- Inside/outside endpoint and direction from the exporter's WAN interfaces (leaves via WAN = upload,
  arrives via WAN = download; FortiOS interface `0` = the firewall itself), or from RFC 1918 / CGNAT
  ranges when no interfaces are configured.
- Enrichment: country, city, coordinates and ASN of the outside address
  ([DB-IP Lite](https://db-ip.com/db/lite.php), CC BY 4.0), L7 protocol from protocol + port,
  service name from ASN or port, post-NAT address, inside host names from a names file and reverse DNS.
- Sampled exporters: the sampling rate is read from the record itself, from NetFlow v9 / IPFIX options
  records, from the NetFlow v5 header, or taken from the device settings (`"sampling": "1:N"`), and bytes
  and packets are scaled up accordingly. The rate is stored with every record and shown per device.
- Exporter health: records/s, templates, packets lost (sequence gaps), records skipped while waiting
  for a template, effective sampling rate.
- Several decoding workers (`FT_WORKERS`): one receiver process only reads the socket and spreads
  packets over the workers, templates go to all of them — so even a single busy exporter uses many
  cores, and a slow database never stalls the socket.
- Collector health: packets dropped by the kernel (socket buffer full), by the worker queues, and records
  lost while ClickHouse was unreachable — shown in Settings → Devices and raised as an event.
- Optional raw forwarding (`FT_FORWARD`) so another collector keeps receiving the same feed.
- Optional SNMP v2c / v3 per device (Settings → Devices): interface names, descriptions, state and IP addresses
  (IPv4 and IPv6, with prefix) read from IF-MIB / IP-MIB when the device is saved and then every hour. They name the
  interfaces on *Through device* and *Path analysis* and place the devices by subnet; names and addresses entered by
  hand win. Without SNMP the interfaces show what the records reveal (inside networks, NAT address).

**Web UI**
- *Overview*: KPIs with trend against the previous period, live inside ↔ outside exchange, connection
  map and 3D globe, top services, hosts, conversations, latest flows.
- *Flows*: top-10 inside × top-10 outside exchange (ribbon width = bytes, packets or flows; colour =
  direction), inspector for the selected host or conversation, protocols, raw flow records with NAT,
  ASN and interfaces.
- *Through device*: one exporter as a box — input interface → output interface, hosts behind each interface; below
  it *Interface load*: every interface's peak, 95th percentile and average in and out over the period against its
  capacity (the port speed from SNMP / sFlow, or your own figures in and out — Settings → Devices → Interfaces), from
  the 5-minute totals, with a small chart; the fullest first.
- *Capacity*: every interface of every device over 7 to 365 whole days (as far as the edition shows), all traffic
  whatever the selector and filters. Per day: the 95th percentile of the 5-minute load (empty 5 minutes count as 0)
  and the busiest 5 minutes, in and out, against the capacity. The trend is a Theil–Sen median over days a whole
  number of weeks apart (quiet weekends are no decline, an odd day does not tilt it) on the busy days' level; a
  forecast needs 14 complete days and reaches at most twice the history it rests on, so it gives the date a link
  reaches 85 % and 100 % or says «not within N days». Days on which a device was mostly silent are left out of the
  trend. A link in depth: chart with the capacity and the forecast, one sentence, weekday × hour (the busiest 5
  minutes of each hour averaged over the weeks), and the inside hosts and services on it, recent half against
  earlier. Status: over the limit · near full (85 % now or within a month) · will fill (within the forecast) · worth
  watching (busy hours above 70 % or peaks above 85 %) · fine · capacity unknown.
  With SNMP on (1.14), the collector reads every interface's octet counters each minute (ifXTable 64-bit, else
  ifTable 32-bit with wraps undone; errors, discards, state) into `if_counters` (src `snmp`, kept 90 days). A day with
  counters for at least half of its 5-minute periods takes their figures — the 95th percentile of the 5-minute rates
  and the busiest minute — and *Flows see* compares the flows' bytes with the counters' for the days both have.
- *Usage*: per inside host, downloaded (from outside, or between your hosts with the traffic selector) and uploaded
  over this month, last month or 7 – 365 whole local days, read from the 5-minute per-host totals (`agg_host`, kept per
  record as long as the edition says). The same length of time before is compared only when the data reach back to its
  start. Cards (downloaded, uploaded, active hosts with the change; the share of the 10 busiest), the days (months over
  92 days), who uses most, the biggest changes, by named network, then the table (500 busiest; all: *Download CSV* =
  `/api/top?dim=int_ip&limit=all&format=csv` with the same period and filters).
- *QoS*: DSCP from NetFlow v5 (ToS), v9 / IPFIX (SRC_TOS 5 and DST_TOS 55, ipDiffServCodePoint 195 and
  postIpDiffServCodePoint 98) and sFlow (the sampled header's ToS / traffic class, the sampled IPv4 / IPv6 records),
  decoded by the core (1.6.0). `dscp` = the class on the way in, `dscp_out` = on the way out where the exporter sends
  it; 255 = not sent (records from before 1.16 too). Read from the rollups `agg_dscp` (5 min: in / out interface,
  class in and out) and `agg_dscp_svc` (1 h: class, service, L7, inside host). Cards: marked share, voice and video
  (EF, VA, CS4, CS5, AF4x), re-marked share, not reported; then classes over time, shares, interfaces, re-marking,
  services per class, the classes table (a row filters every page). The record inspector on *Flows* shows the class.
- *Path analysis*: the layer-3 neighbours of a chosen device (shared subnets, or found from the records — tunnels
  included) with each link's traffic as both ends recorded it, links whose far end is not seen or where traffic goes
  missing, and the hops of any source → destination path across the devices, with NAT and gaps.
- *Hosts*, *Services*, *Geolocation* (live arcs as flows arrive, countries, ASNs). (2.6.0) A device stands on the map
  by its City + Country code alone — the place comes from the DB-IP city data FlowSphera installs, offline; the
  device dialog offers the country's places as you type, and Latitude/Longitude, if set, take priority.
- *Events*: port scans, password guessing on SSH / RDP / management ports, a daily summary of who probes them,
  aggressive web clients, DDoS (floods of a service, inbound volume, UDP reflection — against the network's own
  usual peak), inside hosts that scan the internet or the LAN, contact with addresses on IP reputation lists
  (botnet controllers, malware hosts, criminal netblocks, attackers — eight free public lists, (2.6.0) up to ten lists of your own by URL, plus your own list; ThreatFox
  asks for abuse.ch's free Auth-Key, entered in Settings → Events → IP reputation, where any list can get a key); plus
  sustained upload, bursts, new countries, export health, links near their capacity, and scheduled reports that could
  not be sent. FlowSphera works out who opened each connection (NetFlow has no such field) and which of your
  services are public, so web sites with thousands of visitors stay quiet. One event per source that grows while it
  goes on; each kind can be switched off, given a priority and its thresholds; addresses, networks and ASNs can be
  ignored and a connection excluded in one direction (Settings → Events → Exceptions). New events can go to Telegram
  through your own bot, by e-mail (the mail server of Settings → General), to a webhook (FlowSphera JSON, Slack /
  Mattermost / Rocket.Chat, Discord; HMAC-signed) and to a SIEM as syslog (RFC 5424, CEF or JSON, over UDP / TCP /
  TLS) — once each, by priority and kind, per channel; the SIEM gets every event, without the hourly limit.
- *Reports*: a PDF of the last day, week (on the weekday you choose) or month (on the day you choose), e-mailed at its
  hour to its own recipients, in English or Ukrainian, in any time zone, optionally narrowed by filters — totals
  against the period before, traffic over time, busiest hosts, outside networks, services, countries, named
  networks, events and devices; a period not fully collected is shown with a note, never as zeros. *Report for a
  period* (the report button in the top bar) makes the same PDF of exactly the period and filters on screen.
- *Settings* — tabs for language, version and the mail server, devices (exporters, interfaces and their capacity),
  flow configuration (your own names of ports and hosts, the roles of your services), users and sign-in through the
  directory, events and notifications, backups, reports, API tokens, and the edition / license.
- Any period within the kept flow details (30 days in Community, see [Editions](editions.md)): a preset, *Custom period…* (from / to, to the minute) or
  drag across a traffic chart to zoom in — every page follows, and the link keeps the period, so an
  incident view can be bookmarked or shared.
- Every value is a click-to-filter; filters can also be typed: `ip:10.0.0.5 service:Telegram -country:US port:443`.
- Two roles: **admin** (everything) and **viewer** (read-only). Users are local, or — when it is set up — sign in
  through Active Directory / LDAP: the sign-in page asks how, the role comes from the user's groups (nested ones in
  AD), LDAPS / STARTTLS; at least one local administrator always remains. **API tokens** (read only, or read and
  change) let scripts and monitoring use the API without a password, see [API](api.md#api-tokens).
- English and Ukrainian, chosen per browser in Settings → General; the browser language picks the default. More
  languages are one file each, see [Translations](translations.md).

## How to put a device on the map

The connection map and the 3D globe draw a line from each of your devices to the far end of every connection. A device
needs a place for that, and since 2.6.0 its city is enough:

1. Open *Settings → Devices*, pick the device and press *Edit* (or *Connect a device* for a new one).
2. Type the two-letter **Country code** (for example `BE`, `UA`, `NL`), then start typing the **City**. FlowSphera
   offers the places of that country whose name begins with what you typed — with the region and the coordinates —
   biggest first. Names are matched without accents and case: `liege` finds *Liège*.
3. Pick one, or just type the whole name. The line under *Latitude* and *Longitude* says where the map will put the
   device, e.g. *On the map at Brussels, Brussels Capital (50.85, 4.36) — from City + Country*.
4. *Save*. The device is on the map at once; a device saved earlier with City and Country but no coordinates is placed
   too, without saving it again.

Latitude and Longitude still win when you fill them in — for a site on the edge of a city, or a place the list does
not know. The places (about 150,000) are built from the DB-IP Lite City database that FlowSphera already installs for
GeoIP (CC BY 4.0): nothing is sent to an online geocoding service. The list is made again after each monthly database
refresh (`/opt/flowsphera/geoip/dbip-places.tsv`); a name used in two regions of one country (Springfield, Illinois /
Missouri) offers both, and picking one keeps its exact coordinates.

## How to see your networks without naming them

*Top hosts → Networks* groups the traffic by network: the volume, the trend, the hosts, the main service of each, and
a click adds the network to the filters. You do not need to set anything up first:

- **Named networks** (*Settings → Flow configuration → Networks*, e.g. `172.16.0.0/24 → Office`) come first.
- **Networks found from your devices.** Every address of a device interface — read over SNMP, or typed in *Settings →
  Devices → Edit → Interfaces* — gives its network with its own mask: `10.10.0.1/16` on an interface is one network
  `10.10.0.0/16`, not 256 small ones. The row says which interface of which device it was found on
  (*lan · edge-fw · found from the device*).
- **A /24 guess** for an inside address in none of them, marked *a /24 guessed from the addresses*: turn SNMP on for the
  device, type the interface addresses, or give the network a name to replace it.

The same networks fill the *Your networks* part of the PDF reports, and `net:<address>` filters every page by one of
them, exactly as the row counts it.

## How to add an IP reputation list by URL

FlowSphera checks every connection against eight public reputation lists. To add a list of your own that lives on the
web — a vendor's feed, your SOC's export, a partner's list of scanners:

1. Open *Settings → Events → IP reputation* and press **Add a list by URL** (up to ten lists).
2. Give it a **name** (shown in the events and the notifications), paste the **URL** (`http://` or `https://`),
   choose **what it holds** — malware (contact is critical), criminal netblocks, hosts seen attacking, spam sources (2.6.0, e.g. Spamhaus SBL or UCEPROTECT) or Tor exits —
   and **how often** to download it: every hour, every 6 or 12 hours, daily or weekly.
3. *Save*. The list is downloaded within 10 minutes, then on its schedule; the table shows how many entries it holds
   and when it was last updated.

Formats read by themselves: plain text with one address or network per line (`#` and `;` start a comment, so a list
such as Spamhaus DROP works as published), CSV (the first column), JSON (an array of addresses, or of objects with
`ip`, `cidr`, `network` or `address`) and JSON lines. Private and reserved ranges and blocks wider than /8 are always
left out, so a mistake in a list never marks your LAN or the whole internet. A download that fails or comes back empty
keeps the last good copy and says so in the table (and in the collector's journal); changing a list's URL downloads it
again at once, and removing a list removes its copy.


## How host names are found — and what FlowSphera asks your DNS server

Every page shows an inside host by its name when it has one. The name comes from, in this order:

1. **The name you give it** — *Settings → Flow configuration → Hosts*, one by one or as a CSV file. It always wins.
2. **A device's own address** — shown as *fw-main (self)*.
3. **Reverse DNS (PTR)** — asked from your DNS server with the FlowSphera server's own resolver, for **private
   addresses only** (public ones are shown with their owner and country from GeoIP instead).

The names appear in every table and chart, the host card, the conversations, *Capacity* (the hosts behind the growth),
the text of the events and of every notification (Telegram, e-mail, webhooks, SIEM), the PDF reports and the CSV
exports, and the search box finds a host by any of them.

**Settings → General → Host names from DNS** decides how much FlowSphera asks your DNS server (since 2.6.0):

| Choice | What is asked | When to choose it |
|---|---|---|
| **In the background** (default) | the inside hosts seen in the last 7 days, busiest first, at most 20,000, each **once a day** — at most 5, 20 (default) or 50 lookups a second and never more than 4 at a time | most networks: the search box finds any host by name |
| **Only shown hosts** | the inside hosts a page shows, each at most once an hour (the behaviour before 2.5) | a DNS server you want to touch as little as possible |
| **Off** | nothing; DNS names are not shown | no PTR records in your network, or a policy that forbids it |

The load stays small even on a big network: 20 lookups a second is the ceiling of the first pass of the day (about 17
minutes for 20,000 hosts), the answer — also «no name» — is kept for 24 hours and across restarts
(`/var/lib/flowsphera/dns_names.json`), and with only 4 lookups in flight a slow DNS server automatically gets fewer.
A DNS server easily answers thousands of queries a second, and the network's own computers send far more.

Turn it down or off when your DNS server has **no reverse zones for its private ranges and forwards those PTR queries
to your provider or a public resolver**: they would then leave your network. Well-run servers answer private ranges
themselves (RFC 6303). For an install made by a script, `FT_DNS_RATE` in `/etc/flowsphera/env` gives the default:
`0` (off), `shown`, or `5` / `20` / `50`; a choice saved in the settings wins over it.

**Addresses from DHCP.** A name belongs to the address at the time it was looked up and is refreshed daily (hourly for a
host a page shows). With DHCP that registers its leases in DNS (Active Directory, most office setups) the names follow
the leases within that time; the records themselves keep the address, so a period long ago is labelled with the
address's name of today. Names you give by hand belong to the address as well — for a host that must keep its name,
reserve its address in DHCP.

## MikroTik VPN and PPPoE sessions

RouterOS makes a new interface — with a new number — for every VPN (SSTP, L2TP, PPTP, OpenVPN) or PPPoE session, e.g.
`<sstp-alice>`. Since 2.6.0 FlowSphera keeps the name of every interface number it has seen (read over SNMP every
minute with the counters), so a session that ended still shows its name, and these interfaces are folded into one line
per name — on *Capacity* (they are no links to plan) and in *Settings → Devices*. The `iface:<sstp-alice>` filter
covers all the sessions of that name. To have one interface per user instead, give each user a static server binding
on the MikroTik: `/interface sstp-server add name=sstp-alice user=alice` (likewise `l2tp-server`, `pptp-server`,
`ovpn-server`, `pppoe-server`).
