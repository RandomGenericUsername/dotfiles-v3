---
id: REQ-135
title: "Pin ags-wallpaper-selector v0.6.20 (REQ-005 overlay)"
kind: requirement
status: in-progress
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-135/
branch: ticket/REQ-135-wallpaper-selector-v060
---

# Pin ags-wallpaper-selector v0.6.20

1. Pin the released ags-wallpaper-selector v0.6.20 in `apps.yaml` and
   `FINAL_APP_RELEASES`.
2. deploy-coverage and gates-ci pass.
3. Release the composition.
4. Owner tests the app-only candidate; deploy only after approval.

## Context

- App release: `ags-wallpaper-selector` v0.6.20 (`dd0581a`) — REQ-005
  full-monitor overlay.
- Skin release: `dotfiles-assets` v0.22.2 — wallpaper selector template is
  paint-only and `ags-wallpaper-selector` is enforced in `BOUNDARY_TARGETS`.
- This ticket bumps the composition only. It does not run the full provision.

## Status

In progress. Pin and gates pending.
