# Tasks

## 1. Extend `ags-typecheck` coverage

- [x] 1.1 Widen `WATCHED_PREFIX` to the platform surfaces (`kit/`, `lib/`, `domains/`, `bar/`). Verify: a deliberate type error in a non-audio bar file fails `make ags-typecheck` (negative test).
  - `scripts/ags-typecheck.py`: replaced the single `WATCHED_PREFIX = "…/audio/"` with `BAR_ROOT = "dotfiles/config/ags/"` and `BAR_TESTS = "dotfiles/config/ags/tests/"`; the gate now fails on any error under the bar tree except `tests/`. Watching the whole tree (not an enumerated `kit/lib/domains/bar` list) covers "the other non-audio bar code" and cannot rot as directories are added. It intentionally overlaps `bar-typecheck` — AD-19 requires both.
  - Negative test: appended `const __deliberate_negative_test: number = "not a number"` to `dotfiles/config/ags/kit/icon.ts` (non-audio) → `make ags-typecheck` failed, naming `dotfiles/config/ags/kit/icon.ts(48,7): error TS2322: Type 'string' is not assignable to type 'number'.` (make exit 2). Reverted (`git checkout -- dotfiles/config/ags/kit/icon.ts`).
- [x] 1.2 Resolve the newly-watched errors (fix, or baseline with a stated reason — never a silent allowlist). Verify: `make ags-typecheck` → exit 0.
  - `make ags-typecheck` → exit 0: `PASS (with GIR typings, 0 errors in the extracted bar tree (dotfiles/config/ags/*, excluding dotfiles/config/ags/tests/), 29 third-party, 12 in tests/, 0 exempt)`.
  - No newly-watched errors existed: the bar tree outside `tests/` was already clean, so nothing had to be fixed or baselined. The 12 remaining errors are all `dotfiles/config/ags/tests/ts/*.test.ts` `Cannot find module 'node:test'` (TS2307) — a separate tsc project owned by `make ags-test`, excluded by TREE (`BAR_TESTS`), not by a filename allowlist.
  - Removed the dead numeric baseline (`PRE_EXISTING_BASELINE`) and the unused `--baseline` flag so no one can raise a baseline to hide a regression.

## 2. Run the typechecks in CI

- [x] 2.1 Add a `bar-typecheck` CI job on the self-hosted runner. Verify: `make ci-gates-parity` → exit 0 (workflow job set equals `gates-ci`).
  - `.github/workflows/gates.yml`: added a `bar-typecheck` job on `runs-on: [self-hosted, linux]`, mirroring `ags-typecheck`; updated the header/comment that said bar-typecheck had no job.
  - `scripts/ci-gates-parity.py`: moved `bar-typecheck` from `CI_EXCLUDED_GATES` (no job) to `CI_SELF_HOSTED_GATES` (filtered from the stock `gates-ci`, but runs on the self-hosted runner).
  - `make ci-gates-parity` → exit 0: `declared self-hosted gates (2): ags-typecheck->ags-typecheck, bar-typecheck->bar-typecheck`; `PASS`.
  - `make bar-typecheck` → exit 0 locally (`OK: 0 errors in dotfiles/config/ags`, 29 tolerated third-party), confirming the new job's gate passes on a provisioned host.
- [x] 2.2 Confirm `ags-typecheck` still runs in CI (self-hosted job). Verify: the job exists in `gates.yml`.
  - `ags-typecheck` job present in `.github/workflows/gates.yml` (`runs-on: [self-hosted, linux]`); `ci-gates-parity` lists it in the workflow job set. Its comment now states it covers the extracted surface (AD-19).

## 3. Wire the per-app suites

- [x] 3.1 Add a root gate target running the per-app drift/symbol suites (`event-contract-drift.mjs`, `ags-symbol-check.mjs`). Verify: the target runs them; a deliberate drift fails it.
  - `Makefile`: added `per-app-drift-symbol-suites` (runs hypr-pano drift, ICME drift, ICME `ags-symbol-check`, wallpaper-selector drift) and added it to `GATES`, so it runs from `make gates` AND `make gates-ci`; added a CI job in `gates.yml` on `ubuntu-latest` (pure Node, no desktop stack).
  - `make per-app-drift-symbol-suites` → exit 0; each of the 4 suites reports green.
  - Deliberate drift: changed `contracts/event-contract.json` `well_known_name` to `org.example.DeliberateDrift` → `make per-app-drift-symbol-suites` exit 2 (`FAIL bus name`). Reverted.
  - The suites were RED on master (pre-existing, discovered here) because they ran nowhere. Fixed so the new gate is honest:
    - `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`: the `speedtest.state` payload assertion was stale — the contract additively gained `ssid`/`server_name`; updated the pinned key set to match the authoritative contract (AD-6).
    - `src/gui-tools/icon-color-mapping-editor/tests/ags-symbol-check.mjs`: fixed false positives (interface/type method signatures `name(...):`, generic function params `function f<T>(...)`, paren-bearing param defaults, `readonly` keyword) and made the walk skip `node_modules` (it reported 321 bogus errors when `@types/node` was installed). Negative test: a deliberate `totallyUndefinedFn(1)` still fails (`1 PROBLEM(S)`, exit 1). Direction (1) untouched.

## 4. Verify

- [x] 4.1 `make gates-ci` and `make ci-gates-parity` → green.
  - `make gates-ci` → exit 0 (all 21 stock-runner gates, including the new `per-app-drift-symbol-suites`).
  - `make ci-gates-parity` → exit 0 (`PASS`).
  - `git status --porcelain` → only the intended tracked edits; all generated artifacts are gitignored.
