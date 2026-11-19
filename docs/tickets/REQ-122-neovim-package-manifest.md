---
id: REQ-122
title: "Composition: request the Neovim package"
kind: requirement
status: in-progress
lane: 2 — bounded implementation
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-122/
branch: ticket/REQ-122-neovim-package-manifest
---

# Composition: request the Neovim package

## Why

The composition's `packages.yaml` is the desired logical package set. It has no
Neovim entry, so the engine never installs an editor even though the assets
`configs/nvim` tree is deployed.

## Requirement

1. Add `neovim` to `dotfiles/provisioning/packages.yaml` under a new editor
   comment/section.
2. Do **not** change any pin: `assets.tag`, `installer.pin`,
   `program-tuple.yaml`, `cli-tools.yaml` and `apps.yaml` stay untouched.
3. Do **not** run `make deploy-coverage` as a release gate; it is fine to run
   the existing gates for shape, but the package entry is inert until the
   engine mapping (`dotfiles-provision` `REQ-045`) is released and pinned.

## Dependency / sequencing

- Engine: `dotfiles-provision` `REQ-045` adds `neovim: neovim` to both group_vars
  maps and `nvim` to `verify_system_binaries`.
- Assets: `dotfiles-assets` `req-029` replaces the Neovim config with LazyVim.
- This ticket only adds the composition request. The pin/release sequence
  (assets tag → engine release with asset mirrors → `assets.tag` +
  `installer.pin` bump) is a **shipping** step and is forbidden now.

## Forbidden in this ticket

- No git tag, release, or release-note publication.
- No merge to `master`/`main`; leave the work on the ticket branch.
- No release-metadata change: do not edit `assets.tag`, `installer.pin`,
  `program-tuple.yaml`, `pyproject`/version files, or CHANGELOG release headings.
- No package install, no apply/provision run.
- No touching any `ags-*`, `ags-platform`, or other UI worktree/repo.

## Acceptance

- [x] `dotfiles/provisioning/packages.yaml` contains `neovim` exactly once.
- [x] No pin, tuple, version, or CHANGELOG release metadata changed.
- [x] No tag, release, apply, package install, or UI worktree touched.
- [x] The existing composition shape gates still pass in the worktree.

## Evidence

- Current logical package set has no editor:
  `dotfiles/provisioning/packages.yaml`.
- The engine's group_vars are the install authority:
  `dotfiles-provision/ansible/inventory/group_vars/arch.yml` and
  `debian-family.yml` (no Neovim key today).
- The config copy already exists:
  `dotfiles/provisioning/config-copies.yaml:33-34`.

## Next step

From `dotfiles-v3`:

```bash
bash scripts/worktree-guard.sh create REQ-122 neovim-package-manifest
```

Implement on `ticket/REQ-122-neovim-package-manifest`. Do not bump pins, tag,
release, merge, or apply.


## Notes

Originally filed as `REQ-115`; renumbered to `REQ-118` when
`.worktrees/REQ-115/` was found on the unrelated
`ticket/REQ-115-evolution-secret-service` branch. It was renumbered again to
`REQ-122` when the parallel sound work took `REQ-118`
(`.worktrees/REQ-118-r4/`, `ticket/REQ-118-sound-round4`). Neither existing
worktree was touched. The two follow-up tickets were likewise renumbered to
`REQ-123` (palette projection) and `REQ-124` (skin appearance).

The ticket was filed against a base that pinned assets `v0.20.0` and engine
`v0.1.65`. Those pins were not this ticket's changes and were not edited. The
branch has since been rebased on the current `master`, which pins assets
`v0.21.5` and engine `v0.1.88`; the eventual release will need a new assets tag
and a new engine tag after the Neovim package map and the LazyVim config land.


## Release evidence

- `dotfiles-assets v0.21.6` released (LazyVim nvim config + committed
  `lazy-lock.json`).
- `dotfiles-provision v0.1.89` released (neovim package mapping, `nvim` PATH
  verify, assets `v0.21.6` mirrors).
- `assets.tag` and `program-tuple.yaml` pin `v0.21.6`; `installer.pin` pins
  `v0.1.89`.
- `make deploy-coverage` PASS (engine v0.1.89, assets v0.21.6, platform v1.2.0).
- `make gates-ci` PASS (deploy-coverage, GloView ABI tests,
  ansible-embedded-template-lint, per-app drift, CI parity).
- No host apply/install was run.
