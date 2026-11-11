<p align="center">
  <img src="docs/media/banner-en.webp" alt="FlowSphera by TELESPHERA — see every flow, trust every number" width="100%">
</p>

<p align="center">
  <a href="https://github.com/telesphera/flowsphera/tags"><img alt="Version" src="https://img.shields.io/github/v/tag/telesphera/flowsphera?filter=v*&sort=semver&style=flat-square&color=2F7BFF&label=version"></a>
  <img alt="NetFlow v5/v9 · IPFIX · sFlow v5" src="https://img.shields.io/badge/NetFlow%20v5%2Fv9%20%C2%B7%20IPFIX%20%C2%B7%20sFlow%20v5-27D3F5?style=flat-square">
  <img alt="Linux x86_64 · arm64" src="https://img.shields.io/badge/Linux-x86__64%20%C2%B7%20arm64-0B1736?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Elastic%202.0-8B5CFF?style=flat-square"></a>
</p>

<p align="center">
  <b>English</b> · <a href="README.uk.md">Українська</a>
  <br><br>
  <a href="#install-in-one-command"><b>Install</b></a> ·
  <a href="#a-tour">Tour</a> ·
  <a href="#works-with-your-equipment">Supported devices</a> ·
  <a href="#editions">Editions</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="mailto:flowsphera@telesphera.net?subject=FlowSphera">Contact</a>
</p>

**FlowSphera** turns the NetFlow, IPFIX and sFlow your firewalls, routers and switches already send into a clear, live
picture of your network: who talks to whom, how much, over which service, from where and along which path. It runs on
your own server, installs with one command and is ready in minutes.

> FlowSphera was called **FlowTrack** until version 1.17. Since 2.0 every name on the server is FlowSphera too: the
> `flowsphera` command, the services, the folders. An existing installation upgrades as before — `sudo flowtrack
> upgrade` moves it to the new names by itself and keeps the old command as a synonym until 3.0.

<p align="center">
  <img src="docs/media/en/live-map.webp" alt="Live connection map: new connections arrive as arcs" width="100%">
</p>

## Why FlowSphera

<table>
<tr>
<td width="33%" valign="top"><b>Ready in minutes</b><br>One command installs everything — database, web interface, HTTPS — and hands you a ready-made configuration for your firewall or router.</td>
<td width="33%" valign="top"><b>Numbers you can trust</b><br>Correct accounting of long sessions, sampling and duplicate exports; every lost packet is counted and shown, never silently dropped.</td>
<td width="33%" valign="top"><b>See the path, not just the flows</b><br>How traffic crosses your devices, interface by interface — and which link really has a problem.</td>
</tr>
<tr>
<td valign="top"><b>Security built in</b><br>Port scans, password guessing, floods, contact with known malicious addresses, links running full — with alerts to Telegram, e-mail, webhooks and your SIEM.</td>
<td valign="top"><b>Made for the wall</b><br>Live maps, a 3D globe and animated traffic views that run full screen on a NOC display — smooth, light on the CPU.</td>
<td valign="top"><b>Yours</b><br>Self-hosted, no cloud, no telemetry. Every feature is free; a license only raises the limits.</td>
</tr>
<tr>
<td valign="top"><b>Reports that arrive</b><br>A PDF for the management or the duty engineer — daily, weekly or monthly by e-mail, or for exactly the incident on your screen.</td>
<td valign="top"><b>Fits your company</b><br>Sign in with Active Directory or LDAP; roles from your groups; local accounts stay as a way in.</td>
<td valign="top"><b>Connects to your tools</b><br>API tokens for scripts and monitoring, webhooks for chats and your own systems, syslog (CEF / JSON) for the SIEM.</td>
</tr>
</table>

## A tour

### Path analysis — watch traffic move through your network

Every device that exports flows, its neighbours, and the traffic on each link as both ends recorded it — in motion,
in the direction it really goes. A real gap is shown only when traffic goes in and nothing comes back; everything else
is explained in plain words. Trace any source → destination path hop by hop, with NAT.

