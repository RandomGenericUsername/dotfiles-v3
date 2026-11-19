---
id: REQ-134
title: "Pin ags-icme v0.6.1 (dev-pin parity)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-134/
branch: ticket/REQ-134-icme-v061
---

# Pin ags-icme v0.6.1

1. Pin the released ags-icme v0.6.1 in `apps.yaml` and `FINAL_APP_RELEASES`.
2. deploy-coverage and gates-ci pass.
3. Release v0.2.7.
4. Deploy the v0.2.7 tag into the spine and verify it.

## Evidence

Closed 2026-11-19.

- ags-icme `v0.6.1` released upstream; tag peels to `88a4892` and is pushed
  to the app origin. This is the dev-pin parity release (ags-platform v1.2.0
  dev-pin parity; contracts stays v0.12.0).
- Pin commit `7c3ce472` (`chore(REQ-134): pin ags-icme v0.6.1`):
  `dotfiles/provisioning/apps.yaml` `tag: v0.6.0` -> `v0.6.1`, and
  `scripts/ags_app_consumption.py` `FINAL_APP_RELEASES["icme"]` ->
  `v0.6.1`.
- deploy-coverage and gates-ci **passed** on that pin commit.
- Provision/apply installed ags-icme `v0.6.1` into the spine:
  `~/.local/share/dotfiles/apps/icme/pinned` contains `v0.6.1`, and the
  spine links resolve to `apps/icme/v0.6.1`.
- Apply recap: `ok=1164 changed=25 unreachable=0 failed=0 skipped=509`.
- `dotfiles-provision verify --expected-engine-tag v0.1.95` — **exit 0**:
  `ok=343 changed=2 failed=0 skipped=46`.
- `dotfiles-runtime doctor` — **clean** (exit 0).
- The editor runs live; `ags list` includes `icon-color-mapping-editor`.
- Release: composition `v0.2.7` is tagged on this close commit
  (`v0.2.7: ags-icme v0.6.1 (dev-pin parity)`).

## Status

Done. ags-icme `v0.6.1` is pinned, deployed and verified; composition
`v0.2.7` released.
