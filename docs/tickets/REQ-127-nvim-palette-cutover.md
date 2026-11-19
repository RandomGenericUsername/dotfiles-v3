---
id: REQ-127
title: "Pin the Neovim palette cutover (tpr v0.7.0, runtime v1.6.0, assets v0.21.8, engine v0.1.92)"
kind: requirement
status: in-progress
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

- [ ] Pins are tpr `v0.7.0`, runtime `v1.6.0`, assets `v0.21.8`, engine `v0.1.92`.
- [ ] `make deploy-coverage` PASS.
- [ ] `make gates-ci` PASS.
- [ ] `v0.2.0` tagged/pushed/released.
