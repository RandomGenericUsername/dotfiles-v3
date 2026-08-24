## Why

The AGS bar is a 53-line skeleton (`dotfiles/config/ags/app.tsx`) that displays
only the static text "dotfiles" and a sparkle emoji. It was created as the
minimal proof that the provisioned AGS (aylurs-gtk-shell-git) works end-to-end
(Story 1.14, 2026-08-18). The comment explicitly says "keep it minimal — do not
gold-plate."

The bar needs to become a functional status bar with reactive widgets that
display real system state using the project's existing custom SVG icon templates.
The icons already exist (battery 11 variants, network 7 variants, power-menu 1
variant) and are rendered by ITR during provisioning into `generated/icons/`.
The bar should consume them through a structured, config-driven icon loading
system — not hardcoded path lookups.

## What Changes

### icons.yaml extension (`dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`)

Add a `bar_mappings` section to the `battery`, `network`, and `power-menu`
groups. This section declares which icon variant to use for each widget state,
making the mapping declarative and single-sourced. ITR ignores `bar_mappings`
(only reads `variants` + `color_mappings`); the bar reads it.

### Astal library packages (`dotfiles/provisioning/packages.yaml`)

Add three Astal libraries as system dependencies alongside AGS:
- `astal-hyprland` — Hyprland IPC, workspace tracking
- `astal-battery` — UPower battery monitoring
- `astal-network` — NetworkManager wrapper

These are GObject Introspection libraries loaded via `gi://` at runtime. They
provide reactive GObject properties that auto-update on state changes — zero
polling.

### AGS config restructure (`dotfiles/config/ags/`)

Restructure from 2 files to a modular layout:
```
ags/
├── app.tsx                 # MODIFY — thin entry
├── style.css               # MODIFY — expanded styles
├── icon-manifest.ts        # NEW — exports parsed icons.json
├── lib/
│   └── icon-registry.ts    # NEW — IconRegistry class
├── bar/
│   ├── Bar.tsx             # NEW — bar window component
│   └── widgets/
│       ├── workspaces.tsx  # NEW — AstalHyprland reactive
│       ├── clock.tsx       # NEW — interval-based clock
│       ├── battery.tsx     # NEW — AstalBattery + icon registry
│       ├── network.tsx     # NEW — AstalNetwork + icon registry
│       └── power-menu.tsx  # NEW — button → wlogout
```

### Icon registry (`lib/icon-registry.ts`)

A structured icon loading system that:
1. Reads from `icons.yaml` (the existing source of truth)
2. Provides `getBarMappings(group)` — returns state→variant mapping
3. Provides `resolve(group, variant)` — returns full SVG file path
4. Uses dual-path resolution: `current/icons/` (Phase 2) → `generated/icons/` (Phase 1)

### Reactive widgets (no polling)

| Widget | Astal Library | Reactive Properties |
|--------|--------------|-------------------|
| Workspaces | `gi://AstalHyprland` | `focused-workspace`, `workspaces` |
| Battery | `gi://AstalBattery` | `percentage`, `charging`, `state` |
| Network | `gi://AstalNetwork` | `wifi.ssid`, `wifi.strength`, `wired.speed` |
| Clock | `interval(1000, ...)` | `GLib.DateTime` |
| Power Menu | click handler | static icon, spawns `wlogout` |

All widgets use `createBinding()` from AGS to subscribe to GObject property
changes. The Astal libraries use DBus proxies (UPower, NetworkManager,
Hyprland IPC) that emit signals on state changes. The bar reacts to these
signals and updates the displayed icon via the IconRegistry.

## Capabilities

### New Capabilities

- `ags-bar-workspaces` — reactive workspace indicator (1–5) via AstalHyprland
  IPC, active workspace highlighted with accent color, click to switch
- `ags-bar-clock` — date/time display updating every second via AGS interval
- `ags-bar-battery` — battery level/charging state via AstalBattery DBus proxy,
  maps to 11 custom SVG icon variants via IconRegistry
- `ags-bar-network` — wifi/ethernet status via AstalNetwork DBus proxy,
  maps to 7 custom SVG icon variants via IconRegistry
- `ags-bar-power-menu` — power menu button displaying custom SVG icon,
  spawns wlogout on click
- `ags-icon-registry` — structured icon loading from icons.yaml bar_mappings,
  dual-path resolution (current/ → generated/)
- `ags-icon-manifest` — bar_mappings extension to icons.yaml as declarative
  state→variant mapping

### Modified Capabilities

- `ags-bar-skeleton` — the minimal bar skeleton is replaced by the full bar
  component (same provisioning pipeline, new files in config/ags/)

## Impact

- **New files**: 8 TypeScript/TSX files under `dotfiles/config/ags/` (bar/, lib/,
  icon-manifest.ts) — all deployed by existing `compositor_configs` role
- **Modified files**: `app.tsx` (thin entry), `style.css` (expanded styles),
  `icons.yaml` (additive `bar_mappings` section), `packages.yaml` (3 new
  Astal packages)
- **Provisioning**: 3 new AUR packages (`astal-hyprland`, `astal-battery`,
  `astal-network`) — same install mechanism as existing `ags` package
- **Verify gate**: no changes — existing criteria still hold; Astal libraries
  are package deps, not verify targets
- **ITR**: no changes — `bar_mappings` is a new optional section ignored by ITR
- **Runtime Phase 2**: no dependency — the dual-path icon resolution works now
  with Phase 1 fallback and transitions seamlessly when Phase 2 lands
