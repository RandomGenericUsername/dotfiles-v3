---
id: REQ-139
title: "Pin ags-bar v0.6.35 + assets v0.22.5 (Wi-Fi + Bluetooth panels)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-139/
branch: ticket/REQ-139-wifi-bt-panels
---

# Pin ags-bar v0.6.35 + assets v0.22.5

1. Pin `ags-bar` **v0.6.35** (approved Wi-Fi REQ-007 + Bluetooth REQ-009
   control-centre panels).
2. Pin `dotfiles-assets` **v0.22.5** (Wi-Fi + Bluetooth overlay skins on the
   v0.22.4 lineage, not the `surface.overlay` v0.23.0 line).
3. Bump the engine pin to v0.1.99 (assets v0.22.5 mirror; bar fixture v0.6.35).
4. `deploy-coverage` and `gates-ci` pass.
5. Apply/verify/doctor; composition v0.2.12 tags the close.

## Context

- `ags-bar` v0.6.35 merges the approved REQ-007 Wi-Fi popover and REQ-009
  Bluetooth popover branches.
- Assets v0.22.5 carries both approved overlay skin paints. Established
  `surface.panel` architecture; no `surface.overlay`.
- Skin-dependent paint and app behavior are separate; the apps own layout and
  content, the skin owns role paint.

## Closure (2026-11-25)

- Pinned `ags-bar` **v0.6.35**, `dotfiles-assets` **v0.22.5**, engine **v0.1.99**.
- `make deploy-coverage` PASS; `make gates-ci` PASS (5/5, parity green).
- Live apply: `ok=1166 changed=32 failed=0`; verify exit 0;
  `dotfiles-runtime doctor` clean (28 items, watch/supervision ok).
- Live links: `~/.config/ags` -> `apps/bar/v0.6.35`; clipboard v0.7.0;
  wallpaper selector v0.6.29; assets v0.22.5 installed.
- Generated `appearance/ags.css` contains the `.wifi-*` and `.bt-*` skin rules.
- Composition **v0.2.12** tags this close.