<p align="center"><img src="docs/media/en/path-lines-live.webp" alt="Path analysis, Lines view, traffic moving along the links" width="100%"></p>

Pick the look that suits you — every user keeps their own default view:

<table>
<tr>
<td width="33%" align="center"><img src="docs/media/en/path-stars.webp" alt="Stars view"><br><b>Stars</b></td>
<td width="33%" align="center"><img src="docs/media/en/path-metro.webp" alt="Metro view"><br><b>Metro</b></td>
<td width="33%" align="center"><img src="docs/media/en/path-river.webp" alt="River view"><br><b>River</b></td>
</tr>
</table>

### Overview — the whole network at a glance

Totals with trends, the live connection map or a 3D globe, top services, hosts and conversations. Every panel opens
full screen. Your devices stand on the map by their city and country alone — no coordinates to look up, and no online
service asked.

<p align="center"><img src="docs/media/en/overview.webp" alt="Overview page" width="100%"></p>

<p align="center"><img src="docs/media/en/globe.webp" alt="3D globe with live connections" width="100%"></p>

### Flows — who exchanges how much with whom

The busiest inside hosts and outside addresses as a living diagram: width is volume, colour is direction. Click to
inspect, Shift+click to filter, down to the raw records with NAT, ASN and interfaces.

Beside it, **Ingest** shows what every device sends over the chosen period: records per second, the busiest minute,
your license limit as soon as traffic comes near it and the moments records went over it — so a scan from the Internet
or a device that stopped exporting stands out at once. Drag across it to zoom, open it full screen for detail.

<p align="center"><img src="docs/media/en/flows.webp" alt="Flows: the exchange between inside hosts and outside addresses; on the right the Inspector and Ingest — records per second from each device over the last 24 hours" width="100%"></p>

### Conversations — who talks to whom

Every pair of an inside host and whom it talks to, over any period: our hosts → the services → who owns the addresses
outside (or the countries, or the addresses), as a flow, a chord or a matrix with exact bytes. Cards tell how many
pairs there are against the period before, the biggest one, the countries — and the **new conversations**: a host
talking to an owner it had not talked to in the 7 days before, the first sign of a new cloud service, an infected
machine or data leaving. Every pair with both directions, a search, «Only new» and CSV; a click filters every page.

<p align="center"><img src="docs/media/en/conversations.webp" alt="Conversations: pairs against the period before, the biggest pair, new conversations, countries; who talks to whom as a flow from hosts through services to the owners outside" width="100%"></p>

<table>
<tr>
<td width="50%"><img src="docs/media/en/conversations-chord.webp" alt="Who talks to whom as a chord"></td>
<td width="50%"><img src="docs/media/en/conversations-new.webp" alt="The biggest pairs over time and the new conversations"></td>
</tr>
</table>

### Through device — inside one firewall

Input interface → device → output interface, the hosts behind each, and what each path carries.

<p align="center"><img src="docs/media/en/through-device.webp" alt="Through device page" width="100%"></p>

**Interface load** — how full every link is: the peak, the 95th percentile and the average in and out against its
capacity (the port speed, or your own figures such as an ISP contract of 300 / 50), and an alert when a link stays
near its limit.

<p align="center"><img src="docs/media/en/interface-load.webp" alt="Interface load: peak, 95th percentile and average against the capacity" width="100%"></p>

### Capacity — know when a link fills up, weeks ahead

Every link of every device, day by day: how full it is in the busy hours, how fast that grows and **the date it
reaches 85 %** of its capacity — so the upgrade is ordered before users feel it, not after. The trend meets the
capacity on the chart, the heat map shows the hours of the week when the link is busy, and one sentence says it in
words. Quiet weekends do not pass for a decline, a noisy link is called unsteady instead of given a made-up date.

