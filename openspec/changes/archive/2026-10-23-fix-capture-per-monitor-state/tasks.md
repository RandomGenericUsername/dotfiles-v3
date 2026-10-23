## 0. Anti-drift preamble (read before editing)

- Files in scope: `src/gui-tools/capture-tool/domain/ui-state.ts`,
  `src/gui-tools/capture-tool/ui/classic/ClassicWindow.tsx`,
  `src/gui-tools/capture-tool/app.tsx`,
  `src/gui-tools/capture-tool/tests/ts/ui-state-ownership.test.ts` (new).
- NO new file outside `tests/` → gate check 5 (per-file registration in
  `gui_tools_app_files`) is untouched and `src/provisioning/**` is NOT edited. A new
  module under `domain/` or `ui/` would have required editing
  `gui_tools/vars/main.yml`; `createUiState()` therefore lives in the already-registered
  `domain/ui-state.ts`, beside the constants it seeds.
- Invariants that hold: state is MUTATED IN PLACE and never rebound (the three pages
  hold the exact objects they were given); persistence path, JSON shape and the
  missing-is-silent / corrupt-is-loud degradation unchanged; the three-tier precedence
  rule unchanged; the class vocabulary unchanged (gate check 6 stays 33 used / 28 styled);
  save still happens only at the two capture call sites.
- Do NOT touch `src/provisioning/**` (4 known pre-existing failures there: 4 failed /
  661 passed is the baseline).
- If a step forces a file outside this list, STOP and report.

## 1. Reproduce before fixing (done, evidence in proposal.md + design.md)

- [x] 1.1 Established that this host has ONE monitor, so a live two-monitor
      reproduction is impossible; recorded that plainly rather than claiming one.
- [x] 1.2 Built the two-window instance headlessly against the REAL
      `glibUiStateStore` (`repro/two-window-harness.tsx`, two `Astal.Window`s, real
      `ClassicWindow`, stubbed launcher/backend-probe ports only).
- [x] 1.3 Executed the pre-fix clobber: A saves `screen`, B saves `window`, A saves
      `screen` again — the persisted value flaps and each capture discards the other
      window's explicit choice.
- [x] 1.4 Measured reachability: `ags toggle capture-window` resolves to the LAST-added
      window every time, so the pre-fix defect is a latent second writer, not a live
      keybind bug. Recorded, not used as an excuse.
- [x] 1.5 Answered the four investigation questions: divergence is real (independent
      objects, not a shared-identity illusion); the symptom is a lost AND wrong setting
      depending on which window captures, on save, and it also leaves the visible
      highlight disagreeing with disk; `Object.assign` is the mitigation for the rebind
      hazard, not for this bug; ONE monitor cannot exhibit it at all.

## 2. The fix

- [x] 2.1 `domain/ui-state.ts`: `createUiState(): UiState` — fresh copies of
      `DEFAULT_SCREENSHOT` / `DEFAULT_RECORDING`, documented as cardinality-1 state with
      the "fresh objects" and "not a memoised singleton" properties spelled out.
- [x] 2.2 `ClassicWindow.tsx`: third REQUIRED parameter `state: UiState`; the two
      per-window allocations deleted; `const { screenshot, recording } = state`. The
      in-place/no-rebind comment kept and extended with why the state is injected.
- [x] 2.3 `app.tsx`: `const state = createUiState()` BEFORE the monitor loop, passed to
      every `ClassicWindow(monitor, ports, state)`.
- [x] 2.4 No other call site of `ClassicWindow` exists; the unused
      `DEFAULT_SCREENSHOT` / `DEFAULT_RECORDING` / `ScreenshotUiState` /
      `RecordingUiState` imports removed from `ClassicWindow.tsx`.

## 3. Tests

- [x] 3.1 `tests/ts/ui-state-ownership.test.ts`: the factory's semantics — seeds the
      defaults, hands out objects that are NOT the constants (mutating a state cannot
      corrupt the first-run defaults), and is a factory rather than a singleton.
- [x] 3.2 The invariant on identity: two windows given one state mutate one object; the
      second save cannot resurrect a stale value.
- [x] 3.3 The negative control: the per-window shape modelled in the same file DOES
      diverge and DOES lose the other window's selection — the bug is executable in the
      suite, not merely described.
