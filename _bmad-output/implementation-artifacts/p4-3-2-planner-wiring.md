# Story 4.5: Planner Wiring (Real Gap → Preview → Execute)

Status: ready-for-dev

baseline_commit: a9dc687

Epic: Phase 4 Epic 3 — Diff + Plan Execution (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase4.md`)

## Story

As a user with a `desired.json`,
I want `reconcile --plan` to show the real declarative gap and plain `reconcile` to converge through it,
so that the system keeps its declared promise instead of only its recorded state.

## Acceptance Criteria

1. `reconcile --plan` with a `desired.json` present renders the ChangeSet gap: wallpaper target (or "wallpaper converged"), pins to add + pins absent as INFORMATIONAL rows (never action rows), keep target as `current → desired` (or current + converged), prunable per-layer under the AD-30 floor, and "already converged" iff `is_empty` AND nothing prunable (Gate 2 ratification: bare `is_empty` would print "converged" above prunable rows) (AC 1)
2. `reconcile --plan` with NO `desired.json` keeps today's p4-1-1 output byte-for-byte (imperative behavior untouched; declarative path only engages on declared intent) (AC 2)
3. Plain `reconcile` with a `desired.json` present and non-empty gap executes WITHOUT prompt (B2): wallpaper target via the existing `_run_wallpaper_set` pipeline (same mutex, same reloaders, same history trigger — reuse, not re-implementation); then AD-30 deletes via the `remove_entry` seam ONLY for entries outside `active + last-N + seed-pinned + undated` (manual `--keep 0` + `--prune-pinned` still excludes `active + undated` — no whole-cache delete); every deletion logged; `pins_absent` never triggers removal (AC 3)
4. Malformed `desired.json` fails `reconcile`/`--plan` LOUD (exit 1, file + field in message) — never silent fallback to imperative mode (a typo'd intent file must not masquerade as "no intent") (AC 4)

## Tasks / Subtasks

- [ ] Create `src/runtime/src/runtime/application/planner.py` (AC: 1, 3)
  - [ ] `plan_convergence(desired, actual, current_keep) -> ChangeSet`: thin composition over `build_actual_state`-shaped inputs? No — planner takes the two PROJECTIONS (`DesiredState`, `ActualState`) + `current_keep` and delegates to `diff_states`. (Composition of loaders stays in CLI per repo precedent — `_run_reconcile_plan` composes use cases; use cases stay I/O-free.)
  - [ ] `execute_plan(...)` ownership (Gate 1 ruling: ConvergeUseCase with injected executors `set_wallpaper: Callable[[str], ...]`, `remove: Callable[[str, str], bool]` — testable without disk, mirrors `PruneUseCase` precedent). Execution order: wallpaper converge FIRST (new derivations may create entries prune must see), deletes SECOND under the AD-30 floor recomputed post-converge.
  - [ ] `pins_to_add` handling: NO pin store exists — planner reports them as pending/manual rows; it does NOT invent persistence. (Pin lifecycle is a Phase 5/planner-follow-up question, explicitly out of scope.)
- [ ] Rewire `_run_reconcile_plan` in `src/runtime/src/runtime/cli/main.py` (AC: 1, 2)
  - [ ] `read_desired_state(state_root)` → `None` → today's output untouched (extract current rendering into a helper so the branch is `if desired is None: render_imperative() else: render_declarative()` — no duplicated render code).
  - [ ] Declarative branch composes: `JsonStateRepository.load_current()` + `entries_for`/`seed_pins` adapter callables (same lambdas p4-1-1 uses) → `build_actual_state(current, ..., keep=desired.keep)` → `diff_states(desired, actual, current_keep=<CLI keep>)` → render ChangeSet + prunable + informational pins_absent rows.
  - [ ] `--keep` flag vs `desired.keep` (AD-30 precedence: code default < desired declaration < explicit CLI flags): explicit `--keep` (non-default) overrides `desired.keep` for the actual-state/prune computation; bare default defers to `desired.keep`. Needs an explicit-ness signal — Typer `min=0` default masks it; use a sentinel default (`None`) and fall back to 5 only when neither flag nor desired supplies it. Absent `desired.json` + bare `--keep` keeps today's behavior.
- [ ] Extend plain `reconcile` execute path (AC: 3)
  - [ ] After the existing repoint/reload sequence (untouched), if `desired.json` present and gap non-empty: run wallpaper converge via `_run_wallpaper_set(target)` reuse, then recompute actual + deletes under the floor. No prompt (B2). Log every deletion at the same level as `remove_entry`'s log line (no double-logging — check `remove_entry` already logs; CLI logs the summary count only).
- [ ] `src/runtime/tests/unit/test_planner.py` + CLI tests (AC: 1–4)
  - [ ] Planner unit: converged → no executor calls; wallpaper-only → set_wallpaper called once with target, no deletes; prunable-only → remove called exactly for floor-external entries; pins_absent → zero executor calls (informational).
  - [ ] CLI: `--plan` without desired.json → byte-identical legacy output (golden test against current rendering); with desired.json → gap rows incl. informational pins; malformed desired.json → exit 1 with file+field in output.
  - [ ] AD-30 floor: `--keep 0 --prune-pinned` fixture asserting active + undated survive.
- [ ] Run full `uv run --directory src/runtime pytest` (CLI surface changed) + layering + ruff + format

## Dev Notes

### Scope boundary — planner wiring ONLY

Story 4.5 closes the declarative loop. It does **NOT** implement:
- **AD-31 history file lock** — touches every history writer (broad, cross-cutting). Proposed follow-up story p4-3-3.
- **Auto-check on `wallpaper set`** (Phase 3 deferred, epic cross-contracts) — proposed follow-up story p4-3-4.
- **Pin lifecycle/persistence** (`pins_to_add` application) — no store exists; reported only. Future phase question.
- `desired.json` WRITING from any command (still nothing provisions intent files — user authors them).

### Gate 1 scoping ruling (owner: option (b) — backlog siblings)

AD-31 lock → p4-3-3 backlog. Auto-check on `wallpaper set` → p4-3-4 backlog. This story stays plan+execute only.


### Layering (AD-25, locked)

- Planner use-case in `application/` (injected executors, no I/O); loader composition in CLI (repo precedent); `test_layering.py` run, not modified.

### Conventions consumed (do not redefine)

1. `_run_wallpaper_set` / `remove_entry` reuse (no parallel pipelines).
2. AD-30 precedence + floor (locked); B2 no-prompt execute + log (locked); option-1 `is_empty` (locked p4-3-1 Gate 2).
3. Malformed intent fails loud (declarative-config philosophy, p4-2-1 precedent).
4. `--plan` stays read-only: no seeder, no mutex, no history appends (p4-1-1 precedent).
