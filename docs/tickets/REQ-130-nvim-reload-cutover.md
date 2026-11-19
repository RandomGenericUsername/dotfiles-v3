---
id: REQ-130
title: "Pin the live Neovim palette reload (runtime v1.6.3, assets v0.21.9, engine v0.1.93)"
kind: requirement
status: in-progress
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
