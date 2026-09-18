# Design: add-ags-settings-panel

Reference UI (approved): `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-2026-09-18/.working/key-screens-native.html`
(direction B — "Family Native"). Visual rules: `_bmad-output/planning-artifacts/gui-unification-ux-spec.md`.

## 0. Runtime shape — one instance, one extra window

The panel is a **second window in the existing always-on bar AGS instance**
(`dotfiles/config/ags/`), not a new `ags run -d` process. Rationale: the trigger
is a bar widget, the two share `colors.css` and the icon registry, and the bar is
already the always-on instance `verify` checks — so no autostart change, no new
reloader case, no second manifest.

- `app.tsx` creates the bar per monitor as today, then creates **one**
  `SettingsPanel` bound to the primary monitor (`app.get_monitors()[0]`).
- `settings-panel/state.ts` owns visibility and active view as AGS state:
  `panelVisible: Accessor<boolean>`, `activeView: Accessor<"main"|"wifi"|"bluetooth">`,
  and `open()/close()/toggle()/show(view)/back()`. The bar button and the panel
  are the only writers.

## 1. Window and dismissal

- `Astal.Window`: `name="settings-panel"`, `class="settings-panel"`,
  `gdkmonitor={primaryMonitor}`, `anchor={TOP | RIGHT}`, `exclusive={false}`,
  `layer={Astal.Layer.OVERLAY}`, `keymode={Astal.Keymode.ON_DEMAND}`,
  `visible={panelVisible}`.
- Placement: top margin = bar height + gutter (bar is ~48px; use a CSS margin so
  the panel sits just under the settings icon), right margin = gutter. The panel
  overlays the wallpaper; it is not reserved space.
- Dismissal:
  - `Esc` — `keymode ON_DEMAND` + a `Gtk.EventControllerKey` on the panel calling
    `close()`.
  - Click-outside — a sibling full-screen transparent `Astal.Window` (anchor all
    edges, `layer=OVERLAY`, `exclusive=false`, `keymode=NONE`) shown only while
    the panel is visible, with a primary-click gesture calling `close()`. The
    panel is created after the catcher so it stacks above it.
- `show(view)` resets scroll and sets `activeView`; `back()` returns to `main`.

## 2. Component tree and section extensibility

`settings-panel/primitives.tsx` exposes the reusable building blocks so future
sections are additions, not surgery:

- `PanelCard` — a titled section card (Display, Sound; future cards).
- `CapabilityTile` — a row with `icon` (the toggle), title, sublabel, chevron;
  `onToggle` wired to the icon only, `onOpen` wired to the row/chevron.
- `IconToggle` — the icon circle; `.on`/`.off` visual state; `onClicked` toggles.
- `LevelSlider` — leading glyph + track; value binding, `onChange`, optional
  step; `--p` drives fill and thumb position.
- `NavHeader` — back button + title + optional trailing control.

`MainView` composes a `SECTION_ORDER` array of section descriptors
(`{ id, render }`) so a new section is appended to the array. Order is stable and
extensible; no layout assumptions beyond the card stack.

## 3. Capability wiring

### 3.1 Wi-Fi (`controls/wifi.tsx`)

- **Reactive reads** via `gi://AstalNetwork` (`Network.get_default()`):
  `wifi.enabled`, `wifi.ssid`, `wifi.strength`, `wifi.state`,
  `wifi.access_points`. Bind with `createBinding(...)` (+ `notify::` for nested
  props), per the existing bar `network.tsx` pattern.
- **Toggle**: set `wifi.enabled` (writable GObject property).
- **List**: `wifi.access_points` deduped by SSID, sorted connected-first then by
  `strength`; each row shows SSID, secured/open, strength bars, and a Connected
  badge. Empty/radio-off state renders the family empty message.
- **Connect**: AstalNetwork is read-only for connection activation, so writes go
  through **NetworkManager's CLI** (`nmcli`, provisioned with `networkmanager`):
  - open/known network → `nmcli device wifi connect "<ssid>"`;
  - secured, no saved secret → inline password view → the same command with
    `password "<pw>"`.
  - Invoke with `execAsync` (array form, no shell interpolation of the SSID/PW).
- **Password view**: `surface-search` treatment — solid `@color01` field, label,
  dots + caret; `Cancel` (outline) and `Join` (`@color06` fill, foreground text).
  Join is async; on failure keep the field and surface a short inline message
  (never a raw NM traceback).

### 3.2 Bluetooth (`controls/bluetooth.tsx`)

