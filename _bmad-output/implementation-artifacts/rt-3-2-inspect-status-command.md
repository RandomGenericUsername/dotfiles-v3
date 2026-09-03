---
baseline_commit: 64e4a8000c40be7a54849c4f91efcf26309fa806
---

# Story rt-3.2: inspect status command

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to see the current desktop state,
So that I know what wallpaper/palette/effects/icons are active.

## Scope Reality (READ FIRST)

**This is a GREENFIELD story, unlike rt-3.1.** `InspectStateUseCase` exists ONLY as a name in
the architecture spine (`ARCHITECTURE-SPINE.md` line 27 lists it in `runtime.application`); there
is NO `application/inspect.py`, NO `cli/inspect.py`, NO `inspect` typer group, and NO inspection
code anywhere in `src/runtime` (verified by grep — zero matches for inspect/Inspect beyond docs).
Story 3.2 builds the FIRST Epic-3 inspection command: `dotfiles-runtime inspect status`.

**Scope boundary — do NOT build the other Epic-3 commands.** Story 3.3 (`inspect history`) adds
the history reader; Story 3.4 (`inspect cache list`) adds cache listing. Those land in later
stories. This story touches ONLY the status path: `InspectStateUseCase` (status projection +
live `current/` symlink reflection), the `inspect status` CLI surface, tests, and the shared
auto-seed guard change (below).

## Acceptance Criteria

1. **Status output** — Given `dotfiles-runtime inspect status` runs on a machine with recorded
   state, Then it prints the current wallpaper, palette, effects, and icons **derived from
   `current.json` + the `current/` symlink targets** (FR-7, CAP-7).
2. **Filesystem authority reflected** — The output reflects the **live `current/` symlink**
   (NFR-3: filesystem is the authority), not just the `current.json` index: for each expected
   consumer symlink (`wallpaper-<monitor>.png`, `colors.yaml`, `colors.conf`, `colors.gtk.css`,
   `effects/`, `icons/`) it reports the actual symlink target and flags
   `ok` | `missing` | `diverged` vs the index.
