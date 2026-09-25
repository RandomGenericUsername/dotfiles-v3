## 1. Icons — signal templates + manifest variants (additive only)

- [x] 1.1 Convert the four owner source files
  `~/Downloads/signal {low,medium,good,high}.svg` into
  `dotfiles/assets/icon-templates/settings-panel/signal/{low,medium,good,high}/default/icon.svg`:
  keep the 1024 viewBox and path geometry byte-faithful to the source, rewrite
  every `fill="black"` → `fill="{{COLOR_FOREGROUND}}"`, keep inactive bars'
  `fill-opacity="0.5"` (idiom of
  `dotfiles/assets/icon-templates/status-bar/network/wifi-low/default/icon.svg`).
  Ignore `~/Downloads/signal-svgrepo-com.svg` (16×16, wrong set).
- [x] 1.2 `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` —
  append 4 variants under the EXISTING `settings-panel:` group (`:364`,
  2-space list indent, nested `color_mappings` at 8 spaces):
  `signal-low|medium|good|high` → `template:
  settings-panel/signal/<v>/default/icon.svg` → `output:
  settings-panel-signal-<v>.svg`. No `color_mappings` on these entries — they
  inherit the group's `COLOR_FOREGROUND: foreground` (and `settings-panel` is
  not in `BAR_GROUPS`, so the guard never rewrites it). Comment above the
  block: `# Signal-strength glyphs for the Bluetooth row (guard-exempt group).`
- [x] 1.3 `icons.yaml` — append 5 variants under the EXISTING `battery:` group
  (`:1`): `system-battery-{0,25,50,75,100}` → `template:
  status-bar/battery/battery-<n>/default/icon.svg` → `output:
  system-battery-<n>.svg` + variant-level
  `color_mappings: {COLOR_FOREGROUND: foreground}` (mirror the indent and pin
  of `volume-system-*`). Comment: `# System-surface copies: variant-level pin
  exempts them from the bar contrast guard.`
- [x] 1.4 Validate: `python -c "import yaml; yaml.safe_load(open('dotfiles/config/icon-template-color-scheme-mappings/icons.yaml'))"`
  passes; every new `template:` path exists under
  `dotfiles/assets/icon-templates/`; `itr list --mappings
  dotfiles/config/icon-template-color-scheme-mappings/icons.yaml | grep -c "signal-"`
  (= 4) and `grep -c "system-battery-"` (= 5).
- [x] 1.5 FORBIDDEN (drift tripwires): no edits to group-level
  `color_mappings` of `battery`, no `bar_mappings` edits, no new groups, no
  `panel-*` names, no edits to the stale sibling files (`battery.yaml`,
  `network.yaml`, …), no touching bare `battery-*` variants, no template file
  changes to existing icons.

## 2. Manifest projection — regenerate `icons.json` (never hand-edit)

- [x] 2.1 Regenerate `dotfiles/config/ags/icons.json` with the established
  transform: `json.dumps(yaml.safe_load(open(<icons.yaml>)), indent=2,
  sort_keys=True) + "\n"` (mirror of the `compositor_configs` manifest task).
- [x] 2.2 Addition-only proof: `git diff --stat` shows ONLY `icons.yaml` +
  `icons.json` for this task group; `git diff dotfiles/config/ags/icons.json`
  contains 9 added variant entries (`settings-panel-signal-*`,
  `system-battery-*`) and ZERO removed/modified lines; `python -m json.tool
  dotfiles/config/ags/icons.json` passes.

## 3. Row implementation — live data, no hardcode

- [x] 3.1 `dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx` —
  add two pure helpers (module-level, no JSX): `batteryVariant(level)` →
  `system-battery-{0,25,50,75,100}` using the bar's boundaries
  (`<25→0, <50→25, <75→50, <100→75`, else `100`); `signalVariant(rssi)` →
  `signal-{high,good,medium,low}` for `≥−60 / ≥−70 / ≥−80 / else`. Both take
  live service values only.
- [x] 3.2 Restructure `BluetoothRow` (`:107-151`) to the two-line mock:
  outer `<box orientation={1} spacing={3}>` per row →
  line 1: `<box>` with name `<label class="settings-net-name">` (add
  `maxWidthChars` + `ellipsize={Pango.EllipsizeMode.END}` + `tooltipText={name}`)
  hexpanded, then the existing `settings-badge conn` `Connected` badge;
  line 2: `<box class="settings-row-meta">` with
  `justify-content: space-between` → left `<box orientation={1}>` stacked meta
  rows, right the existing spinner + `settings-rowact` buttons with
  `valign={Gtk.Align.CENTER}`. Preserve ALL existing behavior: `absent`
  dimming, busy spinner, `sensitive` gates, `act()`/`unpair()` handlers.
