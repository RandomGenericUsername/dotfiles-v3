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