<p align="center"><img src="docs/media/en/capacity.webp" alt="Capacity: links near full, the first to fill, the fastest growth, how much the flows see; the trend meeting the capacity on a date; the busy hours of the week" width="100%"></p>

**The interfaces' own counters.** With SNMP on, FlowSphera reads every interface's octet counters each minute: the
figures are every byte the port carried and the busiest minute, not only what the device exports — and it compares
the two. When the flows see only part of a link (an interface without a sampler, traffic exported twice), the page
says so at the top. Below: every link with its busy-hour load, trend, the date it fills and what the flows see; the
hosts and services that drive the growth; and the same in your scheduled reports as *Link capacity*.

<p align="center"><img src="docs/media/en/capacity-table.webp" alt="All links: status, capacity, busy-hour load in and out, trend, the date each reaches 85 %, how much of it the flows see" width="100%"></p>

### QoS — see how your traffic is prioritised

Every packet carries a class (DSCP) that tells the network what to put first — voice before downloads. FlowSphera shows
how much of your traffic is marked and how, which classes cross each interface, which services fall into each class
(is Zoom really voice and video, or best effort?), and what your devices re-mark on the way through. A class is a
filter like any other: `dscp:EF` narrows every page to it.

<p align="center"><img src="docs/media/en/qos.webp" alt="QoS: marked share, voice and video, re-marked traffic; classes over time and their shares; the class mix of each interface; what the firewall re-marks" width="100%"></p>

### Top hosts and your own networks

Name your networks once (*172.16.0.0/24 → Office*) and see the traffic, trend and main services of each — or of every
single host. **No names yet? The networks are already there:** FlowSphera finds them from the addresses of your
devices' interfaces, with their own masks — a `/16` stays one network, not 256 pieces — and says which interface of
which device each one sits behind. A name you give wins.

<p align="center"><img src="docs/media/en/networks-auto.webp" alt="Top networks with no setup: a named network (Servers) and two found from the devices' interfaces — lan of edge-fw, bridge of branch-rtr" width="100%"></p>

### Usage — who used how much

What each host downloaded and uploaded over the period at the top — an hour, a day, a month or the dates you choose —
against the same time before it: totals and the change, the days, who uses most, who grew or dropped, each of your networks. Narrow it to a network,
a device or a service like any page; the full list of hosts downloads as a CSV for Excel or billing.

<p align="center"><img src="docs/media/en/usage.webp" alt="Usage: downloaded and uploaded against the week before, day by day, who uses most, the biggest changes, by network" width="100%"></p>

### Services, countries, ASNs

<table>
<tr>
<td width="50%"><img src="docs/media/en/services.webp" alt="Services page"></td>
<td width="50%"><img src="docs/media/en/geo.webp" alt="Geolocation page"></td>
</tr>
</table>

### Applications — what your firewall knows about every session

FortiGate (with Application Control) and Palo Alto (with *PAN-OS Field Types*) know what each session really is —
Microsoft 365, Zoom, YouTube, SSH, a VPN proxy — and Palo Alto also who opened it. FlowSphera shows it on a page of
its own, in the menu as soon as a device names applications: applications over time, their categories, the users,
and **the applications that appeared only lately** — a proxy on a laptop or a new AI service is visible the same day.
`app:` and `user:` filter every page, down to the records.

<p align="center"><img src="docs/media/en/applications.webp" alt="Applications: 20 named in a week, applications over time, ten categories with Collaboration first, and two new ones — Hotspot.Shield (Proxy) and Claude (GenAI)" width="100%"></p>

### Find anything by typing

`ip:10.0.0.5 service:Telegram -country:US port:443 net:Office` — the search box guides you through every filter, and
every value on every page is a click-to-filter. Any period from the last 15 minutes to a month, or your own down to
the minute; the link keeps it, so an incident view can be shared.

<p align="center"><img src="docs/media/en/search.webp" alt="Search box with filter guide" width="80%"></p>

