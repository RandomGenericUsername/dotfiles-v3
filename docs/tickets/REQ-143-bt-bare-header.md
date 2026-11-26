---
id: REQ-143
title: "Pin ags-bar v0.6.36 + engine v0.1.101 (bare Bluetooth header glyph)"
kind: requirement
status: done
lane: 2 — bounded implementation
worktree: .worktrees/REQ-143/
branch: ticket/REQ-143-bt-bare-header
---

# Pin ags-bar v0.6.36

Use the bare status-bar Bluetooth rune in the panel header (no circular badge),
matching the Wi-Fi header variant. Assets stay v0.22.6.

## Closure (2026-11-26)

- Pinned bar **v0.6.36** and engine **v0.1.101**; assets stay **v0.22.6**.
- `deploy-coverage` PASS; `gates-ci` PASS (5/5).
- Live apply: `ok=1165 changed=28 failed=0`; verify exit 0; doctor clean.
- Live link: `~/.config/ags` -> `apps/bar/v0.6.36`.
- Composition **v0.2.14** tags this close.
