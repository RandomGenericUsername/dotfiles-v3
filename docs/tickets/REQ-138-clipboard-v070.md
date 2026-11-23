---
id: REQ-138
title: "Pin ags-clipboard v0.7.0 + assets v0.22.4"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-138/
branch: ticket/REQ-138-clipboard-v070-assets-v0224
---

# Pin ags-clipboard v0.7.0 + assets v0.22.4

1. Pin `ags-clipboard` **v0.7.0** (REQ-009 card-stage full/compact clipboard).
2. Pin `dotfiles-assets` **v0.22.4** (REQ-042 clipboard paint-only skin on
   `surface.panel`; base v0.22.3, not the `surface.overlay` v0.23.0 line).
3. Bump the engine pin to v0.1.98 (assets v0.22.4 mirror).
4. `deploy-coverage` and `gates-ci` pass.
5. Release the composition.

## Context

- App release: `ags-clipboard` v0.7.0 (card-stage full/compact, in-page settings,
  app-owned content accents, fixed stage cards, full search/filter/clear,
  compact Enter collapse).
- Assets release: `dotfiles-assets` v0.22.4 (clipboard skin paint-only;
  `ags-clipboard` added to `BOUNDARY_TARGETS`).
- This ticket bumps the composition only. Full provision/deploy follows the
  release.

## Closure (2026-11-23)

- Pinned `ags-clipboard` **v0.7.0**, `dotfiles-assets` **v0.22.4**, engine
  **v0.1.98**.
- `make deploy-coverage` PASS (assets v0.22.4 mirrored; program tuple agrees;
  seven standalone apps).
- `make gates-ci` PASS (5/5 gates, parity green).
- Composition **v0.2.11** tags this close.
- Live apply: `dotfiles-provision apply` exit 0 — `ok=1163 changed=21 failed=0`; verify exit 0; `dotfiles-runtime doctor` clean (28 items, watch/supervision ok).
- Live links: `~/.config/ags-clipboard` -> `apps/clipboard/v0.7.0`;
  assets `v0.22.4` installed; engine `v0.1.98` installed.
- Composition **v0.2.11** tags this close.
