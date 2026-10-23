## Why

Host-side Incus/QEMU dev harness lives at `scripts/dev/vmtest/` forcing `scripts/dev/vmtest/vm` and `../../..` repo-root traversal. Moving it to top-level `dev/` with `./dev/vm` as entry makes the inner-loop (`fresh`, `up`, `shell`, `status`) discoverable and shortens every doc/runbook reference.

## What Changes

- Move `scripts/dev/vmtest/*` (vm, vm-fresh.sh, vm-continue.sh, run-vm.sh, provision-in-vm.sh, install.sh, README.md) to `dev/` verbatim except path fixes.
- Update `REPO_ROOT` traversal in `run-vm.sh` / `vm-fresh.sh` from `../../..` to `..` (one level: `dev/` -> repo root).
- Retarget all `Makefile` `vm-*` targets from `scripts/dev/vmtest/vm` to `dev/vm`.
- Update `.gitignore` dev artifact path from `/scripts/dev/vmtest/.images/` to `/dev/.images/`.
- No behavior change to Incus provisioning, QEMU flags, or VM image handling.

## Capabilities

### New Capabilities

- `dev-vm-harness`: location, entry-point, and path contracts for the developer VM harness under `dev/`.

### Modified Capabilities

*(None — pure relocate, no spec-level behavior change to provisioning or runtime.)*

## Impact

- Codebase paths: `dev/` created; `scripts/dev/` removed (rest of `scripts/` untouched by this change).
- Build/tooling: `Makefile`, `.gitignore` only.
- Docs/runbooks referencing `scripts/dev/vmtest/vm` must use `./dev/vm`.
- No Ansible, AGS, or provisioning role changes.
