---
id: REQ-129
title: "Pin runtime v1.6.2 (optional nvim palette artifact)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-129/
branch: ticket/REQ-129-runtime-v162-pin
---

# Pin runtime v1.6.2

1. `cli-tools.yaml` runtime pin `v1.6.1 -> v1.6.2`.
2. `make deploy-coverage` and `make gates-ci` pass.
3. Release `v0.2.2`.

## Acceptance

- [x] Runtime pin is v1.6.2.
- [x] deploy-coverage PASS.
- [x] gates-ci PASS.
- [x] v0.2.2 tagged/pushed/released.


- Runtime v1.6.2: https://github.com/RandomGenericUsername/dotfiles-runtime/releases/tag/v1.6.2
- Composition v0.2.2: https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.2.2
