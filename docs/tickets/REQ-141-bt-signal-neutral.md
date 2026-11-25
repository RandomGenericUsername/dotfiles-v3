---
id: REQ-141
title: "Pin assets v0.22.6 + engine v0.1.100 (neutral Bluetooth signal badge)"
kind: requirement
status: done
lane: 2 — bounded implementation
worktree: .worktrees/REQ-141/
branch: ticket/REQ-141-bt-signal-neutral
---

# Pin assets v0.22.6 + engine v0.1.100

Normalize the Bluetooth full-signal badge to the same neutral container as
good/medium/low. Bar remains v0.6.35.

## Closure (2026-11-25)

- Pinned assets **v0.22.6** and engine **v0.1.100**; bar stays **v0.6.35**.
- `deploy-coverage` PASS; `gates-ci` PASS (5/5).
- Live apply: `ok=1164 changed=25 failed=0`; verify exit 0; doctor clean.
- Assets v0.22.6 installed; regenerated
  `current/icons/settings-panel-bluetooth-signal-full.svg` has the same neutral
  badge fill as good/medium/low (`#292a2f` on the live palette).
- Composition **v0.2.13** tags this close.
