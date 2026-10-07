# Tasks — add-bluetooth-bar-popup

Legend: `[ ]` open · `[x]` done. Every section names its own verification, and
the tripwires are executable, not aspirational.

Sections 1–3 are **already landed** on this branch (icons + provisioning +
harness); they are marked done and kept as the record of what shipped and how it
was verified.

## 1. Icons — DONE (landed with the design branch)

- [x] 1.1 Convert the four circle-badge glyphs from `~/Downloads/Untitled/
  signal-{full,good,medium,low}-circle.svg` into
  `dotfiles/assets/icon-templates/settings-panel/bluetooth-signal-<v>/default/icon.svg`,
  rewriting `fill="#D9D9D9"` → `fill="{{COLOR_BACKGROUND}}"` and
  `fill="black"` → `fill="{{COLOR_FOREGROUND}}"`, preserving each step's
  `fill-opacity="0.5"` ladder byte-faithfully.
- [x] 1.2 `icons.yaml` — register `bluetooth-signal-{full,good,medium,low}`
  under the EXISTING `settings-panel:` group, mirroring the `wifi-signal-*`
  tint contract exactly (badge `color12` on the top step, `color13` below;
  bars `color0`).
- [x] 1.3 Convert the two bar glyphs from `~/Downloads/bluetooth-{on,off}.svg`
  into `status-bar/bluetooth/{on,off}/default/icon.svg`, rewriting
  `stroke="black"` → `stroke="{{COLOR_FOREGROUND}}"` (stroke-drawn, not
  fill-drawn).
- [x] 1.4 `icons.yaml` — new `bluetooth:` group with GROUP-LEVEL
  `color_mappings: {COLOR_FOREGROUND: color15}` and `bar_mappings`
  (`widget: bluetooth`, `icon_size: 24`). **No variant-level pins** — a
  variant pin would structurally exempt the glyph from the contrast guard,
  which is wrong for a glyph floating over the wallpaper.
- [x] 1.5 FORBIDDEN: state keys MUST NOT be bare `on:` / `off:` — YAML 1.1
  resolves those to booleans and every bar lookup then misses silently. Keys
  are `bluetooth-on` / `bluetooth-off`. Asserted by 1.7.
- [x] 1.6 Add `"bluetooth"` to `BAR_GROUPS` in
  `src/runtime/src/runtime/domain/icon_contrast.py`.
- [x] 1.7 Regenerate `dotfiles/config/ags/icons.json` (never hand-edit) and
  assert: every `bar_mappings.states` key is a `str`; the `bluetooth` group has
  no variant-level `color_mappings`; all 6 new variants present.
- [x] 1.8 Render all six through `itr render --icon settings-panel` and
  `--icon bluetooth` against the live palette; assert no unresolved
  `{{COLOR_*}}` token survives in any output.

## 2. Provisioning — DONE

- [x] 2.1 `blueman` into `dotfiles/provisioning/packages.yaml`, mapped in BOTH
  `group_vars/arch.yml` and `group_vars/debian-family.yml`. An unmapped logical
  entry is silently skipped by the packages role.
- [x] 2.2 Extend the two tests that pin the logical package set
  (`test_yaml_manifest_reader.py`, `test_ansible_scaffold.py`).
- [x] 2.3 Validate on the target machine: already installed (2.4.6-2),
  `bluetooth.service` active, `hci0` unblocked, controller
  `A0:E7:0B:8B:36:7E`. `blueman-manager` launched cleanly against the live
  adapter and was torn down; `bluetooth`, `pipewire`, `wireplumber` verified
  unaffected; session restored (no blueman processes before, none after).
- [x] 2.4 Add `blueman-{on,off}.svg` + `system-battery-100.svg` +
  `settings-panel-signal-good.svg` to `verify_icons_samples` so `verify` proves
  a REAL render happened rather than an empty dir.

## 3. Anti-drift harness — DONE

- [x] 3.1 Add stable `id="…"` anchors to every state cell in
  `mockups/panel.html` (13 states), matching `wifi-popup-mockup.html`'s
  convention. Captions alone are not machine-checkable.
- [x] 3.2 Copy the mock AND its `assets/` into the change so
  `mockups/panel.html` is self-contained and cannot drift against the BMAD
  folder.
- [x] 3.3 `scripts/bluetooth-mock-parity.py`: `ANCHORS`, `STATE_TSX`,
  `ALLOWLIST` (scaffolding + reason), `CLASS_MAP` (mock token → shipped
  class), `KNOWN_GAPS` (unimplemented, with the owning task).
- [x] 3.4 Negative test — inject an invented class into the mock and assert the
  gate exits 1 naming state + token. A gate that cannot fail is not a gate.
- [x] 3.5 Wire `bluetooth-mock-parity` into the `Makefile` and into `gates`.
- [x] 3.6 Assert the three pre-existing parity gates stay green
  (`wifi-mock-parity`, `speedtest-mock-parity`,
  `speedtest-no-new-architecture`).