- **Reactive reads** via `gi://AstalBluetooth` (`Bluetooth.get_default()`):
  `adapter.powered` (or `enabled`), `adapter`, `devices`, per-device name /
  connected / paired / battery percent.
- **Toggle**: set `adapter.powered` (writable). Header toggle in the subview uses
  the same icon-toggle primitive.
- **Device list**: connected first, then paired, then available; each row offers
  Connect / Disconnect (and Pair for unpaired) by calling the AstalBluetooth
  device methods. Requires `bluez` running — ensured by provisioning (`bluetooth.service`).

### 3.3 Display brightness (`controls/brightness.tsx`)

- Backend: **`brightnessctl`** (already in `packages.yaml`). No Astal brightness
  binding is assumed; the implementing agent confirms whether an installed GIR
  namespace provides reactive brightness, and if not uses the CLI path below.
- Read: `brightnessctl -m` (machine-readable current/max) → percent. Write:
  `brightnessctl set <pct>%` via `execAsync`.
- Reactivity: optimistic value on drag/change, plus an `interval` refresh while
  the panel is visible (clear on hide) so Fn-key changes reflect. The interval is
  a panel-scoped concern only; bar widgets keep the no-polling rule.
- Provisioning must ensure the user can set brightness (udev rule shipped by the
  package; add the user to the `video` group if required) — see capability
  `settings-panel-provisioning`.

### 3.4 Sound volume (`controls/volume.tsx`)

- Reactive reads via `gi://AstalWp` (`Wp.get_default().default_speaker`):
  `volume` (0.0–1.5), `mute`.
- Slider writes `volume`; clicking the leading speaker glyph toggles `mute`.
- **Level-aware glyph** — thresholds over the effective volume
  (`mute ? 0 : volume`):
  | Level | Range | Icon variant |
  |---|---|---|
  | muted | 0 | `volume/muted` |
  | lowest | 1–25% | `volume/lowest` |
  | low | 26–50% | `volume/low` |
  | medium | 51–75% | `volume/medium` |
  | max | 76–100% | `volume/max` |

  Resolved through the shared `IconRegistry` (`registry.resolve("volume", variant)`);
  the initial assignment happens inside a `createEffect` so the first render is
  correct (the recorder pause/play lesson).

### 3.5 Hyprmod (`controls/hyprmod.tsx`)

- Action tile (no state): `execAsync(["hyprmod"])`. `hyprmod` is already
  provisioned. The tile closes the panel before/after launch (agent's choice;
  closing keeps focus behavior predictable).

## 4. Bar integration

