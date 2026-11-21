---
id: REQ-137
title: "Wallpaper skin polish: app v0.6.24 + assets v0.22.3"
kind: requirement
status: in-progress
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-137/
branch: ticket/REQ-137-skin-polish
---

# Wallpaper skin polish

1. Pin `ags-wallpaper-selector` v0.6.24 (popover shell clipping fix) and
   `dotfiles-assets` v0.22.3 (look-frame radius from `surface.control.radius`).
2. Pin engine v0.1.97.
3. deploy-coverage and gates-ci pass; apply/verify/doctor.
4. Composition v0.2.10 tags the close.

## Context

Owner feedback after the skin cutover: the settings panel shell clipped the
skin's rounding, and the look chips had app rounding inside square skin
containers. The frame radius now comes from the skin template (the sound-panel
pattern), and the app-owned popover shell no longer clips the card surface.
