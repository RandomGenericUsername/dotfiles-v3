---
id: REQ-144
title: "Pin ags-bar v0.6.37 + engine v0.1.102 (skin-tinted BT header)"
kind: requirement
status: done
lane: 2 — bounded implementation
worktree: .worktrees/REQ-144/
branch: ticket/REQ-144-bt-header-tint
---

Pin the bare Bluetooth header rune tinted from the skin primary; assets stay
v0.22.6.

## Closure (2026-11-26)

- Shipped bar **v0.6.37**, engine **v0.1.102**, assets **v0.22.6**.
- `deploy-coverage` / `gates-ci` PASS.
- Live apply: `ok=1165 changed=26 failed=0`; verify exit 0; doctor clean.
- Live link: `~/.config/ags` -> `apps/bar/v0.6.37`.
- Composition **v0.2.15** tags this close.
