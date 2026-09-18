## Why

The desktop has no control center. Wi-Fi can only be changed by opening the
`wifitui` TUI from the bar, Bluetooth has no surface at all, volume and
brightness are Fn-key only (no on-screen feedback), and `hyprmod` is a CLI with
no launcher. The owner approved a macOS-style control-center panel: a
status-bar settings icon that opens a panel anchored top-right under the bar,
with Wi-Fi and Bluetooth as icon-toggle rows that open in-place network/device
lists, plus Display (brightness) and Sound (volume) sliders and a Hyprmod
launch tile.

The approved UX artifacts are the design source of truth:

- `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-2026-09-18/.working/key-screens-native.html`
  (Direction B — "Family Native": main, main-with-Bluetooth-off, Wi-Fi list,
  Wi-Fi password entry, Bluetooth devices, and the volume icon ladder)
- `.../ux-designs/ux-dotfiles-repo-v3-2026-09-18/.working/directions-1.html`
  (the direction comparison the owner chose from)
- `_bmad-output/planning-artifacts/gui-unification-ux-spec.md` (the GUI family
  visual language: glass panel, solid `@color10` selection, `@color06`/`@color13`
  action intent, "fields are surfaces not holes")

Per the owner's standing constraint, **all setup — packages, GObject-Introspection
bindings, services, permissions, file deployment, icon rendering — is performed by
the provisioning process; the runtime (AGS) only consumes what provisioning
delivered.** No runtime install, no first-run bootstrap, no runtime package
detection.

## What Changes

### Icon templates and mappings (additive)

Five supplied SVGs enter the existing ITR pipeline (literal `fill="black"` →
`{{COLOR_FOREGROUND}}` placeholders, registered in `icons.yaml`):

| Group | Variants | Template root | Source SVG |
|---|---|---|---|
| `settings` | `default` (bar icon, `bar_mappings`) | `status-bar/settings/` | `status-bar-settings.svg` |
| `settings-panel` | `wifi`, `bluetooth`, `hyprmod` | `settings-panel/*/` | `settings-panel-*.svg` |
| `brightness` | `default` (generic, own group) | `brightness/default/` | `brightness.svg` |
| `volume` | `muted`, `lowest`, `low`, `medium`, `max` | `volume/*/` | `volume-*.svg`, `lowest-volume.svg`, etc. |

The `settings` group joins the runtime **contrast-guard allowlist** (bar icons
retarget on light wallpapers). Panel/volume/brightness glyphs render over the
opaque panel surface and stay out of the allowlist.

### New AGS settings panel (bar instance)

A second AGS window inside the **existing bar instance**
(`dotfiles/config/ags/`) — no new autostart instance. New tree:

```
dotfiles/config/ags/settings-panel/
├── SettingsPanel.tsx        # window: anchored TOP|RIGHT under the bar, primary monitor
├── state.ts                 # shared visible/view signal (bar ↔ panel)
├── primitives.tsx           # Card / Tile / IconToggle / Slider / Row
├── controls/
│   ├── wifi.tsx             # AstalNetwork reactive; toggle + AP list + password entry
│   ├── bluetooth.tsx        # AstalBluetooth reactive; toggle + device list
│   ├── brightness.tsx       # brightnessctl-backed slider
│   ├── volume.tsx           # AstalWp slider + level-aware speaker glyph
│   └── hyprmod.tsx          # execAsync(["hyprmod"]) action tile
└── views/
    ├── MainView.tsx
    ├── WifiView.tsx
    └── BluetoothView.tsx
```

Plus `dotfiles/config/ags/bar/widgets/settings.tsx` (bar button that toggles the
panel) and additions to `bar/Bar.tsx` and `style.css`.

### Behavior (from the approved mocks)

- **Icon is the power toggle; the row opens the list** (owner correction to the
  first mock — no explicit pill switch). Filled icon = on, dimmed = off.
- Wi-Fi / Bluetooth subviews are **in-place swaps with a back arrow**; panel
  dimensions stay stable.
- Wi-Fi list connects **in-panel**, including an inline **password entry** for
  secured networks.
- **Audio level glyph is level-aware**: muted (0%), lowest (1–25%), low (26–50%),
  medium (51–75%), max (76–100%).
- Panel is **primary monitor only**, dismissed on `Esc` and click-outside.
- **Extensible**: sections are composable primitives so future cards (VPN, Night
  Light, power profiles, media) append without redesign.

### Provisioning (the dependency gate)

- The `packages` role installs the Astal Bluetooth and WirePlumber bindings
  (AUR-only, same family/channel as the installed `astal-*` set), plus `bluez`
  and `bluez-utils`; it enables `bluetooth.service` and ensures the user can
  drive the backlight (`brightnessctl`).
- `compositor_configs` deploys every new AGS file (explicit per-file entries and
  the new `settings-panel/` config dirs) and keeps generating `icons.json` from
  `icons.yaml`.
- `verify` asserts: every new AGS file present, the new icon variants render
  into `current/icons/`, the Astal Bluetooth/Wp namespaces are importable,
  `bluetooth.service` is enabled, and the bar instance remains the always-on one.

## Capabilities

### New Capabilities

- `ags-settings-panel` — the panel window, shared visibility/view state, the bar
  settings button, the icon-as-toggle / row-opens-list interaction, Wi-Fi connect
  flow with password entry, Bluetooth connect/disconnect, brightness and volume
  sliders (level-aware glyph), Hyprmod launch, dismissal, primary-monitor
  placement, and the extensible section primitives.
- `settings-panel-icons` — the four icon groups added to the ITR pipeline
  (templates with palette placeholders, `icons.yaml` registration with
  `bar_mappings` for `settings`, and the contrast-guard allowlist entry).
- `settings-panel-provisioning` — package/binding installation, `bluez` service
  enablement, backlight permission, AGS source deployment, manifest generation,
  and the verify assertions; this provision is the implementation gate.

### Modified Capabilities

*(None. The bar gains a widget but no existing capability contract changes; the
icon pipeline and provisioning contracts are extended additively.)*

## Impact

- **New files**: ~13 TSX/TS files under `dotfiles/config/ags/settings-panel/` +
  `bar/widgets/settings.tsx`; 9 icon templates; 4 icon-mapping group entries.
- **Modified files**: `dotfiles/config/ags/{app.tsx,style.css}`,
  `dotfiles/config/ags/bar/Bar.tsx`,
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`,
  `dotfiles/provisioning/packages.yaml`,
  `src/provisioning/ansible/roles/packages/vars/arch.yml`,
  `src/provisioning/ansible/group_vars/{arch,debian-family}.yml`,
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml` (+ task for service /
  binding assertions), and the runtime contrast-guard allowlist.
- **Provisioning**: 2–4 new packages (confirm exact AUR names at implementation
  time), one systemd service enable, one backlight-permission check. No new
  autostart instance; the panel lives in the always-on bar instance.
- **Verify gate**: extended (new files, new icon samples, binding importability,
  `bluetooth.service` enabled).
- **Runtime**: no new install/setup logic; the panel only reads GObject state and
  writes through already-provisioned control surfaces.
- **Non-goals (v1)**: Wi-Fi "Other…"/hidden-network dialog, Bluetooth pairing
  PIN UI beyond the OS agent, Night Light / VPN / power-profile sections, panel
  on non-primary monitors, per-monitor instances, media controls.