- [x] 3.7 Runtime: update `test_icon_contrast.py::test_constants` for the new
  `BAR_GROUPS` member; `10 passed`.

## 4. Service accessors — OPEN

- [ ] 4.1 `bluetoothAdapterAddress: Accessor<string>` — set in
  `updateAdapterProps` from `Adapter1.Address`. The local controller address,
  not a device's. Feeds the `Adapter` row.
- [ ] 4.2 `bluetoothAudioTarget: Accessor<string | null>` — set by
  `routeAudioToDevice` to the endpoint it actually defaulted; `null` when the
  16 × 500ms window expires. Closes the silent failure where a device reads
  `Connected` while sound stays on the speakers.
- [ ] 4.3 `setBluetoothPowered(enabled: boolean)` — the mirror of
  `setWifiEnabled`. Replaces the blind `toggleBluetooth()` read-modify-write;
  two surfaces now mount a power control, so a stale read writes the wrong
  value.
- [ ] 4.4 Reference-count `startBluetoothDiscovery` / `stopBluetoothDiscovery`;
  issue `StopDiscovery` only at zero. The settings panel keeps all three views
  mounted, so a popup close racing a panel open is a real race.
- [ ] 4.5 Export all three accessors plus `setBluetoothPowered`.
- [ ] 4.6 Verify: `rg -n "setAdapterPowered|toggleBluetooth" services/bluetooth-service.ts`
  shows no remaining read-modify-write path; discovery counter unit-checkable by
  reading the exported accessor sequence.

## 5. Popup window + catcher — OPEN

- [ ] 5.1 `components/bluetooth/state.ts` — `bluetoothPopupVisible`,
  `bluetoothIconX`, `openBluetoothPopup` / `closeBluetoothPopup` /
  `toggleBluetoothPopup` / `setBluetoothIconX`. **Imports nothing from
  `settings-panel/**`** (the one-way dependency rule
  `components/wifi/state.ts` documents).
- [ ] 5.2 `components/bluetooth/BluetoothPopup.tsx` — `BluetoothPopup` +
  `BluetoothPopupCatcher`, mirroring `WifiPopup.tsx` property for property:
  `class="settings-panel"`, `anchor={TOP|LEFT}`, `exclusivity=IGNORE`,
  `layer=OVERLAY`, `marginTop={52}`, follower `marginLeft` clamped to
  `[8, monitorWidth - 320]`, `Keymode.NONE`, `widthRequest={312}`, pinned
  `settings-nav-header` as a SIBLING of the scrolledwindow, and
  `propagateNaturalWidth={false}` + `maxContentHeight={420}`.
- [ ] 5.3 Register the catcher BEFORE the popup in `app.tsx`.
- [ ] 5.4 Extend `app.tsx`'s `popup-close` request handler to call
  `closeBluetoothPopup()`.
- [ ] 5.5 `settings-panel/state.ts` `open()` calls `closeBluetoothPopup()` via
  `import { closeBluetoothPopup } from "../components/bluetooth/state"` —
  **note the single `../`**: from `dotfiles/config/ags/settings-panel/`,
  `../../components/...` would resolve to `dotfiles/config/components`, which
  does not exist. The bar widget calls `close()` then `toggleBluetoothPopup()`
  (the `bar/widgets/network.tsx` order).
- [ ] 5.6 Esc handler on an `EventControllerKey` mirroring `WifiPopup` —
  currently unreachable, live the instant a PIN field exists.
- [ ] 5.7 FORBIDDEN: `exclusivity` MUST NOT be `NORMAL` (Hyprland offsets the
  overlay below the bar's reserved zone, then applies `marginTop`, pushing the
  popup ~48px too low); `keymode` MUST NOT be unconditionally `ON_DEMAND`
  (grabs the keyboard, the bar swallows the first click, same-spot collapse
  stops working); no new window may own keyboard focus.
- [ ] 5.8 Verify: `make bluetooth-mock-parity` reports `popup-off`,
  `popup-no-adapter` green.

## 6. Reworked body — OPEN

