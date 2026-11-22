---
id: REQ-137
title: "Wallpaper skin polish: app v0.6.29 + assets v0.22.3"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-137/
branch: ticket/REQ-137-skin-polish
---

# Wallpaper skin polish

1. Pin `ags-wallpaper-selector` v0.6.29 (popover shell clipping fix) and
   `dotfiles-assets` v0.22.3 (look-frame radius from `surface.control.radius`).
2. Pin engine v0.1.97.
3. deploy-coverage and gates-ci pass; apply/verify/doctor.
4. Composition v0.2.10 tags the close.

## Context

Owner feedback after the skin cutover: the settings panel shell clipped the
skin's rounding, and the look chips had app rounding inside square skin
containers. The frame radius comes from the skin template (the sound-panel pattern). The
settings panel is now the mock's in-page `.settings-pop` with a full-window
catcher; a `Gtk.Popover` is a separate compositor popup whose grab/pointer
focus swallowed the next same-spot gear click. The app-owned popover shell
clipping fix remains for the old path.

## Batch record

Canonical architecture, live state and the pending design index:
`docs/117-redesign-batch.md`.

## Closure (2026-11-21)

- Engine `v0.1.97` (`f9a0fdb`) pins assets `v0.22.3`; tag pushed. Full engine
  `make gates` RC 0: 1145 passed / 3 skipped; hermetic 1110 passed / 38
  skipped; ruff and `uv lock --check` clean.
- Composition pin commit `686c6716` (engine v0.1.97, assets v0.22.3) and app
  bump `f1c2c2a4` (v0.6.29) merged at `572ea2fa`.
- `make deploy-coverage` PASS; `make gates-ci` PASS (5/5 gates, parity green).
- Live apply: `ok=1163 changed=25 failed=0`; verify in the apply exit 0;
  `dotfiles-runtime doctor` clean (28 items, watch/supervision ok).
- Live links: `~/.config/ags-wallpaper-selector` ->
  `apps/wallpaper-selector/v0.6.29`; assets `v0.22.3` installed.
- Generated `appearance/ags-wallpaper-selector.css`: `.ws-control-bar`
  `@surface`, 1 px, radius 0 (Hyprland `rounding 0` / `border 1`);
  `.ws-look-frame` radius 0 from `surface.control.radius`.
- Composition `v0.2.10` tags this close.
