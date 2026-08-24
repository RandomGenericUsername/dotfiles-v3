## 1. icons.yaml bar_mappings extension

- [ ] 1.1 Add `bar_mappings` section to `battery` group in `icons.yaml`
  - widget: battery, icon_size: 24
  - states: discharging-0/25/50/75/100, charging-0/25/50/75/100, plugged
  - Each state maps to existing variant name
- [ ] 1.2 Add `bar_mappings` section to `network` group in `icons.yaml`
  - widget: network, icon_size: 24
  - states: wifi-high/medium/low/disabled/no-internet, ethernet, ethernet-no-internet
  - Each state maps to existing `*-default` variant name
- [ ] 1.3 Add `bar_mappings` section to `power-menu` group in `icons.yaml`
  - widget: power-menu, icon_size: 24
  - states: default → power-menu-default
- [ ] 1.4 Add YAML→JSON conversion step in provisioning (icons.yaml → icons.json)
  - Ansible task in `compositor_configs` or `config_copies` role
  - Produces `config/ags/icons.json` from `icon-mappings/icons.yaml`

## 2. Provisioning — Astal packages

- [ ] 2.1 Add `astal-hyprland`, `astal-battery`, `astal-network` to `packages.yaml`
- [ ] 2.2 Add AUR package mappings in `ansible/roles/packages/vars/arch.yml`
- [ ] 2.3 Verify package names are correct for Arch AUR

## 3. Icon registry

- [ ] 3.1 Create `lib/icon-registry.ts`
  - `IconRegistry` class
  - Constructor loads `icons.json` (imported at build time)
  - `getBarMappings(group: string): BarMapping | null`
  - `resolve(group: string, variant: string): string | null`
  - Dual-path: checks `current/icons/` then `generated/icons/`
- [ ] 3.2 Export singleton `registry` instance

## 4. Bar shell

- [ ] 4.1 Create `bar/Bar.tsx`
  - Window with exclusivity, anchoring (TOP | LEFT | RIGHT)
  - Centerbox with start (workspaces), center (clock), end (battery, network, power-menu)
  - Import all widgets
- [ ] 4.2 Modify `app.tsx` to import and use `Bar` from `bar/Bar.tsx`
  - Keep `app.apply_css(colors.css)` for palette loading
  - Keep `app.get_monitors().map(Bar)` for multi-monitor

## 5. Widgets

- [ ] 5.1 Create `bar/widgets/workspaces.tsx`
  - Import `Hyprland` from `gi://AstalHyprland`
  - `createBinding(hyprland, "focused-workspace")` for active indicator
  - `createBinding(hyprland, "workspaces")` for workspace list
  - Render 5 buttons, active one with `@color_01` background
  - Click handler: `hyprland.dispatch("workspace", id.toString())`
- [ ] 5.2 Create `bar/widgets/clock.tsx`
  - Use AGS `interval(1000, ...)` to update time
  - Format as `HH:MM` (24h) and `YYYY-MM-DD`
  - Styled with `@color_foreground`
- [ ] 5.3 Create `bar/widgets/battery.tsx`
  - Import `Battery` from `gi://AstalBattery`
  - `createBinding(device, "percentage")` and `createBinding(device, "charging")`
  - Map percentage + charging to state key via IconRegistry
  - Render `<image>` with resolved SVG path
  - Handle no-battery case (desktop) — hide widget
- [ ] 5.4 Create `bar/widgets/network.tsx`
  - Import `Network` from `gi://AstalNetwork`
  - `createBinding(network, "wifi")` and `createBinding(network, "wired")`
  - Map wifi strength / wired state to state key via IconRegistry
  - Render `<image>` with resolved SVG path
  - Handle no-network case — show disabled icon
- [ ] 5.5 Create `bar/widgets/power-menu.tsx`
  - Static icon from IconRegistry (`power-menu` group, `default` state)
  - Click handler: `execAsync(["wlogout"])`
  - Render `<button>` with `<image>` child

## 6. Styles

- [ ] 6.1 Expand `style.css`
  - Window bar: `min-height: 48px`, transparent background
  - Centerbox: `@color_00` background, `border-radius: 10px`, `margin: 8px`
  - `.widget-icon`: `min-width: 24px`, `min-height: 24px` (normalizes SVG viewBox)
  - `.workspace-indicator button`: `min-width: 32px`, `min-height: 32px`, `border-radius: 8px`
  - `.workspace-indicator button.active`: `background-color: @color_01`
  - Clock: `padding: 0 16px`, `font-size: 14px`
  - Widget containers: `spacing: 8px`

## 7. Verification

- [ ] 7.1 Run `ags run` and verify bar renders with all widgets
- [ ] 7.2 Verify workspace switching works (click + keybind)
- [ ] 7.3 Verify battery widget updates reactively (if laptop)
- [ ] 7.4 Verify network widget updates reactively
- [ ] 7.5 Verify power menu spawns wlogout
- [ ] 7.6 Verify icons display correctly (SVG scaling, colors from palette)
- [ ] 7.7 Verify bar survives Hyprland workspace switches
- [ ] 7.8 Verify provisioning re-apply does not break bar (don't-clobber guard)
