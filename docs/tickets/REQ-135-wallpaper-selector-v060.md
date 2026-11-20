---
id: REQ-135
title: "Pin ags-wallpaper-selector v0.6.23 (REQ-005 overlay)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-135/
branch: ticket/REQ-135-wallpaper-selector-v060
---

# Pin ags-wallpaper-selector v0.6.23

1. Pin the released ags-wallpaper-selector v0.6.23 in `apps.yaml` and
   `FINAL_APP_RELEASES`.
2. deploy-coverage and gates-ci pass.
3. Release the composition.
4. Owner tests the app-only candidate; deploy only after approval.

## Context

- App release: `ags-wallpaper-selector` v0.6.23 (`64cb59a`) — REQ-005
  full-monitor overlay.
- Skin release: `dotfiles-assets` v0.22.2 — wallpaper selector template is
  paint-only and `ags-wallpaper-selector` is enforced in `BOUNDARY_TARGETS`.
- This ticket bumps the composition only. It does not run the full provision.

## Status

Done. `ags-wallpaper-selector` v0.6.23 is pinned, deployed and verified;
composition v0.2.8 tags this close.

## Closure (2026-11-20)

- Pinned `ags-wallpaper-selector` **v0.6.23** in `apps.yaml` and
  `FINAL_APP_RELEASES` (`fcf392c2`); `deploy-coverage` and `gates-ci` pass.
- Live deploy from this composition: `dotfiles-provision apply` →
  `ok=1163 changed=25 failed=0`; `verify` exit 0; `dotfiles-runtime doctor`
  clean.
- Live links resolve to `apps/wallpaper-selector/v0.6.23`; `pinned` is
  `v0.6.23`; `wallpaper-selector-ui` cold-starts it.
- Composition **v0.2.8** tags this close commit (manifests unchanged from the
  pin).
- `dotfiles-assets` stays at **v0.22.1**: v0.22.2 is released but its overlay
  paint (`surface.panel`) conflicts with the frozen mock; the overlay role/token
  is a post-dev item.
