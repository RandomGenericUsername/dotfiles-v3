---
id: REQ-123
title: "Neovim consumes the generated palette (tpr nvim projection)"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
worktree: none
branch: none
---

# Neovim consumes the generated palette (tpr nvim projection)

## Why

`req-029` ships LazyVim with Catppuccin as a temporary colorscheme. The palette
pipeline already generates `state/current/palette/colors.*` from the wallpaper
through `theme-producer` and exposes stable consumer links through
`dotfiles-provision`'s `state_links` role. Neovim is not a consumer yet.

This ticket is the clean Route A: make Neovim another first-class palette
consumer, with the role→highlight mapping owned by the palette producer rather
than duplicated in the editor config.

## Requirement (cross-repo plan, implementation later)

1. **theme-producer** — add an `nvim` open projection:
   - `colors.nvim.lua.j2` → `colors.nvim.lua`;
   - a pure mapping from the palette roles (background/foreground/accent/
     surface/error/warning/primary/secondary/outline/…) to Neovim highlight
     groups and the 16 ANSI slots;
   - register it in the projection registry/capability table/format names and
     add fixtures/tests.
2. **dotfiles-runtime** — publish the new palette artifact:
   - add it to `PaletteArtifacts`, `producer_process` hashing, `meta.json`,
     `derive`, `seeder` and `inspect`;
   - keep the existing eight artifacts intact;
   - add the `current/palette/colors.nvim.lua` pointer.
3. **dotfiles-provision** — add the stable consumer link:
   - `state_links_consumers` entry
     `{ base: palette, spine: nvim/lua/dotfiles-palette.lua, target: colors.nvim.lua }`;
   - mirror it in `verify_consumer_symlinks`;
   - update the hardcoded consumer-list test in
     `tests/unit/test_v3_locality.py:90-105`.
4. **dotfiles-assets** — change the LazyVim colorscheme to a function:
   - `require("dotfiles-palette").load()` when the pointer exists;
   - fall back to Catppuccin/habamax when it does not (fresh host before the
     first runtime seed);
   - no host path in the assets config; the module name is the only contract.
5. **dotfiles-v3** — pin the released tpr/runtime/engine/assets tags and run the
   composition gates. This is the shipping step and is explicitly out of scope
   until the user authorizes it.

## Non-goals

- No skin/appearance tokens (that is `REQ-124`).
- No live palette reload while Neovim is open; a new palette applies on the next
  start unless a separate Neovim RPC reloader is designed.
- No changes to the existing gtk/rofi/btop/wlogout/kitty consumers.

## Forbidden now

- No git tag, release, or release-note publication.
- No merge to `master`/`main`.
- No release-metadata or pin bump (`installer.pin`, `assets.tag`, tpr/runtime
  pins, `program-tuple.yaml`).
- No package install or apply/provision run.
- No touching any `ags-*`, `ags-platform`, or other UI worktree/repo.

## Acceptance

- [ ] A design/implementation record names the exact highlight mapping and the
      tpr/runtime/provisioning/assets slices.
- [ ] The tpr projection renders a valid Lua module for both dark and light
      palette modes.
- [ ] Runtime publishes the new artifact without changing the identity of the
      existing eight.
- [ ] Provisioning exposes the stable link and verify asserts it resolves.
- [ ] Neovim loads the generated colorscheme on next start; a missing pointer
      falls back cleanly.
- [ ] No tag, release, pin bump, package install/apply, or UI worktree touched
      during this implementation phase.

## Evidence

- Projection registry and open projections:
  `theme-producer/src/theme_producer/adapters/projections/registry.py:75-130`.
- Palette artifact set and hashing:
  `dotfiles-runtime/src/runtime/adapters/producer_process.py:228-243`,
  `dotfiles-runtime/src/runtime/domain/models.py:56-77`.
- Stable consumer links:
  `dotfiles-provision/ansible/roles/state_links/vars/main.yml:38-46`.
- LazyVim colorscheme accepts a function:
  `LazyVim/lua/lazyvim/config/init.lua:11-15,250-263`.
- Current palette artifacts:
  `theme-producer/src/theme_producer/defaults/templates/colors.yaml.j2`,
  `colors.conf.j2`, `colors.rasi.j2`, `colors.kitty.j2`.

## Next step

Decide the highlight mapping and write the tpr projection design first. Do not
start pin/release work until the user authorizes shipping.
