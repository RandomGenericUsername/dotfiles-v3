---
id: REQ-127
title: "Pin the Neovim palette cutover (tpr v0.7.0, runtime v1.6.0, assets v0.21.8, engine v0.1.92)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-127/
branch: ticket/REQ-127-nvim-palette-cutover
---

# Pin the Neovim palette cutover

## Requirement

1. `cli-tools.yaml`: tpr `v0.7.0`, dotfiles-runtime `v1.6.0`.
2. `assets.tag` and the program tuple: `v0.21.8`.
3. `installer.pin`: `v0.1.92`.
4. `make deploy-coverage` and `make gates-ci` pass.
5. Release `v0.2.0`.

## Acceptance

- [x] Pins are tpr `v0.7.0`, runtime `v1.6.0`, assets `v0.21.8`, engine `v0.1.92`.
- [x] `make deploy-coverage` PASS.
- [x] `make gates-ci` PASS.
- [x] `v0.2.0` tagged/pushed/released.


- tpr v0.7.0: https://github.com/RandomGenericUsername/theme-producer/releases/tag/v0.7.0
- runtime v1.6.0: https://github.com/RandomGenericUsername/dotfiles-runtime/releases/tag/v1.6.0
- assets v0.21.8: https://github.com/RandomGenericUsername/dotfiles-assets/releases/tag/v0.21.8
- engine v0.1.92: https://github.com/RandomGenericUsername/dotfiles-provision/releases/tag/v0.1.92
- composition v0.2.0: https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.2.0