3. **Absent state is loud** — Given `current.json` is absent (never seeded / missing), When
   `dotfiles-runtime inspect status` runs, Then it exits NON-ZERO with a clear message (e.g.
   "no state recorded — run `dotfiles-provision apply` / `dotfiles-runtime wallpaper set <img>`
   to seed"). No fabricated/empty state, no exit-0.
4. **Read-only + format parity** — The command MUTATES NOTHING: no cache population, no `current/`
   repoint, no `history.jsonl` append, no seed side-effects. Supports `--format plain|json|rich`
   (`OutputFormat`) like every other command; JSON object is structured and deterministic.
5. **Zero regressions** — full suite passes (`pytest`, `ruff check src`, `ruff format --check src`,
   `mypy --strict src`, layering tests) with ZERO new violations; existing seeding/apply/reconcile
   behavior unchanged (the auto-seed guard change must not seed for non-inspect commands).

## Tasks / Subtasks

- [x] Task 1: `InspectStateUseCase` (AC: 1, 2, 3)
  - [x] New `src/runtime/src/runtime/application/inspect.py`: frozen `InspectStatusResult` +
    `InspectStateUseCase(state_repo: IStateRepository, state_root: Path)`
  - [x] `run() -> InspectStatusResult`: `state_repo.load_current()` → `None` raises
    `RuntimeError` with the absent-state message (AC 3); otherwise project wallpaper /
    monitors / palette / effects / icons from `DesktopState`
  - [x] Read live `current/` symlink targets under `state_root / "current"` and compare each
    expected name against `resolve()` (read-only; mirror `reconcile._build_expected_targets`
    name set) → per-name `ok|missing|diverged` (AC 2)
- [x] Task 2: CLI `inspect status` (AC: 1, 4)
  - [x] `inspect_app = typer.Typer(...)` + `app.add_typer(inspect_app, name="inspect")` in
    `cli/main.py` (precedent: `wallpaper_app` at main.py:35-36); command `status`
    (class-name `inspect_status`)
  - [x] `_run_inspect_status()` composition helper mirroring `_run_reconcile` (main.py:384-417):
    `_resolve_state_root()` + `JsonStateRepository(state_root)` injected into the use case
  - [x] Error mapping: `ValueError`/`RuntimeError`/`OSError` → `ErrorView` + `typer.Exit(1)`
    (mirror main.py:311-323 / 438-450); absent state → logger.error + `ErrorView` + exit 1
  - [x] Render success via `CustomView(plain=..., object={...}, rich=...)`; JSON object carries
    wallpaper/monitors/palette/effects/icons hashes + live symlink statuses
  - [x] **Auto-seed guard:** extend `main_callback` (main.py:164-176) so `inspect` NEVER
    auto-seeds — `if "reconcile" in sys.argv or "inspect" in sys.argv: return` (precedent:
    the "reconcile" skip; AC 3 requires the absent-state error to be reachable)
- [x] Task 3: Tests (AC: 1-5)
  - [x] `tests/unit/test_inspect.py`: use-case level — happy path projects all layers; absent
    state raises; per-monitor + palette + effects + icons reflected; live symlink
    `ok`/`missing`/`diverged` (create real symlinks under `tmp_path`); result is read-only
    (no `current/` mutations, no history file created)
  - [x] `tests/unit/test_cli_inspect_status.py`: mirrors `test_cli_reconcile.py` — exit codes,
    plain summary text, `--format json` object shape, absent-state → exit 1 + `ErrorView`
    (monkeypatch the composition helper, not the whole app)
  - [x] `tests/integration/test_inspect_integration.py`: real `JsonStateRepository` + real
    `current/` symlinks on `tmp_path` `state_root` (seed-style `_make_state` builder with
    `"a"*64`-style hashes); assert output + divergence when a symlink is repointed away
  - [x] Guard tests: `inspect`/`reconcile` skip auto-seed; other commands still seed
    (extend existing seed-hook CLI tests if the guard change requires it)
- [x] Task 4: Quality gates (AC: 5)
  - [x] `uv run --directory src/runtime pytest`
  - [x] `uv run --directory src/runtime ruff check src` — zero NEW (baseline: exactly 3 —
    cli/main.py:166, cli/main.py:271, domain/models.py:35). Do NOT run bare `ruff check`
  - [x] `uv run --directory src/runtime ruff format --check src` — clean (src scope; unscoped
    run reports pre-existing test-file violations, do not count them)
  - [x] `uv run --directory src/runtime mypy --strict src` — zero NEW (baseline: exactly 4).
    Bare `mypy --strict` errors out ("Missing target module")
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v`
  - [x] Confirm `git status --short` contains ONLY this story's new files + the story/status
    artifacts (`main.py`, `application/inspect.py`, 3 test files, `sprint-status.yaml`, this
    story file)

## Dev Notes

### Pinned sources (cite in References)

- PRD/epic: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 3
  (line 93-98), **Story 3.2 ACs verbatim** (lines 451-462), FR-7, CAP-7, NFR-3, R1 note (line 102).
- Architecture: `ARCHITECTURE-SPINE.md` — application layer list line 27 (`InspectStateUseCase`),
  `cli` spine line 28 (`wallpaper/status/history/cache commands`), AD-20 (`dotfiles-runtime
  {wallpaper,status,history,cache,...}`) line 152, AD-3/NFR-3 (filesystem authority) lines 46-51,
  AD-5 state_root line 62, AD-17 consumer wiring line 134.
- Data contract: `shared-data-contract.md` (same folder) — `current.json` schema (lines 5-39),
  Swap sequence symlink names (lines 137-148), fs authority notes (line 50 AD-3).

### Command-naming decision (do not re-litigate)

The EPIC pins `dotfiles-runtime inspect status` / `inspect history` / `inspect cache list`.
**Use the `inspect` group with subcommands.** Do NOT create a top-level `status` command and do
NOT follow SPEC.md:76 ("`dotfiles status`") or AD-20's flat `{wallpaper,status,history,cache}`
list — those are earlier, coarser namings. Flag this drift once in this story's record; the epic
naming wins for 3.2/3.3/3.4.

### Data sources (as-built)

- `IStateRepository.load_current() -> DesktopState | None` — `ports/state_repository.py:10-11`;
  **no other repository port needed.** Rt-3.1 pinned the port minimal (`load_current`/`save`
  only); `load_history` for the history use case is a Phase-3/rt-3-3 concern — do NOT add it here.
- `DesktopState` shape — `domain/models.py:133-144`: `wallpaper: WallpaperEntry`,
  `monitors: dict[str, MonitorWallpaperConfig]`, `palette/effects/icons: ... | None`,
  `applied_at`. Hashes: `wallpaper.content_hash`, `palette.entry_hash`, `effects.entry_hash`,
  `icons.entry_hash`; foundational note: palette/effects/icons are `None` when never derived
  (degraded apply) — the status output must render them as absent, not crash.
- `current/` live layout (`shared-data-contract.md` swap sequence + `cache-model.md` lines 12-18):
  `wallpaper-<monitor>.png` per monitor, `colors.yaml`, `colors.conf`, `colors.gtk.css`,
  `effects/` (dir symlink), `icons/` (dir symlink). Expected target names derive from
  `DesktopState` EXACTLY as `ReconcileDesktopStateUseCase._build_expected_targets` does
  (`reconcile.py:492-529`) — mirror that name set but READ-ONLY (no `_repoint_symlink`, no
  revert). `link.resolve()` may raise `OSError` on a dangling symlink — treat dangling as a
  distinct status (e.g. `dangling`), never crash (mirror reconcile.py:543-547).

### Composition root + CLI patterns to mirror

- Build the helper `_run_inspect_status()` in `cli/main.py` and monkeypatch IT in CLI tests
  (exact precedent: `_run_reconcile` main.py:384-417 + `test_cli_reconcile.py:97-102`
  `_fake_composition`).
- Wrap ALL expected domain errors: `(ValueError, RuntimeError, OSError)` → `logger.error` +
  `renderer.error(ErrorView(kind=..., message=...))` + `raise typer.Exit(code=1)`; plus a
  catch-all `Exception` → `UnexpectedError`. Mirror main.py:438-450 verbatim style.
- Output: `renderer.custom(CustomView(plain=..., object={...}, rich=...))`. The `object` is the
  `--format json` payload — include `wallpaper`, `monitors` (per-monitor backend/source_hash/
  fit_mode/mpv_options/ipc_socket), `palette`, `effects`, `icons`, `applied_at`, and a
  `current_symlinks` map with `{status, target}`.
- **Auto-seed guard:** `main_callback` (main.py:164-176) runs `_run_seed_if_needed()` for every
  command except when `"reconcile" in sys.argv`. `inspect` commands are read-only inspectors —
  auto-seeding would (a) hide AC 3's absent-state error on provisioned machines and (b) invoke
  csg/weg/itr for free a read command. Extend the skip: `if "reconcile" in sys.argv or
  "inspect" in sys.argv: return`. This mirrors the documented Story-1.13 P3 decision.

### Read-only invariant (AC 4 — negative tests required)

`inspect status` must create/write NOTHING: no `current/` symlink creation or repoint, no
`.staging-*` dirs, no `history.jsonl` file, no `.seed.lock` acquisition. Tests must assert the
absence of these side-effects (e.g. `state_root` snapshot before/after; `history.jsonl` does not
exist; `current/` unchanged on a diverged symlink). "A story implementation must leave the system
working end-to-end" — the status command must be safe to run anytime (including mid-swap).

### Test conventions (pass review or get bounced)

- Runner: `uv run --directory src/runtime pytest`; class-based grouping with AC/AD-citing
  docstrings (e.g. `class TestInspectStateUseCase:` "(NFR-3)"). No conftest.py.
- `_make_state()` builders with deterministic `"a"*64`-style hashes; `tmp_path` as `state_root`
  via adapter injection.
- CLI unit tests: monkeypatch the composition helper (`_fake_composition` pattern),
  `DOTFILES_INSTALL_SPINE` + `XDG_STATE_HOME` fixtures (mirror `test_cli_reconcile.py:88-95`).
- Pin TRANSIENT observables (caplog) not just final state; assert VALUES (hashes, symlink
  targets) not key presence; JSON payload asserts assert exact shape.
- Integration: use real `JsonStateRepository.save` + `os.symlink` to build the `current/` tree,
  then a FRESH `InspectStateUseCase` reads it — restart-survival-style realism (rt-3.1 lesson).

### Commit flow

`feat(rt-3-2): inspect status command ...` for the implementation; `docs(bmm): add story
rt-3-2 ...` carrying this story `.md` + `sprint-status.yaml`. (Precedent: rt-3-1 commits.)

### Project Structure Notes

- All new code under existing layers: `src/runtime/src/runtime/application/inspect.py` and
  `cli/main.py` (inspect group). Layering: application → domain/ports/adapters/application ONLY
  (test_layering.py:9,64); cli is the composition root (imports everything in-runtime).
  New `application/inspect.py` must import only `runtime.domain.*`, `runtime.ports.*`,
  `runtime.adapters.*` (if needed), and stdlib — NEVER `runtime.cli`.
- Tests land at `tests/unit/test_inspect.py`, `tests/unit/test_cli_inspect_status.py`,
  `tests/integration/test_inspect_integration.py` — naming matches `test_cli_*` / layer split.
- Package facts: `dotfiles-runtime` at `src/runtime/` (nested src layout), Python >= 3.14,
  hatchling, typer>=0.12, cli-output (editable sibling), ruff line-length 100 double-quotes,
  mypy strict, target py314.

### References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md#Story 3.2: inspect status command] (ACs verbatim)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md#Layer mapping] / [#AD-3 — JSON / dict-like store; filesystem is authority] / [#AD-5 — state_root] / [#AD-17 — Consumer wiring] / [#AD-20 — Separate dotfiles-runtime binary] / [line 27 application list: InspectStateUseCase]
- [Source: same folder shared-data-contract.md#current.json] / [#Swap sequence (AD-6 ownership)]
- [Source: _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md#CAP-7] / [cache-model.md#filesystem layout lines 10-18]
- [Source: src/runtime/src/runtime/cli/main.py:384-417 `_run_reconcile`] / [:164-176 `main_callback` auto-seed guard] / [:438-450 error mapping]
- [Source: src/runtime/src/runtime/application/reconcile.py:492-529 `_build_expected_targets`]
- [Source: src/runtime/src/runtime/ports/state_repository.py:10-11 `load_current`]
- [Source: src/runtime/src/runtime/domain/models.py:133-144 `DesktopState`]
- [Source: _bmad-output/implementation-artifacts/rt-3-1-history-jsonl-persistence.md#Dev Notes] — quality-gate baselines, port-minimality, commit style

## Dev Agent Record

### Agent Model Used

(Baseline: HEAD `06cb5b4` — fix: auto-commit code review findings.)

### Debug Log References

- Baseline before any change: `pytest` 429 passed / 2 skipped; `ruff check src` exactly 3
  (cli/main.py:166, cli/main.py:271, domain/models.py:35); `mypy --strict src` exactly 4
  (domain/models.py:30 + 3 import-untyped in cli/main.py); `ruff format --check src` clean
  (src scope); layering 56 passed. Re-verified live at baseline: ruff 3 (same rules, B008×2
  + E501), mypy 4 (same rules). RED phase confirmed per task: test_inspect.py failed with
  ModuleNotFoundError before use case existed; test_cli_inspect_status.py 11 failed before
  CLI surface existed.
- After implementation: `pytest` 459 passed / 2 skipped (+30 new: 11 use-case, 13 CLI incl.
  4 guard tests, 5 integration, 1 new layering module case); `ruff check src` exactly 3
  baseline violations (same rules, shifted line numbers only — no NEW); `ruff format --check
  src` clean; `mypy --strict src` exactly 4 baseline violations (no NEW); layering 57 passed.

### Completion Notes List

- **Implemented** `InspectStateUseCase` in `application/inspect.py`: read-only projection of
  `current.json` (wallpaper hash + source path, per-monitor backend/source_hash/fit_mode/
  mpv_options/ipc_socket, palette/effects/icons entry hashes or `None` for degraded layers,
  `applied_at`) plus live `current/` symlink reflection. Absent state → `RuntimeError`
  "no state recorded — run `dotfiles-provision apply` / `dotfiles-runtime wallpaper set
  <img>` to seed" (AC 3).
- **Symlink statuses** are `ok | missing | diverged | dangling` (AC 2, NFR-3): `missing` =
  no symlink at the expected name (incl. a non-symlink file squatting there), `dangling` =
  symlink whose target does not exist or whose `resolve()` raises `OSError` (mirrors
  reconcile.py:543-547 tolerance), `diverged` = resolves elsewhere than the expected
  cache-entry target. Expected name set mirrors `ReconcileDesktopStateUseCase
  ._build_expected_targets` exactly (incl. the monitor traversal ValueError guard) but with
  ZERO writes. Design note: dangling detection uses `link.exists()` (follows symlink) —
  `Path.resolve()` is non-strict in Python 3.14 and does NOT raise for broken targets, so a
  resolve-only check could never distinguish dangling; the `reconcile` OSError branch only
  fires on pathological cases (e.g. symlink loops).
- **CLI**: `inspect` typer group + `status` command via `inspect_app` (epic naming
  `dotfiles-runtime inspect status` wins — see drift note below). `_run_inspect_status()`
  composition helper wires `_resolve_state_root()` + `JsonStateRepository` only — no seeder,
  mutex, derivation adapters, or reloaders (AC 4). Error mapping mirrors main.py:438-450:
  `(ValueError, RuntimeError, OSError)` → `ErrorView` + exit 1; catch-all → `UnexpectedError`.
  JSON payload: wallpaper, wallpaper_source_path, monitors (per-monitor detail), palette,
  effects, icons, applied_at, `current_symlinks` map of `{status, target}`.
- **Auto-seed guard** extended: `main_callback` now skips seeding when `"inspect" in
  sys.argv` (alongside the reconcile skip). Guard tests prove: inspect never seeds, reconcile
  still skips, other commands still seed, and the absent-state error is reachable end-to-end
  (AC 3).
- **Read-only invariant verified negatively** (AC 4): unit + integration tests snapshot the
  full `state_root` tree (paths, symlink targets, file bytes) before/after a run on a
  DIVERGED tree and assert byte-identity; assert `history.jsonl` absent, `.seed.lock`
  absent, no `.staging-*` dirs, diverged symlink untouched, and the repo `save()` tripwire
  never fires.
- **Naming drift flag (once, per Dev Notes)**: SPEC.md:76 ("`dotfiles status`") and AD-20's
  flat `{wallpaper,status,history,cache}` list are earlier/coarser namings; the epic's
  `inspect` group with `status`/`history`/`cache list` subcommands wins for 3.2/3.3/3.4 —
  implemented as such.
- **Scope respected**: only the status path was built — no `inspect history`, no
  `inspect cache list`, no `IStateRepository.load_history` (rt-3-3/3-4 concerns).

### File List

- src/runtime/src/runtime/application/inspect.py (new)
- src/runtime/src/runtime/cli/main.py (modified: inspect group + status command +
  `_run_inspect_status` helper + auto-seed guard)
- src/runtime/tests/unit/test_inspect.py (new)
- src/runtime/tests/unit/test_cli_inspect_status.py (new)
- src/runtime/tests/integration/test_inspect_integration.py (new)
- _bmad-output/implementation-artifacts/rt-3-2-inspect-status-command.md (modified)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified)

## Change Log

- 2026-09-02: Story created — ultimate context engine analysis completed. Greenfield Epic-3
  inspection command; `InspectStateUseCase` + `inspect status` CLI + read-only guardrail tests.
- 2026-09-02: Implemented — `InspectStateUseCase` (read-only status projection + live
  `current/` symlink reflection), `dotfiles-runtime inspect status` CLI, auto-seed guard
  extended to `inspect`; 30 new tests (11 use-case, 13 CLI incl. guard, 5 integration, 1
  layering module case); all quality gates pass with zero new violations. Status → review.