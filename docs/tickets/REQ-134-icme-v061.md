---
id: REQ-134
title: "Pin ags-icme v0.6.1 (dev-pin parity)"
kind: requirement
status: in-progress
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

Opened 2026-11-19.

- ags-icme `v0.6.1` released upstream; tag peels to `88a4892` and is pushed
  to the app origin. This is the dev-pin parity release.
- Pin: `dotfiles/provisioning/apps.yaml` `tag: v0.6.0` -> `v0.6.1`, and
  `scripts/ags_app_consumption.py` `FINAL_APP_RELEASES["icme"]` ->
  `v0.6.1`.
- deploy-coverage and gates-ci **passed** on the pin commit.

## Status

In progress. Stage B pins and deploys ags-icme `v0.6.1`; Stage C closes this
ticket and releases composition `v0.2.7`.
