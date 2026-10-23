## 1. Provisioning dependencies (GATE — do not start §3–§5 until green)

- [x] 1.1 Add logical packages to `dotfiles/provisioning/packages.yaml`:
  `astal-bluetooth`, `astal-wp` (Astal bindings), `bluez`, `bluez-utils`
- [x] 1.2 Resolve exact AUR names in `src/provisioning/ansible/roles/packages/vars/arch.yml`
  `aur_packages` (confirm the real names on the machine — Astal ships as both
  `astal-*` and `libastal-*-git`; mirror `libastal-notifd-git` if needed)
- [x] 1.3 Add Debian-family name mappings in
  `src/provisioning/ansible/group_vars/debian-family.yml` (`bluez`, `bluez-utils`)
- [x] 1.4 Ensure `bluetooth.service` is enabled + started by provisioning
  (packages role task, or the role that owns system services)
- [x] 1.5 Ensure the user can set brightness: `brightnessctl set` succeeds
  (udev rule from the package; add user to `video` group if the ACL does not apply)
- [x] 1.6 Extend `verify` to assert the Astal Bluetooth/Wp GIR namespaces resolve
  and `bluetooth.service` is enabled (fail the gate otherwise)
- [x] 1.7 Gate proven green: both AUR bindings installed via `yay`, `bluetooth.service`
  enabled+active, typelibs (`AstalBluetooth-0.1`, `AstalWp-0.1`) resolve, packages +
  verify playbooks `--check` clean, provisioning unit tests pass (137). Full
  `make bootstrap` not run (narrow gate proven instead).

## 2. Icon templates and mappings

- [x] 2.1 Copy templates into `dotfiles/assets/icon-templates/`:
  - `status-bar/settings/default/icon.svg` (from `status-bar-settings.svg`)
  - `settings-panel/wifi/default/icon.svg`, `settings-panel/bluetooth/default/icon.svg`,
    `settings-panel/hyprmod/default/icon.svg`
  - `brightness/default/icon.svg`
  - `volume/muted|lowest|low|medium|max/default/icon.svg`
  - Hyprmod glyph resolved: owner re-exported a single square glyph
    (`viewBox 0 0 1024 1024`); template swapped in and re-rendered palette-correct
- [x] 2.2 Replace literal `fill="black"` with `{{COLOR_FOREGROUND}}` in all new
  templates; preserve the `opacity="0.5"` wave wrappers in the volume set so the
  level distinction survives
