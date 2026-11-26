---
id: REQ-145
title: "Pin ags-clipboard v0.7.1"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-145/
branch: ticket/REQ-145-clipboard-v071
---

# Pin ags-clipboard v0.7.1

1. Pin `ags-clipboard` **v0.7.1** (image/text polish, newest-item selection)
   on top of composition v0.2.15.
2. `deploy-coverage` and `gates-ci` pass.
3. Apply/verify/doctor.
4. Release composition v0.2.16.

## Context

v0.7.1 fixes image cropping (`CONTAIN`), long stage text clamping, decoded
image texture caching, and newest-item selection on open. Assets (v0.22.6)
and engine (v0.1.102) are unchanged.

## Closure (2026-11-26)

- Pinned `ags-clipboard` **v0.7.1** on composition **v0.2.15**.
- `make deploy-coverage` PASS.
- `make gates-ci` PASS (5/5 gates, parity green).
- Composition **v0.2.16** tags this close.
- Live apply: exit 0 — `ok=1164 changed=25 failed=0`; verify exit 0; doctor clean (28 items, watch/supervision ok).
- Live link: `~/.config/ags-clipboard` -> `apps/clipboard/v0.7.1`.
- Composition **v0.2.16** tags this close.
