# Tasks: Wi-Fi real data + connected row

- [x] 1. Diagnose with `AGS_WIFI_DEBUG=1`: classify empty-list vs unmarked-connected per `design.md`; record the finding in this file.
- [x] 2. Implement the minimal `wifi-service.ts` fix for the proven cause.
- [x] 3. Re-run provision (`compositor-configs.yaml`) + restart AGS; confirm no toggle regression (switch settles, no oscillation).
- [ ] 4. Live check: connected row first with badge; saved rows follow; empty state only when truly empty.
- [ ] 5. Parity gate green; screenshot-vs-`state-1-connected` row-by-row sign-off.

## Finding (2026-09-26, machine connected to `Canela&Dulce`, NM device state 100)

- NOT empty-list at service level: `ap refresh: read=1..19 kept=1..13`
  (cold cache keeps only the active AP; a fresh scan repopulates; the
  transient-empty guard never blanked the list across bootstrap + scans).
- NOT unseeded state: `state=100` from the very first AP refresh, and
  `connected ssid -> Canela&Dulce` logged at bootstrap — the prime suspect
  (`lastDeviceState` never seeded) is disproven for the steady-state path.
- PROVEN-BY-READING gap fixed: `handleStateChanged` returned early when no
  UI attempt was in flight, so an *external* activation (autoconnect, roam,
  resume, another client) never re-resolved the active connection nor
  re-rendered — the connected row then depended solely on the
  `ActiveAccessPoint` property signal, which the code itself notes can be
  missed (stale AP path) → populated-but-unmarked. Fix: on `ACTIVATED` with
  nothing in flight, `refreshDeviceProps()` (no state-machine disturbance;
  in-flight completion path untouched). Plus two `AGS_WIFI_DEBUG`-only log
  lines in `refreshAccessPoints` (zero behavior change) for future diagnosis.

## Follow-up finding (2026-09-26, owner screenshot)

- The details table showed live MAC/IP/interface data while Known Networks had
  no connected row. Service data was reaching the view; the connected row was
  gated by a one-time JSX conditional that ran before the async network list
  arrived. Replace it with a keyed reactive `<For>` over connected networks.
- The Run action's CLI was also absent from PATH. The logical `speedtest`
  package had no distro mapping, so provisioning could not install it. Map it
  to `speedtest-cli` on Arch and Debian-family systems, parse its `--json`
  output as a fallback, and show a clear missing-command error.
- Live retest is still pending after package/config provisioning and AGS
  restart.

Verification: bar log `connected ssid -> <ssid>` present; popup matches
`state-1-connected` rows; `state-5-connecting` busy branch still triggers
during a manual connect.
