---
id: REQ-146
title: "Pin ags-clipboard v0.7.2"
kind: requirement
status: done
lane: 2 — bounded implementation
links: { openspec: none, bmad: none }
worktree: .worktrees/REQ-146/
branch: ticket/REQ-146-clipboard-v072
---
# Pin ags-clipboard v0.7.2

Pin the full-layout key-focus fix (root focus on open) on top of composition
v0.2.16; run gates, apply/verify, release v0.2.17.

## Closure (2026-11-26)

Pinned v0.7.2; gates-ci PASS; composition v0.2.17.
Live apply exit 0 — `ok=1163 changed=21 failed=0`; verify exit 0; doctor
clean. `~/.config/ags-clipboard` -> `apps/clipboard/v0.7.2`.
