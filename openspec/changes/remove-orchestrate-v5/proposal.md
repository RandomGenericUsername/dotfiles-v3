## Why

`scripts/orchestrate-v5.sh` is a completed July-2026 migration coordinator with zero references from `Makefile`, `bootstrap.sh`, Ansible, or tests. Deleting it (separately, after the three relocates) is the last step before `scripts/` itself can be removed.

## What Changes

- Delete `scripts/orchestrate-v5.sh` after grep-proof that nothing references it.
- Remove `scripts/` only when empty (follow-up commit, not this one).

## Capabilities

### New Capabilities

*(None — pure deletion.)*

### Modified Capabilities

*(None.)*

## Impact

- One file deleted. No provisioning, AGS, or harness impact. Verify with repo-wide grep + unit suite.