- `bar/widgets/settings.tsx`: a button styled like the other bar widgets,
  `registry.resolve("settings", "default")` icon at bar `pixel_size`, `onClicked`
  → `toggle()`. Added to `bar/Bar.tsx` end section (rightmost, matching the
  approved mock's status-bar strip).
- The `settings` group carries `bar_mappings` (`widget: settings`,
  `states: { default: status-bar-settings }`) for consistency with the other bar
  groups.

## 5. Styling (`style.css`)

Direction B tokens, exclusively from `colors.css` (`@color_00..15`,
`@background`, `@color_foreground`) — no literal colors:

- Panel: `background: alpha(@color_00, .94)`, `border: 1.5px solid @color_04`,
  `border-radius: 12px`.
- Cards: `alpha(@color_01, .18)` fill + `1px alpha(@color_foreground, .10)`.
- Icon toggle on: `@color_13` fill, `@color_00` glyph; off: neutral translucent
  with dimmed foreground glyph.
- Selected row: `@color_10` fill with **foreground** text (on this palette
  background-on-`@color10` is 2.67:1; foreground is 4.10:1 — the family rule
  resolves to foreground).
- Slider: 10px track `alpha(@color_foreground, .16)`, fill `@color_13`, thumb
  `@color_15`.
- Field: solid `@color_01` (fields are surfaces, not holes).
- GTK-safe properties only (no `max-width`/`max-height`; explicit
  `background-image: none` where a theme pill must be cleared).

## 6. Icons pipeline

Templates under `dotfiles/assets/icon-templates/` (deployed by the `assets` role
via directory synchronize — no new asset category):

```
status-bar/settings/default/icon.svg          → output status-bar-settings.svg
settings-panel/wifi/default/icon.svg          → output settings-panel-wifi.svg
settings-panel/bluetooth/default/icon.svg     → output settings-panel-bluetooth.svg
settings-panel/hyprmod/default/icon.svg       → output settings-panel-hyprmod.svg
brightness/default/icon.svg                   → output brightness.svg
volume/muted/default/icon.svg                 → output volume-muted.svg
volume/lowest/default/icon.svg                → output volume-lowest.svg
volume/low/default/icon.svg                   → output volume-low.svg
volume/medium/default/icon.svg                → output volume-medium.svg
volume/max/default/icon.svg                   → output volume-max.svg
```

- Replace every literal `fill="black"` with `{{COLOR_FOREGROUND}}` (the volume
  wave layers that were `opacity=0.5` keep their opacity wrappers so the level
  distinction survives).
- Register groups/variants in
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (single source
  of truth; `icons.json` is generated output and must not be hand-edited).
- Add `settings` to the runtime contrast-guard allowlist (`src/runtime`,
  `domain/icon_contrast.py:BAR_GROUPS`) so the bar icon retargets on light
  wallpapers; `settings-panel`, `volume`, and `brightness` stay out (they render
  over the opaque panel). Brightness is deliberately its own group rather than a
  variant under the allowlisted `ui` group, so a bar contrast flip can never
  darken the panel's brightness glyph.
- Validate with `itr list` and a temporary `itr render` before bootstrap.

## 7. Provisioning wiring (gate)

1. **Packages** (`dotfiles/provisioning/packages.yaml` + per-manager maps):
   - add logical `astal-bluetooth`, `astal-wp`, `bluez`, `bluez-utils`;
   - resolve AUR names in `roles/packages/vars/arch.yml` `aur_packages` (exact
     names confirmed at implementation time — the Astal packaging naming varies
     between `astal-*` and `libastal-*-git`, as `libastal-notifd-git` shows);
   - Debian-family equivalents in `group_vars/debian-family.yml` (bluez).
2. **Service**: ensure `bluetooth.service` is enabled and started by provisioning.
3. **Backlight permission**: ensure the user's `brightnessctl set` succeeds
   (udev rule from the package; add the user to `video` if the ACL does not
   apply).
4. **Deploy** (`roles/compositor_configs/vars/main.yml`):
   - extend `compositor_configs_config_dirs` with
     `.../ags/settings-panel`, `.../ags/settings-panel/controls`,
     `.../ags/settings-panel/views`;
   - add one `compositor_configs_skeleton_files` entry per new source file
     (panel + subdirs + `bar/widgets/settings.tsx`);
   - `icons.json` generation is unchanged (new groups flow through automatically).
5. **Verify** (`roles/verify/vars/main.yml` + tasks):
   - add every new AGS file to the required-files list;
   - add a new icon sample (e.g. `settings-panel-wifi.svg` and `volume-low.svg`)
     so verify proves the new groups rendered;
   - assert `AstalBluetooth` / `AstalWp` GIR namespaces resolve and
     `bluetooth.service` is enabled;
   - the always-on instance list stays `[ags]` (no new instance).
6. **Gate**: implementation of the AGS panel SHALL NOT begin until steps 1–3
   provision and verify green. Provisioning is the only installer; the runtime
   never detects or installs anything.

## 8. Testing / verification

- Static: `ags bundle dotfiles/config/ags/app.tsx /tmp/ags-check.bundle.js --root .`
  must succeed (catches TS/JSX/import errors).
- Icons: `itr list` + temp `itr render` for `settings`, `settings-panel`,
  `volume`, `ui` (brightness); assert rendered fills are palette colors.
- Provisioning: `make bootstrap` ends green; verify role reports the new files,
  icon samples, bindings, and enabled `bluetooth.service`.
- Manual matrix (on the host, after `ags quit && ags run`): bar icon toggles the
  panel; icon toggles Wi-Fi/BT while the row opens the list; back arrow returns;
  Wi-Fi connects incl. password; BT connects/disconnects; brightness and volume
  sliders write; speaker glyph changes across the 5 levels; hyprmod launches;
  `Esc` and click-outside dismiss; secondary monitor does not show the panel.

## 9. Risks and mitigations

- **Astal package names / binding availability** — confirmed at implementation
  time; the gate stops the change if a binding is absent rather than hand-rolling
  a daemon.
- **AstalNetwork cannot activate connections** — writes go through `nmcli` (NM is
  provisioned); reads stay reactive via Astal.
- **Backlight permission** — explicit provisioning + verify step, since a slider
  that fails silently is worse than no slider.
- **Bluetooth service not running** — provisioning enables it; verify asserts it.
- **Palette contrast** — selection uses foreground text and the on-icon uses
  `@color13`; documented in DESIGN.md so it is not "fixed" back to the family
  defaults that fail on dark palettes.
