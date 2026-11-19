---
id: REQ-130
title: "Pin the live Neovim palette reload (runtime v1.6.3, assets v0.21.9, engine v0.1.93)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-130/
branch: ticket/REQ-130-nvim-reload-cutover
---

# Pin the live Neovim palette reload

1. runtime `v1.6.3`, assets `v0.21.9`, engine `v0.1.93`.
2. `make deploy-coverage` and `make gates-ci` pass.
3. Release `v0.2.3`.

## Acceptance

- [x] Pins updated.
- [x] deploy-coverage PASS.
- [x] gates-ci PASS.
- [x] v0.2.3 tagged/pushed/released.


- runtime v1.6.3: https://github.com/RandomGenericUsername/dotfiles-runtime/releases/tag/v1.6.3
- assets v0.21.9: https://github.com/RandomGenericUsername/dotfiles-assets/releases/tag/v0.21.9
- engine v0.1.93: https://github.com/RandomGenericUsername/dotfiles-provision/releases/tag/v0.1.93
- composition v0.2.3: https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.2.3
