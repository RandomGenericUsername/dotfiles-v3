---
id: REQ-125
title: "Pin engine v0.1.90 (Neovim stale-file prune)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-125/
branch: ticket/REQ-125-neovim-stale-prune-pin
---

# Pin engine v0.1.90 (Neovim stale-file prune)

## Why

`dotfiles-assets v0.21.6` replaced the hand-rolled Neovim config with LazyVim.
The config copy does not delete files absent from the source, so hosts that had
the old config kept `lua/options.lua` and six old `lua/plugins/*.lua` files
beside the new tree. Engine `v0.1.90` prunes those seven retired paths.

## Requirement

1. `dotfiles/provisioning/installer.pin` moves `v0.1.89 -> v0.1.90`.
2. Assets stay `v0.21.6`; no other pin/tuple changes.
3. `make deploy-coverage` and `make gates-ci` pass.
4. Release tag `v0.1.98` after the gates.

## Acceptance

- [x] `installer.pin` is `v0.1.90`; assets stay `v0.21.6`.
- [x] `make deploy-coverage` PASS.
- [x] `make gates-ci` PASS.
- [x] Composition `v0.1.98` tagged/pushed/released.


- Engine `v0.1.90` release: https://github.com/RandomGenericUsername/dotfiles-provision/releases/tag/v0.1.90
- Composition `v0.1.98` release: https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.1.98