- [x] 3.3 Meta lines (left block): each row = `<image pixel_size={14}
  $={...set_from_file(registry.resolve(...) ?? "")}>` + label, pattern of
  `VolumeSlider.tsx:61-67`. Battery row: `registry.resolve("battery",
  batteryVariant(battery()))`, label `battery() + "%"`, `visible` only when
  `battery() > 0`. Signal row: `registry.resolve("settings-panel",
  "signal-" + signalVariant(rssi()))`, label `` `−${Math.abs(rssi())} dBm` ``,
  `visible` only when `rssi() < 0`.
- [x] 3.4 `dotfiles/config/ags/style.css` — add `.settings-row-meta` (line 2,
  `spacing` + `justify-content: space-between`), `.settings-meta-icon`
  (`14px`, `flex: none`), `.settings-meta-stat` (10.5px, `opacity: 0.72`,
  `line-height: 14px`), and ellipsis-safe name rules. Do NOT rely on CSS
  `max-width` for the name (GTK4 ignores it — comment in
  `.audio-routing label`, `style.css:853-860`).
- [x] 3.5 Hardcode tripwire: `grep -nE '"[0-9]+%"|dBm"' dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx`
  finds no literal percent/dBm value other than the composed template string;
  `grep -n 'resolve("battery", "battery-' …` returns nothing (bare variants
  forbidden in the panel).
- [x] 3.6 Type/bundle gate: `ags bundle` (or the project's AGS typecheck)
  exits 0; existing settings-panel views compile unchanged.

## 4. Gates — anti-drift harnesses (additive only)

- [x] 4.1 `src/provisioning/ansible/roles/verify/vars/main.yml:367`
  (`verify_icons_samples`): append
  `{{ verify_state_current_dir }}/icons/system-battery-100.svg` and
  `{{ verify_state_current_dir }}/icons/settings-panel-signal-good.svg`. Keep
  the existing 5 entries. Mirror in
  `src/provisioning/tests/unit/test_verify_role.py` fixtures if they assert
  the sample list.
- [x] 4.2 `src/runtime/tests/unit/test_derive_icon_contrast_overlay.py`: add
  ONE test mirroring the `camera-accent` exemption (`:63-72`, assertions
  `:281-319`): light palette flips bare `battery.COLOR_FOREGROUND`, while
  `system-battery-*` variant blocks and `settings-panel-signal-*` outputs are
  byte-identical in the overlay. No existing test may be modified.
- [ ] 4.3 Pre-gates green:
  `uv run --directory src/runtime pytest -q`,
  `uv run --directory src/provisioning pytest -q`,
  `make contracts-check`, `itr list --mappings
  dotfiles/config/icon-template-color-scheme-mappings/icons.yaml | grep -c
  "system-battery-\|signal-"` (= 9).
- [x] 4.4 Structural mock check: open
  `openspec/changes/bluetooth-row-battery-signal/mockups/bluetooth-row-final.html`
  side by side with the live panel and confirm line order, badge placement,
  stacked meta, and right-side action placement match; ANY deviation is a
  fix, not a "close enough".
- [x] 4.5 Live gate (bundle-green ≠ working): after deploy, the AGS log shows
  no TS/bundle error and the row renders real values — set a device battery/
  RSSI, confirm the glyph and number change without rebuilding.
- [ ] 4.6 Light-wallpaper proof: `dotfiles-runtime wallpaper set <light.png>`
  → bar battery glyph goes dark (guard ON) while the panel's battery/signal
  glyphs stay palette `foreground`; then restore the original wallpaper and
  confirm the bar returns to authored colors.

## 5. Deploy — narrow path (no full bootstrap)

- [x] 5.1 Run as a PAIR (assets must land before compositor-configs reads
  `icons.yaml`):
  `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg ansible-playbook -i
  src/provisioning/ansible/inventory/localhost.yaml -e install_dir=$(realpath
  ~/.local/share/dotfiles) -e os_family=arch
  src/provisioning/ansible/playbooks/assets.yaml` then the same command with
  `compositor-configs.yaml` (user-scoped: no become).
- [x] 5.2 `dotfiles-runtime icons regenerate` — live-palette re-derive
  (contrast `auto`), repoints `current/icons`, restarts AGS so the new row
  code re-bundles. Must report zero `reload_failures`.
- [x] 5.3 `uv run --directory src/provisioning dotfiles-provision verify`
  green — proves `verify_icons_samples` (incl. the 2 new entries) and the
  AGS config file list (`BluetoothContent.tsx`, `style.css`) converged.
- [ ] 5.4 Final owner-accept gate: `make bootstrap` green, then owner visual
  sign-off on the live panel against `mockups/bluetooth-row-final.html`.

## 6. Docs (minimal)

- [x] 6.1 `docs/Adding an Icon — ITR and Provisioning Pipeline.md`: one short
  subsection noting the Bluetooth row's two icon sources — `settings-panel`
  group (guard-exempt) and `battery` group `system-battery-*` variants
  (variant-level pin) — and the standing rule "panel surfaces never resolve
  bare `battery-*`". No other doc churn.
