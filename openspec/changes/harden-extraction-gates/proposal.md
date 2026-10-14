# harden-extraction-gates

## Why

The platform extraction (spine **AD-20**) is the riskiest step, and the gates cannot catch a bad extraction: `bar-typecheck`/`ags-typecheck`/`capture-typecheck` are excluded from `gates-ci`; `ags-typecheck` only fails under `dotfiles/config/ags/audio/` (`WATCHED_PREFIX`), so errors in `kit/`, `lib/`, `domains/`, `bar/` pass silently; `bar-typecheck` has no CI job at all; and the per-app drift/symbol suites run only via each app's own Makefile.

Evidence: `Makefile:76` (`gates-ci: $(filter-out capture-typecheck bar-typecheck ags-typecheck,...)`), `scripts/ags-typecheck.py:91` (`WATCHED_PREFIX = "dotfiles/config/ags/audio/"`), `.github/workflows/gates.yml` (no `bar-typecheck` job; `ags-typecheck` self-hosted only).
Verify: `make -n gates-ci | grep -E 'bar-typecheck|ags-typecheck'` → none.

## What Changes

- **Extend `ags-typecheck`'s watched surface** beyond `audio/` to the platform surfaces being extracted (`kit/`, `lib/`, `domains/`, `bar/`), fixing or deliberately baselining the pre-existing errors.
- **Run the typechecks in CI**: add a `bar-typecheck` job on the self-hosted runner (like `ags-typecheck`), so both run on a provisioned host.
- **Wire the per-app drift/symbol suites** (`event-contract-drift.mjs`, `ags-symbol-check.mjs`) into the root gate.
- Keep `ci-gates-parity` green (the workflow job set must equal `gates-ci`).

## Non-goals

- Not the extraction itself (spine AD-20).
- **Not weakening any gate** to make it pass — errors are fixed or baselined with a stated reason.

## Impact

- `Makefile`, `scripts/ags-typecheck.py`, `.github/workflows/gates.yml`, per-app test wiring.