- [x] 3.4 The wiring guard, comment-stripped: `ClassicWindow.tsx` allocates no state
      and declares `state: UiState`; `app.tsx` calls `createUiState()` exactly once,
      outside the monitor loop, and passes it at the only `ClassicWindow` call site.
- [x] 3.5 `applyStateToUi()`'s reload asserted to `Object.assign` INTO the shared object
      (identity preserved), so the no-rebind invariant is pinned too.
- [x] 3.6 Stated in the file header what the suite does NOT prove: a GTK-requiring
      window cannot be constructed under `node --test`, so (3.4) is a source-shape guard
      and the end-to-end proof is the harness.

## 4. Gates

- [x] 4.1 `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 still
      `33 used / 28 styled`, check 5 still 24 registered files (no new deployed file).
- [x] 4.2 `make capture-typecheck` → `OK: 0 errors in src/gui-tools/capture-tool`.
- [x] 4.3 `make capture-test` → 93/93 (85 pre-existing + 8 new), and
      `tsc --noEmit -p tests/tsconfig.tests.json` → 0 type errors.
- [x] 4.4 `cd src/gui-tools/capture-tool && uv run --with pytest python -m pytest
      tests/ -q` → 97 passed.
- [x] 4.5 `uv run --directory src/provisioning pytest tests/unit -q` → still exactly 4
      failed (`test_packages_manifest_has_verified_set`,
      `test_arch_packages_cover_exactly_logical_set`,
      `test_debian_family_packages_cover_exactly_logical_set`,
      `test_settings_parse_gate_tasks_exist_and_are_check_gated`), passed count
      unchanged at 661. Identical to the baseline: `tests/` is not a deployed path, so
      the new test file is invisible to provisioning.

## 5. Verification of the fix itself

- [x] 5.1 Re-ran the IDENTICAL harness against the fixed tree: A's capture now emits
      `--target window` (the shared truth) and the persisted value no longer flips.
- [x] 5.2 Recorded the one honest limitation: with two windows mapped at once the
      unfocused window's CSS highlight can lag the shared state until its next `map`.
      Capture output and persistence are correct either way, which is the invariant that
      matters.
- [x] 5.3 Left the duplicate window name (`hideCaptureWindow` / `syncWindowSize`
      resolving to one window) untouched and recorded it as a separate defect: renaming
      windows is a behaviour change and belongs in its own change.

## 6. Close-out

- [x] 6.1 `git diff --stat` touches only the four in-scope files plus the change
      directory.
- [x] 6.2 Nothing committed (worktree state only, per the task's instruction).

## 7. Pre-existing toolchain conflict found on the way (NOT fixed here)

`make capture-test`'s optional test-file typecheck
(`tsc -p tests/tsconfig.tests.json`, which sets `"types": ["node"]`) and
`make capture-typecheck` cannot both be satisfied from the repo-root `node_modules`:

- Without `@types/node`: the tests config fails `TS2688: Cannot find type definition
  file for 'node'`. Reproduced at HEAD **with this change's files removed** — i.e. it is
  pre-existing, and it only shows up once `make capture-typecheck` has installed
  `typescript` (on a pristine clone the step prints `NOTE: typescript not installed,
  skipping` and the target passes).
- With `@types/node` at the repo root: `tsconfig.capture.json` sets no `"types"`, so
  every `@types/*` package is auto-included and the gnim JSX types widen — 96 errors in
  files this change never touches (`Type 'Box | Object' is not assignable to type
  'Box'`). Also reproduced at HEAD with this change's files removed.

Both gates are green simultaneously here because `@types/node` is installed under
`src/gui-tools/capture-tool/tests/node_modules/` instead: the tests config resolves it by
walking up from `tests/`, while the app config's `typeRoots` walk starts at the capture
tool directory and never descends into `tests/`. That directory is an UNTRACKED local
toolchain artefact and **must not be committed**; `.gitignore` covers
`/src/gui-tools/capture-tool/node_modules/` but not the `tests/` one, and adding a rule
would be an unrelated repo change. Deleting it returns `make capture-test` to the
`NOTE: … skipping` behaviour, which also passes.

No Makefile, tsconfig or gate was modified to accommodate this.

