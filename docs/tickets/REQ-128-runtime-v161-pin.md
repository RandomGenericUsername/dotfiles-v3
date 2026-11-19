---
id: REQ-128
title: "Pin runtime v1.6.1 (nvim.lua invocation)"
kind: requirement
status: in-progress
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-128/
branch: ticket/REQ-128-runtime-v161-pin
---

# Pin runtime v1.6.1

## Requirement

1. `cli-tools.yaml` runtime pin `v1.6.0 -> v1.6.1`.
2. `make deploy-coverage` and `make gates-ci` pass.
3. Release `v0.2.1`.

## Acceptance

- [x] Runtime pin is v1.6.1.
- [x] deploy-coverage PASS.
- [x] gates-ci PASS.
- [x] v0.2.1 tagged/pushed/released.
