# Story 1.3: Read-Only `--check-inputs` Stale Report

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 1 — Invalidation-Aware Regeneration (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 1.3)

## Story

As a user,
I want `reconcile --check-inputs` (read-only) to report stale layers without mutating anything,
so that editing a csg template surfaces exactly palette (+icons cascade) as stale before I commit to regeneration.

## Acceptance Criteria

1. `dotfiles-runtime reconcile --check-inputs` reports stale layers with cascade (edited csg template → palette stale + icons via cascade; effects fresh; wallpapers out of scope — content-addressed per Story 1.2, freshness structural) and performs zero mutations — no cache writes, no symlink repoints, no JSON/history writes, no seeding (AC 1, FR-1)
2. On a warm cache it completes with zero csg/weg/itr invocations (hash walk only) (AC 2, NFR-4)
3. Absent state (no `current.json`) exits non-zero with a clear message (never seeds behind a read command) (AC 3)
4. Exit 0 with the report whether stale layers exist or not — staleness is information, not failure (non-zero-on-drift belongs to doctor Story 2.1) (AC 4)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/application/check_inputs.py` (AC: 1, 2)
  - [x] Frozen dataclass `CheckInputsResult(stale: frozenset[str], fresh: frozenset[str])` (layer names as plain strings; CLI serializes to sorted lists)
  - [x] Class `CheckInputsUseCase(state_repo, invalidation, recorded_inputs)` with `run() -> CheckInputsResult` — three read-only collaborators (repository + port + bound reader method from the same adapter instance); no writers, no locks, no derivation adapters
  - [x] `run()`: `load_current()` → `None` raises `ValueError` (absent state, AC 3); else for each active derived entry (palette/effects/icons non-`None` in `current.json`) call `invalidation.recorded_inputs(layer, entry_hash)`; then `invalidation.recompute_input_hashes()`; then `invalidation.compare_against_meta(recorded, recomputed)` → stale; fresh = `{palettes, effects, icons} - stale`
  - [x] Layers absent from `current.json` are simply omitted from `recorded` (missing side → stale per p3-1-1 semantics: derivable-but-uncached is truthfully stale; 1.4's regen covers the miss path via the Phase-2 cache-ensure)
  - [x] Structural read-only guarantee: ctor takes NO seeder, NO mutex, NO derivation adapters, NO reloaders — only `IStateRepository` (read) + `IInvalidationQuery` (read) + the adapter's bound `recorded_inputs` reader (read). The type signature IS the guarantee
- [x] Wire `reconcile --check-inputs` in `src/runtime/src/runtime/cli/main.py` (AC: 1, 3, 4)
  - [x] Add `check_inputs: bool = typer.Option(False, "--check-inputs", help=...)` to the existing `reconcile` command (flag, not a new command — doctor owns its own command in Epic 2)
  - [x] New composition helper `_run_check_inputs()` mirroring `_run_inspect_status` wiring: resolve `state_root`/`install_spine` (absolute), build `JsonStateRepository`, resolve the four spine paths via `derive.find_templates_dir / find_effects_catalog / find_icon_templates / find_icon_mappings` (the 1.2 pinned seam: composition owns discovery), build `InvalidationQueryAdapter`, inject both into `CheckInputsUseCase`
  - [x] Render via `cli-output` `CustomView` (plain summary + machine-readable object `{stale: [...], fresh: [...]}`, sorted lists); exit 0 on report; `ValueError` (absent state) → `ErrorView` + exit 1, mirroring `inspect status`
  - [x] Confirm the existing `main_callback` seed guard (`"reconcile" in sys.argv` → skip seed) covers the flag path — no new seed-guard code; pin with a test
- [x] Create `src/runtime/tests/unit/test_cli_check_inputs.py` (AC: 1, 2, 3, 4)
  - [x] Mirror `test_cli_inspect_status.py` patterns: `CliRunner`, monkeypatched `_run_check_inputs` for CLI shape (exit 0, plain summary, `--format json` object shape), absent-state exit 1
  - [x] Real end-to-end (no monkeypatch): tmp `XDG_STATE_HOME` + `DOTFILES_INSTALL_SPINE` with warm seeded entries; edit a template file; run `reconcile --check-inputs`; assert palette+icons stale, effects+wallpaper fresh
  - [x] Zero-mutation pin: snapshot `state_root` (file list + content hashes) before/after the command; assert byte-identical (no cache writes, no JSON/history writes, no repoints)
  - [x] Zero-tool pin: wiring contains no csg/weg/itr adapters (structural — assert by construction in the composition helper; plus the FS snapshot proves no generator output landed)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_cli_check_inputs.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — this story is the READ-ONLY REPORT ONLY

Story 1.3 surfaces staleness. It does **NOT** implement:
- Selective regeneration + cascade reconverge (Story 1.4 — consumes this report)
- Digest enforcement at populate (Story 1.5)
- `doctor` three-way check / non-zero-on-drift (Stories 2.1/2.2)
- Any cache mutation, symlink repoint, history append, or reload

### Layering (AD-25, locked)

- New use case in `application/`; may import `ports`, `domain`; must not import `adapters` (receives the port by injection) nor `cli`
- CLI change is composition-root only (wiring + rendering), mirroring `_run_inspect_status`
- Discovery (`derive.find_*`) is same-layer (`application/` → `application/`) when used by the use case, or composition-root when used by CLI — either satisfies the 1.2 seam; prefer CLI-side resolution to keep the use case to two collaborators (`state_repo` + `invalidation`)
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. Icons `\x00`-join encoding, wallpapers exclusion, missing→`None`, corrupt→`ValueError` (Story 1.2).
2. Stale-vs-corrupt boundary: this report NEVER classifies artifact corruption (Story 1.5/2.x own it).
3. Exit 0 on report; absent state exits 1 without seeding.

## Review Record (Gate 2, 2026-09-10)

Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
18 findings (several overlapping). Operator verdicts per-item ballot: apply A–L, dismiss X1–X3.

Applied:
- A: fake recomputed map is full 3-key (no spurious staleness).
- B: missing-layer test asserts exact stale==all-three, fresh==empty.
- C: use case raises `ValueError` on stale layers outside `REPORT_LAYERS`.
- D: snapshot v2 records symlinks (targets), dirs, modes, mtimes, hashes.
- E: seed guard matches the command positionally, flag-aware (pre-existing `main_callback` touch, minimal).
- F: absent-state asserts hardened (no `.seed.lock`, no tmp files).
- G: stderr-robust error assertion.
- H: all-entries-None state tested; `none` rendering pinned.
- I: AC1/task reworded — wallpapers out of scope (content-addressed, 1.2).
- J: structural no-derivation-adapters getsource test.
- K: three-collaborator wording + same-instance docstring line.
- L: boxes checked; this record.

Dismissed:
- X1 recorded_inputs onto the port — reworks DONE p3-1-1 (breaks its fake); divergence impossible in real wiring (same instance); covered by K doc line.
- X2 CLI-side derive-or-raise — redundant given C; CLI stays dumb.
- X3 exit code 2 on stale — contradicts approved AC4; doctor 2.1 owns drift codes.
