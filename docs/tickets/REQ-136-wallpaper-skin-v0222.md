---
id: REQ-136
title: "Pin assets v0.22.2 (established paint-only wallpaper skin)"
kind: requirement
status: in-progress
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
