---
id: REQ-133
title: "Pin ags-icme v0.6.0 (edit-target dropdown)"
kind: requirement
status: done
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-133/
branch: ticket/REQ-133-icme-v060
---

# Pin ags-icme v0.6.0

1. Pin the released ags-icme v0.6.0 in `apps.yaml` and `FINAL_APP_RELEASES`.
2. deploy-coverage and gates-ci pass.
3. Release v0.2.6.
4. Deploy the v0.2.6 tag into the spine and verify it.

## Evidence

Closed 2026-11-19.

- Pin commit `ad07f1ea` (`chore(REQ-133): pin ags-icme v0.6.0`):
  `dotfiles/provisioning/apps.yaml` `tag: v0.5.2` -> `v0.6.0`, and
  `scripts/ags_app_consumption.py` `FINAL_APP_RELEASES["icme"]` ->
  `v0.6.0`.
- deploy-coverage and gates-ci **passed** on that commit.
- Provision/apply installed ags-icme `v0.6.0` into the spine:
  `~/.local/share/dotfiles/apps/icme/pinned` contains `v0.6.0`, and the
  spine links resolve to `apps/icme/v0.6.0`.
- `dotfiles-provision verify --expected-engine-tag v0.1.95` — **exit 0**:
  `ok=343 changed=2 unreachable=0 failed=0 skipped=46`.
- `dotfiles-runtime doctor` — **exit 0**: desktop clean (28 items), watch
  health ok, palette v1 conforming, supervision ok.
- The editor runs live; `ags list` includes `icon-color-mapping-editor`.
- Note on the deploy run: apply's own final summary was not captured because
  the 900s harness cutoff ended the run while it was already in the trailing
  verify role. Apply printed no final summary; the standalone verify above is
  authoritative and passed.
- Release: composition `v0.2.6` is tagged on the commit that closes this
  ticket (`v0.2.6: pin ags-icme v0.6.0 (edit-target dropdown)`).
- GitHub Release **published** (not just the tag) for the existing tag
  `v0.2.6` — title `v0.2.6 — ags-icme v0.6.0 edit-target dropdown`:
  https://github.com/RandomGenericUsername/dotfiles-v3/releases/tag/v0.2.6
  Created with `gh release create --verify-tag`, not draft/prerelease, no
  assets. Tag `v0.2.6` still points at `802c2236` and was not moved.

## Status

Done. ags-icme `v0.6.0` is pinned, deployed and verified; composition
`v0.2.6` released.