- [ ] 6.1 Lead every row with
  `settings-panel/bluetooth-signal-{full,good,medium,low}` at **30px**
  (`.settings-net-signal`'s real size; `WifiContent` uses `pixel_size={30}`),
  threshold `≥−60 full, ≥−70 good, ≥−80 medium, else low`. No glyph when
  `rssi >= 0`. Tooltip carries the exact reading.
- [ ] 6.2 Replace the `−N dBm` meta line with a word: `Not in range` /
  `Paired` / `Ready to pair`.
- [ ] 6.3 Row `act()` becomes the whole-row `Gtk.GestureClick` target with the
  action button claiming its own click first; no-op while busy or out of
  range.
- [ ] 6.4 Busy branch: spinner + `<Action>ing…`, other rows' primary actions
  insensitive via `anyBusy()`, `Unpair` hidden. Add the static
  `Can take up to 30 s` line — **no countdown** (a timer in the view is
  forbidden).
- [ ] 6.5 `Available Devices` chevron section, collapsed when empty
  (`manuallyToggled || nearbyCount > 0`).
- [ ] 6.6 Settings tile subtitle states (`Off` / `Not connected` /
  `<alias>` / `<alias> · <battery>%`).
- [ ] 6.7 Inline unpair confirm: meta stack → `Remove from paired devices`,
  actions → `Keep` / `Unpair device`, **no reflow**; one confirm at a time;
  click-outside/Esc dismisses the confirm before the surface. Adds the ONE new
  class `.settings-rowact.danger` to `style.css`.
- [ ] 6.8 `Bluetooth Settings ›` footer row launching `blueman-manager`
  (NOT `bluetoothctl`), with the wrap-not-ellipsize note rule from
  `WifiContent`'s `nm-connection-editor` row.
- [ ] 6.9 Adapter detail row from `bluetoothAdapterAddress`, hidden while
  powered off. **No audio-output row** (owner ruling: PipeWire state inside a
  Bluetooth surface mixes concerns).
- [ ] 6.10 FORBIDDEN: no new CSS class other than `.settings-rowact.danger` and
  `.settings-net.confirming` (the spec was amended from one to two — see the
  requirement's amendment note);
  no `dBm` string in any row label; no timer/interval in the view; no bus call
  or subprocess in the view; no bare `battery-*` variant from the panel.
- [ ] 6.11 Verify: `make bluetooth-mock-parity` — `KNOWN_GAPS` must reach
  **0**, meaning both 6.7 entries cleared.

## 7. Header parity + bar indicator — OPEN

- [ ] 7.1 `BluetoothView`'s header switches from the bare `BluetoothToggle` to
  `WifiSwitch`, pinned above the scroll area like `WifiPopup`'s.
- [ ] 7.2 `controls/bluetooth.tsx` keeps `IconToggle` on the tile and forwards
  `setBluetoothPowered(v)` explicitly.
- [ ] 7.3 `bar/widgets/bluetooth.tsx` — reads `bluetoothPowered` directly,
  resolves `registry.getBarMappings("bluetooth").states[stateKey]` →
  `registry.resolve("bluetooth", variant)` (the `network.tsx` path). Primary
  click records the pointer x via an `EventControllerMotion` (which does not
  claim clicks) then toggles the popup.
- [ ] 7.4 Register in `bar/Bar.tsx`'s `end` box immediately left of
  `NetworkStatus`.
- [ ] 7.5 FORBIDDEN: no right-click or scroll action on the bar glyph (there is
  no continuous value to nudge); no hub subscription; no `IconToggle` in a
  header slot.
- [ ] 7.6 Verify: `make bluetooth-mock-parity` reports `bar-anchor`, `bar-on`,
  `bar-off`, `panel-subview`, `panel-tile` green.

## 8. Tray hygiene — OPEN

- [ ] 8.1 `isBluetoothItem()` in `lib/status-notifier.ts`, excluding any
  Bluetooth StatusNotifier item from `bar/widgets/tray.tsx` alongside the
  existing `isNetworkItem` filter.
- [ ] 8.2 User-level autostart override disabling `blueman-applet` so the tray
  item is never created. Must survive package upgrades — do NOT edit
  `/etc/xdg/autostart/blueman.desktop`.
- [ ] 8.3 Verify: exactly one Bluetooth affordance in the bar after login; no
  `blueman-applet` tray item.

## 9. Gates + deploy — OPEN

- [ ] 9.1 `make gates` green: `contracts-check`, `wifi-mock-parity`,
  `speedtest-mock-parity`, `speedtest-no-new-architecture`,
  `bluetooth-mock-parity`, `capture-test`, `capture-hexagonal-gate`.
- [ ] 9.2 `make contracts-check` proves the hub contract is untouched (no new
  topic, payload or enum in either contract file).
- [ ] 9.3 Deploy: `assets.yaml` → `compositor-configs.yaml` playbooks (icons +
  AGS sources), then `dotfiles-runtime icons regenerate` to re-derive from the
  live palette and restart AGS so the new components re-bundle. Gate on
  `dotfiles-provision verify`. Full `make bootstrap` is the final accept gate.
- [ ] 9.4 Owner visual sign-off against `mockups/panel.html` at ×1 and ×2.

## 10. Known pre-existing debt — NOT this change

- [ ] 10.1 `test_packages_manifest_has_verified_set` and the two group_vars
  coverage tests fail on `master`, over `astal-*`, `astal-battery`,
  `astal-hyprland`, `astal-network`, `grim`, `hyprcursor`, `hypridle`,
  `hyprlock`, `hyprpolkitagent`, `lf`, `slurp`, `tidal-hifi`, `wl-clipboard`,
  `xdg-desktop-portal-*`, `xdg-utils`. Verified failing before this change
  started (`git stash` + re-run). Separate change; not fixed here so this diff
  stays scoped.