- [x] 2.3 Verify each SVG has a valid `viewBox` and no remaining literal fills
- [x] 2.4 Register groups/variants in
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`:
  - `settings` (variant `default` → `status-bar-settings.svg`, plus
    `bar_mappings: {widget: settings, states: {default: status-bar-settings}}`)
  - `settings-panel` (variants `wifi`, `bluetooth`, `hyprmod`)
  - `brightness` (variant `default` → `brightness.svg`)
  - `volume` (variants `muted`, `lowest`, `low`, `medium`, `max`)
- [x] 2.5 Add `settings` to the runtime contrast-guard allowlist
  (`src/runtime/src/runtime/domain/icon_contrast.py` `BAR_GROUPS`); leave
  `settings-panel` / `volume` / `brightness` out (they render over the opaque panel)
- [x] 2.6 Validate: `itr list` for each group, then a temp `itr render`; assert
  rendered fills are palette colors (not black)
- [x] 2.7 Confirm `icons.json` regenerates with the new groups during provisioning

## 3. Panel foundation

- [x] 3.1 Create `dotfiles/config/ags/settings-panel/state.ts` — `panelVisible`,
  `activeView` state + `open/close/toggle/show/back`
- [x] 3.2 Create `dotfiles/config/ags/settings-panel/primitives.tsx` —
  `PanelCard`, `CapabilityTile`, `IconToggle`, `LevelSlider`, `NavHeader`
- [x] 3.3 Create `dotfiles/config/ags/settings-panel/SettingsPanel.tsx` — the
  window (TOP|RIGHT, `exclusive=false`, `layer=OVERLAY`, keymode), plus the
  click-outside catcher window and `Esc` handler
- [x] 3.4 Wire `dotfiles/config/ags/app.tsx` to create the panel once on the
  primary monitor (`app.get_monitors()[0]`)
- [x] 3.5 Create `dotfiles/config/ags/bar/widgets/settings.tsx` — bar icon
  (`registry.resolve("settings","default")`) toggling the panel
- [x] 3.6 Add the settings widget to `bar/Bar.tsx` end section (rightmost)

## 4. Controls

- [x] 4.1 `controls/wifi.tsx` — AstalNetwork reactive reads; `wifi.enabled`
  toggle; AP list (dedupe, sort, secured/open, strength, connected badge);
  connect via `nmcli` (array-form `execAsync`); open/known vs password path
- [x] 4.2 Wi-Fi password view — solid `@color01` field, Cancel (outline), Join
  (`@color06` fill, foreground text); async failure keeps the field + short message
- [x] 4.3 `controls/bluetooth.tsx` — AstalBluetooth reactive reads;
  `adapter.powered` toggle; device list with Connect/Disconnect/Pair via device
  methods
- [x] 4.4 `controls/brightness.tsx` — read/write via `brightnessctl`
  (`-m`, `set <pct>%`), optimistic value + interval refresh while panel visible
  (clear on hide)
- [x] 4.5 `controls/volume.tsx` — AstalWp `default_speaker` `volume`/`mute`;
  slider writes volume; speaker glyph toggles mute
- [x] 4.6 Level-aware speaker glyph via `registry.resolve("volume", variant)`
  with thresholds muted 0 / lowest 1–25 / low 26–50 / medium 51–75 / max 76–100;
  initial assignment inside `createEffect`
- [x] 4.7 `controls/hyprmod.tsx` — action tile, `execAsync(["hyprmod"])`

## 5. Views, extensibility, styles

- [x] 5.1 `views/MainView.tsx` — Wi-Fi tile, Bluetooth tile, Hyprmod tile,
  Display card, Sound card; driven by an extensible `SECTION_ORDER` array
- [x] 5.2 `views/WifiView.tsx` — `NavHeader` (back + Wi-Fi icon-toggle) + list
  or password view
- [x] 5.3 `views/BluetoothView.tsx` — `NavHeader` (back + Bluetooth icon-toggle)
  + device list
- [x] 5.4 Add panel styles to `dotfiles/config/ags/style.css` — panel/card/icon
  toggle/slider/field/selected-row tokens per design §5 (colors.css only, no
  literals; GTK-safe properties)
- [x] 5.5 Confirm extensibility: document in code how a new section appends
  (`SECTION_ORDER` + a control + a card type)

## 6. Deployment and verify

- [x] 6.1 Add config dirs to `compositor_configs/vars/main.yml`
  (`ags/settings-panel`, `.../controls`, `.../views`)
- [x] 6.2 Add one `compositor_configs_skeleton_files` entry per new AGS source
  file (panel, state, primitives, controls ×5, views ×3, `bar/widgets/settings.tsx`)
- [x] 6.3 Add the new files to `verify/vars/main.yml` required-files list
- [x] 6.4 Add new icon samples to verify (`settings-panel-wifi.svg`,
  `volume-low.svg`)
- [x] 6.5 Confirm no autostart/always-on-instance change (instance list stays `[ags]`)

## 7. Validation

- [x] 7.1 `ags bundle dotfiles/config/ags/app.tsx /tmp/ags-check.bundle.js --root .`
  succeeds
- [x] 7.2 `itr list` / temp `itr render` green for all four icon groups
- [x] 7.3 `make bootstrap` converges; verify role reports the new files, samples,
  bindings, and enabled `bluetooth.service`
- [ ] 7.4 Owner manual matrix (panel loaded; bar button confirmed live):
  panel toggle; icon-toggles vs row-opens-list; back arrow; Wi-Fi connect +
  password; BT connect/disconnect; brightness + volume sliders; speaker glyph
  changes across all 5 levels; hyprmod launches; `Esc` + click-outside dismiss;
  panel absent on the secondary monitor
- [x] 7.5 Confirm no runtime setup/install path exists (grep the diff for
  `pacman`/`apt`/`install`/download in AGS sources)

## 8. Owner-review refinement (icons)

- [x] 8.1 Remove the rounded container behind the Wi-Fi/Bluetooth/Hyprmod glyphs
- [x] 8.2 Add pipeline-tinted state variants: `settings-panel` `wifi`/`bluetooth`
  → `color13` (accent), new `wifi-off`/`bluetooth-off` → `foreground` (neutral)
  and dimmed via opacity in the panel (hue alone failed: palette tokens can be
  near-identical);
  regenerate `icons.json`
- [x] 8.3 Swap the glyph on enable/disable in `IconToggle`/`CapabilityTile`
  (on/off paths + `createEffect`), no CSS filter
- [x] 8.4 Increase glyph sizes: capability 28px, subview header 22px, Hyprmod 28px
- [x] 8.5 Converge provisioning + regenerate the runtime icon cache; verify
  `current/icons/` contains `settings-panel-wifi-off.svg` / `-bluetooth-off.svg`
  with the accent/muted fills
- [x] 8.6 Fix panel launch offset: `exclusivity=NORMAL` made Hyprland place the
  overlay below the bar's 48px exclusive zone *and then* apply `marginTop`
  (measured top = 104 = 56 + 48). Set `IGNORE` (no exclusive-zone request, like
  the catcher) and `marginTop=52` so the panel sits ~4px under the bar
- [x] 8.7 Bluetooth: the radio can be rfkill SOFT-blocked (vendor WMI killswitch
  / persisted `systemd-rfkill` state), so BlueZ refuses to power it and the
  `powered` setter fails silently — the toggle looked dead. Fix at both layers:
  the packages role clears a soft block at provision time (`rfkill unblock
  bluetooth`) and verify pins the unblocked state; the panel's toggle also
  clears a soft block before enabling, for a later user-triggered block.
  Proven by soft-blocking the radio, re-running the packages role, and
  confirming it powers on
- [x] 8.8 Discovery: Bluetooth had no discovery (BlueZ only lists known devices), so the list was always empty; start/stop `adapter.start_discovery()` while the BT view is open (with a "Scanning…" state) and force `wifi.scan()` when the Wi-Fi list opens
- [x] 8.9 Pairing: no `org.bluez.Agent1` existed on the bus, so `Device.pair()` failed (device flipped to Connected then reverted). Added `settings-panel/bluetooth-agent.ts` — a headless NoInputNoOutput agent registered as default at AGS startup (verified via dbus-monitor) — and the Pair action now trusts + auto-connects once `paired` flips
- [x] 8.10 Audio routing: a connected headset stayed "Connected" but audio kept playing on speakers because it was not the default PipeWire sink (and WirePlumber's bluez monitor had failed to init while the radio was rfkill-blocked). On connect the panel now polls for the device's sink, sets it default, and moves active streams
- [x] 8.11 Bluetooth row actions: added an Unpair action for paired devices and an in-flight Gtk.Spinner (connect/pair/disconnect) that replaces the action button, so a press is visibly acknowledged
- [x] 8.12 Provisioning gap closed: `pipewire-audio` (Arch; `libspa-0.2-bluetooth` on Debian) — the package that ships the bluez5 SPA — was installed on the host but absent from the manifest, so a fresh machine would have no Bluetooth audio sink. Added to `packages.yaml` + both group_vars; `verify` now asserts the package, the unblocked radio, and a powered controller (tests updated, hermetic rfkill/bluetoothctl stubs)
- [x] 8.13 Out-of-range: paired-but-unseen devices (RSSI 0) are dimmed, labelled "Not in range", and Connect is disabled (Unpair stays). Verified via forced-open screenshot
- [x] 8.14 Toggle race fixed: the click-outside catcher closed on press, so the matching release fell through to the bar button and re-opened the panel (same-spot click appeared not to collapse). It now closes on release, consuming the whole gesture
- [x] 8.15 Panel anchored under the settings icon: the bar button reports the pointer x (motion controller; bar surface == monitor coords) and the panel sets `marginLeft = iconX - width/2` clamped to the monitor, anchor TOP|LEFT. Moving the icon mid-bar is followed
- [x] 8.16 Deterministic dismissal: full-screen hit-testable catcher (1%-opacity background — alpha-0 layer surfaces are not hittable) closes on release for outside clicks; the panel uses `keymode=NONE` so it does not steal keyboard focus and the bar button activates on the first same-spot click. Esc-to-close dropped in v1 (restorable via a global bind + AGS request handler). Verified with synthetic clicks: icon toggles 1/0/1/0, outside closes
- [x] 8.17 Wi-Fi connect: choosing a network set the password target but `<With>` did not render `WifiPasswordPrompt`, leaving the subview blank. Mount the prompt permanently and toggle visibility; rows use an explicit Connect button (whole-row `<button>` did not receive clicks); the saved-connection lookup has a timeout so a slow `nmcli` cannot leave the UI silent. Password prompt verified rendering (forced) and the Connect click opens it
- [x] 8.18 Wi-Fi list freshness + message polish: NetworkManager keeps vanished APs cached, so a switched-off hotspot lingered and could be clicked. Drop APs whose `last-seen` lags the newest by >25s (connected always kept; no-op if `last-seen` is unset), recomputed on a scan tick. List messages auto-clear after 6s and wrap (maxWidthChars) instead of overflowing. Rescan every 5s while the list is open
- [x] 8.19 Wi-Fi list source corrected: AstalNetwork's `access-points` objects never refresh on this stack (their `last-seen`/strength stay frozen), so the list was stale until AGS restarted and the `last-seen` filter was useless. The list is now read from `nmcli -t -f IN-USE,SSID,BSSID,SIGNAL,SECURITY device wifi list` (NetworkManager's live cache) and refreshed every 5s while the list is open, with a `nmcli device wifi rescan` trigger. Verified the panel matches nmcli's current SSID/signal/security output
- [x] 8.20 Wi-Fi list via NetworkManager D-Bus: Astal freezes access-point properties and nmcli's cache hides nothing, so the list is now read from NM D-Bus (Devices→Wireless→AccessPoint) and APs whose `LastSeen` lags the newest by >20s are dropped (NM's LastSeen does advance — verified 5173→5183→5196). RequestScan is issued each poll. Verified the panel reflects NM and drops stale APs; NM throttling means a vanished AP drops within ~1 scan cycle. Note: over-aggressive dropping was observed on first read before scans settled; networks reappear once seen
- [x] 8.21 Wi-Fi freshness via `iw`: provisioning installs `iw` and grants it CAP_NET_ADMIN+CAP_NET_RAW (`setcap`), with `verify` gating the package and the capability. The panel's list is now an authoritative `iw dev <iface> scan` (interface from NM D-Bus), polled every 8s while open, so a switched-off hotspot disappears instead of lingering in NM's cache. Removed the over-strict 'controller powered' verify gate (a user may toggle Bluetooth off; the not-soft-blocked gate covers the real fault) — **SUPERSEDED** by `refactor-ags-settings-panel-dbus` (workstream A3): `iw` and its CAP_NET_ADMIN/CAP_NET_RAW grant are removed end to end (packages.yaml, group_vars, packages role setcap, verify gate/vars, unit tests); the panel scans via NetworkManager D-Bus `RequestScan`.
- [x] 8.22 Wi-Fi switching between known networks: `nmcli device wifi connect` was unreliable when another network was active, and `nmcli connection up id <ssid>` does NOT scan (verified: fails with 'The Wi-Fi network could not be found' when NM's cache is cold). Match the saved profile by SSID (profile name may differ), issue `nmcli device wifi rescan` first, then `connection up id <profile>`; fall back to `device wifi connect`. Concurrency guard (one connect at a time, all Connect buttons disabled while pending) and a few post-connect list refreshes so the switch shows promptly — **SUPERSEDED** by `refactor-ags-settings-panel-dbus` (workstream A3): switching is handled by the NM D-Bus state machine (`DeactivateConnection` → wait `State == 30` → `ActivateConnection`/`AddAndActivateConnection`); no `nmcli`, no global connect lock.
- [x] 8.23 Wi-Fi connect hang guard: the saved-profile path ran `nmcli connection up` without a timeout, so a hung activation left `connectingSsid` set and every Connect button insensitive ("clicking does nothing"). Every nmcli step now has a hard timeout (helper `run`), plus a 40s watchdog and a reset when leaving the list. Verified from the shell that both `nmcli connection up id <profile>` (with a rescan first) and `nmcli device wifi connect <ssid>` switch in ~0.5s — **SUPERSEDED** by `refactor-ags-settings-panel-dbus` (workstream A3): no subprocess, no timeout helper, no 40s watchdog; NM `StateChanged` drives progress with one bounded self-cancelling UI fallback.
