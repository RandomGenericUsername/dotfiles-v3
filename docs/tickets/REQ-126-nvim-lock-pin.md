---
id: REQ-126
title: "Pin engine v0.1.91 and assets v0.21.7 (resolved LazyVim lock)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-126/
branch: ticket/REQ-126-nvim-lock-pin
---

# Pin engine v0.1.91 and assets v0.21.7

## Requirement

1. `installer.pin` moves `v0.1.90 -> v0.1.91`.
2. `assets.tag` and the program tuple move `v0.21.6 -> v0.21.7`.
3. `make deploy-coverage` and `make gates-ci` pass.
4. Release `v0.1.99`.

## Acceptance

- [x] Pins are `v0.1.91` / `v0.21.7`.
- [x] `make deploy-coverage` PASS.
- [x] `make gates-ci` PASS.
- [x] `v0.1.99` tagged/pushed/released.


- Engine v0.1.91: https://github.com/RandomGenericUsername/dotfiles-provision/releases/tag/v0.1.91
- Assets v0.21.7: https://github.com/RandomGenericUsername/dotfiles-assets/releases/tag/v0.21.7
- Composition v0.1.99: https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.1.99