Hosts are found by name too: type part of a name and the box offers every host whose name holds it — names you set
and names from reverse DNS. FlowSphera looks up the reverse DNS names of the week's inside hosts in the background and
keeps them across restarts, so a host is found even if no page has shown it yet.

<p align="center"><img src="docs/media/en/search-names.webp" alt="Typing «laptop» offers four hosts: laptop-guest.office.lan from reverse DNS and three names set by hand, each with its address" width="80%"></p>

### Security events

Port scans, password guessing on SSH / RDP / management ports, floods and DDoS against your usual peak, inside hosts
that scan, contact with addresses on eight public reputation lists (plus your own), sustained uploads, new countries
and exporter health. **Add any blocklist by its URL** — text, CSV or JSON, refreshed every hour to every week — next
to the built-in ones. FlowSphera works out who opened each connection and which of your services are public, so busy
web sites stay quiet. New events go to Telegram (your own bot), e-mail, webhooks (Slack, Mattermost, Discord or your
own system) and your SIEM as syslog (CEF or JSON).

The page shows the picture first: how many events of each priority, how their number changes over the period by kind,
and the share of each kind. Pick a priority or a kind and the chart, the ring and the list follow it. Below — the newest
30 events with Filter / Exclude / Ignore; **All events** pages through the rest with a search by address or text.

<p align="center"><img src="docs/media/en/url-lists.webp" alt="IP reputation: lists by URL — name, address, what it holds, how often it is downloaded" width="100%"></p>

<p align="center"><img src="docs/media/en/events.webp" alt="Events page: cards by priority, events over time by kind, the share of each kind, the newest events with Filter / Exclude / Ignore" width="100%"></p>

The same two charts open the *Security events* part of every PDF report:

<p align="center"><img src="docs/media/en/report-events.webp" alt="Security events in a PDF report: events over time by kind and the share of each kind" width="80%"></p>


### Reports — by e-mail, on schedule or for any period

A PDF for the management or the duty engineer: totals against the period before, traffic over time, the busiest hosts,
outside networks, the conversations and the new ones, the applications your firewall named (with their categories, users and
the new ones), services, countries, ports, your networks, usage of every host, traffic classes (DSCP), the load of every
interface, link capacity with the date each link fills, security events and the devices with their records per second. Daily, weekly or monthly on
the day and hour you choose, in English or Ukrainian — or, after an attack or an outage, for exactly the period and
filters on your screen, with one click.

<table>
<tr>
<td width="58%"><img src="docs/media/en/reports.webp" alt="Settings → Reports: scheduled reports"></td>
<td width="42%"><img src="docs/media/en/report-pdf.webp" alt="A report as PDF"></td>
</tr>
</table>

### Fits into your company

