# Tasks

## 1. Extend `ags-typecheck` coverage

- [ ] 1.1 Widen `WATCHED_PREFIX` to the platform surfaces (`kit/`, `lib/`, `domains/`, `bar/`). Verify: a deliberate type error in a non-audio bar file fails `make ags-typecheck` (negative test).
- [ ] 1.2 Resolve the newly-watched errors (fix, or baseline with a stated reason — never a silent allowlist). Verify: `make ags-typecheck` → exit 0.

## 2. Run the typechecks in CI

- [ ] 2.1 Add a `bar-typecheck` CI job on the self-hosted runner. Verify: `make ci-gates-parity` → exit 0 (workflow job set equals `gates-ci`).
- [ ] 2.2 Confirm `ags-typecheck` still runs in CI (self-hosted job). Verify: the job exists in `gates.yml`.

## 3. Wire the per-app suites

- [ ] 3.1 Add a root gate target running the per-app drift/symbol suites (`event-contract-drift.mjs`, `ags-symbol-check.mjs`). Verify: the target runs them; a deliberate drift fails it.

## 4. Verify

- [ ] 4.1 `make gates-ci` and `make ci-gates-parity` → green.
