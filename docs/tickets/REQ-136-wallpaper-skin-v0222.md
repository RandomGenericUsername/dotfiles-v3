---
id: REQ-136
title: "Pin assets v0.22.2 (established paint-only wallpaper skin)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-136/
branch: ticket/REQ-136-overlay-skin
---

# Pin assets v0.22.2 (established paint-only wallpaper skin)

1. Pin `dotfiles-assets` v0.22.2 and engine v0.1.96 in `assets.yaml`, the
   program tuple and `installer.pin`.
2. deploy-coverage and gates-ci pass.
3. Deploy the assets cutover; verify; doctor.
4. Record the live evidence; release the composition.

## Context

The established architecture maps AGS bar/layer-shell overlays to
`surface.panel`; the host policy delegates panel radius/border-width to the
compositor. v0.22.2 is the paint-only wallpaper skin on that role. The
`surface.overlay` experiment (contracts v0.14.0 / assets v0.23.0) is released
but not consumed.

## Closure (2026-11-20)

- Engine `v0.1.96` (`2c342b9`) pins assets `v0.22.2`; composition pin commit
  `7b25c577`; `deploy-coverage` and `gates-ci` pass.
- Live apply: `ok=1164 changed=25 failed=0`; `verify` exit 0;
  `dotfiles-runtime doctor` clean.
- Live links resolve to `apps/wallpaper-selector/v0.6.23`; assets `v0.22.2`
  installed; the generated `current/appearance/ags-wallpaper-selector.css` maps
  `.ws-control-bar` to `surface.panel` (`@surface`, 1 px, radius 0).
- Established architecture: AGS overlays use `surface.panel`; `[host]`
  delegates panel/card/control/cell geometry to Hyprland (`rounding 0`,
  `border 1` here).
- Composition `v0.2.9` tags this close.
- Not consumed: the `surface.overlay` experiment (contracts `v0.14.0`,
  assets `v0.23.0`). Do not pin it.