**Sign in with Active Directory or LDAP**: the sign-in page asks how to sign in — your directory or a local account —
and the role comes from the user's groups (nested ones too); LDAPS / STARTTLS, a check that shows what FlowSphera finds
for a user before you switch it on. **API tokens** let scripts and monitoring (Zabbix, Grafana, your own) read
FlowSphera — or change it, with a token that may — without a password; every host of a network with its upload and
download for any period comes as JSON or a CSV file for Excel or billing ([how](docs/api.md#export-every-host-of-a-network)). **Webhooks** send new events to Slack,
Mattermost, Rocket.Chat, Discord or your own system (signed with HMAC), and **syslog** in CEF or JSON feeds Splunk,
QRadar, ArcSight, Microsoft Sentinel, Elastic, Graylog or Wazuh.

<table>
<tr>
<td width="28%" valign="top"><img src="docs/media/en/sign-in.webp" alt="Sign-in with the directory offered"></td>
<td width="72%" valign="top"><img src="docs/media/en/api-tokens.webp" alt="Settings → API: tokens and examples"></td>
</tr>
</table>

### Backups — your history is safe

Every night FlowSphera backs up the flow data and every setting on its own: a full backup once a week, only the changes
on the other days. Copies go to a folder on the server and, if you like, to S3-compatible storage, SFTP or FTP —
encrypted with your passphrase (AES-256-GCM). One click checks that a backup is whole; another restores it — on the
same server or on a brand-new one after a disk failure.

A power cut does not take the database down either: after an unclean stop FlowSphera opens it by itself, sums the
long-period totals again from the records and tells you in Events and on your notification channels what happened —
when the server stopped, what is missing, what was summed again.

<p align="center"><img src="docs/media/en/backups.webp" alt="Settings → Backups: a week of verified, encrypted backups kept here and on S3" width="100%"></p>

### Data retention — as much history as your disk holds

Keep flow details as long as your license allows — or fewer days on a small disk. Settings → General shows what the
data takes now, about a day, and what it will take with your choice before you save it. Fewer days free the space at
once and are confirmed with your password; the license only sets the most you can choose.

<p align="center"><img src="docs/media/en/retention.webp" alt="Settings → General → Data retention: kept now 30 days, on disk now, about a day, and the estimate with 14 days chosen" width="100%"></p>

### Devices and names — move, copy, import

When a firewall starts exporting from another address, **Change address…** moves everything set for it — interface
names, roles, capacities, SNMP — and keeps the old address as its alias, so its history continues as one device on every
page. Devices go to another server as a JSON file (checked device by device, all or nothing, no SNMP secrets), and a
source that sends but is not described can be **ignored**. Port, host and network names come and go as **CSV** — straight
from Excel in any language — with a preview of what is new, changed or unreadable before anything is saved.

**City and country are enough.** Type the city and the device is on the connection map and the globe: FlowSphera
offers the places of that country as you type (about 150,000, from the GeoIP data it already has — offline, no online
service asked), and latitude and longitude stay for when you want it exact. A MikroTik's VPN and PPPoE sessions — a new
interface each time — are kept by name and folded into one line, so the lists of interfaces stay clean.

<table>
<tr>
<td width="50%" valign="top"><img src="docs/media/en/device-place-offer.webp" alt="The device dialog: «Bru» typed with the country BE — Brussels, Bruges and more offered with their region and coordinates"></td>
<td width="50%" valign="top"><img src="docs/media/en/device-place.webp" alt="The device dialog: City Brussels, Country BE — «On the map at Brussels, Brussels Capital (50.85, 4.36) — from City + Country»"></td>
</tr>
</table>

<table>
<tr>
<td width="50%" valign="top"><img src="docs/media/en/device-move.webp" alt="Settings → Devices → Edit: a new address for a device — everything set for it moves there, the records from the old one stay this device's"></td>
<td width="50%" valign="top"><img src="docs/media/en/names-csv.webp" alt="Settings → Flow configuration: a CSV import previewed — new, changed and unreadable rows with their line numbers"></td>
</tr>
</table>

### Fast on a busy network, over days

A day of a busy network is hundreds of millions of flow records. FlowSphera keeps summary tables — per 5 minutes and
per hour, filled as the records arrive — and every page over a day or more reads those instead of the records. The
numbers stay the same: before each release every summary table is checked row by row against the records.

<p align="center"><img src="docs/media/en/perf-day.svg" alt="A day on screen with 216 million records in it: Overview 35 s → 3 s, Flows 31 s → 3 s, the host page 32 s → 8 s, Through device 21 s → 5 s, QoS 11 s → 0.6 s — FlowSphera 1.16.2 against 1.17.0" width="100%"></p>

Measured in FlowSphera's own test lab: a synthetic network sending 5,000 records/s (the most Community stores) for 12
hours — 216 million records — on 6 virtual cores of a laptop-class CPU, nothing cached. All the figures: [docs/performance.md](docs/performance.md).

## Works with your equipment

Ready configuration — with a **Copy** button — for each vendor and export protocol, right in *Settings → Devices*:

<p align="center"><img src="docs/media/en/connect-device.webp" alt="Connect a device: ready configuration with a Copy button" width="100%"></p>

**Fortinet** · **Cisco** · **MikroTik** · **Juniper** · **Palo Alto** · **Check Point** · **SonicWall** · **Huawei** ·
**Arista** · **HPE Aruba** · **VyOS / EdgeOS** · **pfSense / OPNsense** · **Linux** (pmacct, softflowd, hsflowd) · and
any other NetFlow v5 / v9, IPFIX or sFlow v5 exporter, over IPv4 or IPv6. Optional SNMP v2c / v3 names the interfaces.

## Install in one command

```bash
curl -fsSL https://raw.githubusercontent.com/telesphera/flowsphera/main/install.sh | sudo bash
```

The installer (English or Ukrainian) sets up everything, asks a few questions with sensible defaults and finishes with
the address of your FlowSphera and the configuration for your exporter. Later: `sudo flowsphera upgrade` — settings,
users and data stay.

- **Runs on** Debian / Ubuntu and Fedora / RHEL / Rocky / Alma, x86_64 or arm64.
- **Disk**: about 25 MB per million flow records; a small office needs a few hundred MB for 30 days.
- **Speed**: one decoding worker handles about 40,000 records/s, four about 100,000 — on a 4-core laptop-class CPU.
  A day on screen with 216 million records in it opens in 1–8 s ([performance](docs/performance.md)).

Unattended install, upgrades, all server commands: [docs/install.md](docs/install.md).

## Editions

| | **Community** — free | **Pro** — license for one server |
|---|---|---|
| Every feature, now and in future versions | ✓ | ✓ |
| Flow records per second | up to **5,000** | no limit (or per license) |
| Data kept (flows and every total built from them) | **30 days**, or fewer of your choice | per license, e.g. 90 days, or fewer of your choice |
| Activation | — | a license key, activated in a minute in Settings → License |

5,000 records/s covers homes, small and medium offices; a busy 1 Gbit/s internet edge typically exports a few thousand.
**For a Pro license, a demo or help with deployment: [flowsphera@telesphera.net](mailto:flowsphera@telesphera.net?subject=FlowSphera%20Pro).**
Details: [docs/editions.md](docs/editions.md).

## Documentation

| | |
|---|---|
| [Install and upgrade](docs/install.md) | one-line, unattended, upgrade, server commands, requirements |
| [Exporter configuration](docs/exporters.md) | FortiGate, Cisco, MikroTik, Juniper, Linux and more |
| [Features in detail](docs/features.md) | everything FlowSphera collects, computes and shows |
| [Backups and restore](docs/backups.md) | schedule, S3 / SFTP / FTP copies, encryption, restore on a new server |
| [Configuration](docs/configuration.md) | `/etc/flowsphera/env` |
| [Security](docs/security.md) | passwords, sessions, HTTPS, what runs where |
| [API](docs/api.md) | JSON endpoints, filters, API tokens, webhooks, SIEM / syslog |
| [Performance](docs/performance.md) | measured receiving and page speeds |
| [Editions and licensing](docs/editions.md) | limits, activating a license key, moving it to another server |
| [Translations](docs/translations.md) | adding a language: one file |
| [Repository layout and roadmap](docs/development.md) | for contributors |

## License

[Elastic License 2.0](LICENSE): free to use, run and modify, including in companies; not allowed: offering FlowSphera as
a hosted service or circumventing the license checks. The FlowSphera core (`ftcore`) ships compiled under the FlowSphera
End User License Agreement. Versions up to 1.1.0 were published under MIT and stay so. IP geolocation by
[DB-IP](https://db-ip.com), licensed under CC BY 4.0. Fonts Manrope and JetBrains Mono ship with FlowSphera under the
[SIL Open Font License 1.1](web/fonts/). PDF reports are made with [ReportLab](https://www.reportlab.com) (BSD).
Screenshots show demo data, no real network.
