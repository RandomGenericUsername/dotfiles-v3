# Story 4.4: Diff Engine (Desired × Actual → ChangeSet)

Status: ready-for-dev

baseline_commit: 8e3ec07

Epic: Phase 4 Epic 3 — Diff + Plan Execution (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase4.md`)

## Story

As the future planner,
I want a pure diff between declared intent and observed reality,
so that `reconcile --plan` shows a real gap instead of a policy preview.

## Acceptance Criteria

1. `ChangeSet` frozen dataclass carries `{wallpaper_target, pins_to_add, pins_absent, keep_target}`: `wallpaper_target` is the desired path or `None` when converged (including desired-equals-`None`-actual — fresh machine always diverges unless desired wallpaper is also absent, which the schema forbids); `pins_to_add`/`pins_absent` are sorted tuples; `keep_target` is the desired keep or `None` when unchanged (AC 1)
2. `diff_states(desired, actual, current_keep=5)` is pure: `wallpaper_target = None` iff `desired.wallpaper == actual.current_wallpaper`; `pins_to_add = sorted(set(desired.pinned) - set(actual.pinned_hashes))`; `pins_absent = sorted(set(actual.pinned_hashes) - set(desired.pinned))` (informational — seed-pins stay protected per AD-30 floor; the planner in p4-3-2 decides, defaulting to no unpin); `keep_target = None` iff `desired.keep == current_keep`, else `desired.keep`; `current_keep` injected (default 5 = code default per AD-30 precedence) with `current_keep < 0` → `ValueError` (AC 2)
3. `ChangeSet.is_empty` is `True` iff wallpaper, pins-to-add, and keep are converged — `pins_absent` deliberately EXCLUDED (owner decision, Gate 2 option 1: an extra seed-pin is informational residue, not an actionable gap; the planner must still render it in `--plan` output) — the planner's converge/skip signal (AC 3)

## Tasks / Subtasks

- [ ] Add `ChangeSet` frozen slots dataclass to `src/runtime/src/runtime/domain/models.py` (AC: 1, 3)
  - [ ] Fields: `wallpaper_target: str | None`, `pins_to_add: tuple[str, ...]`, `pins_absent: tuple[str, ...]`, `keep_target: int | None`. Document dumb-carrier status (comparison/canonicalization in the builder) and that `pins_absent` is informational (seed-pin protection lives with the planner/policy, AD-30).
  - [ ] `is_empty` as a property on the model (derived predicate, no I/O — same pattern as any derived domain predicate; takes no arguments).
  - [ ] stdlib allowlist only; no I/O imports.
- [ ] Create `src/runtime/src/runtime/application/diff.py` (AC: 2)
  - [ ] `diff_states(desired: DesiredState, actual: ActualState, current_keep: int = 5) -> ChangeSet` implementing exactly the AC 2 rules. `isinstance(current_keep, bool)` or non-`int` or `< 0` → `ValueError` (bool guard mirrors the `keep` strictness from p4-2-1 — `True` must not slip in as `1`).
  - [ ] No imports beyond `domain.models` (+ stdlib `collections.abc` only if needed). No ports, no adapters, no `PruneUseCase` — the diff consumes projections, never raw sources.
- [ ] Create `src/runtime/tests/unit/test_diff.py` (AC: 1, 2, 3)
  - [ ] Converged pair → all-None/empty `ChangeSet`, `is_empty is True` (desired wallpaper == actual path, pins equal as sets in different order, keep == current_keep).
  - [ ] Fresh machine (`current_wallpaper=None`, empty pins) → `wallpaper_target` set, `pins_to_add` == all desired pins, `is_empty is False`.
  - [ ] Wallpaper-only change; pins added only; pins absent only (seed-pin still listed, not removed — informational); keep-only change (`keep_target` set, everything else converged).
  - [ ] `current_keep` override: `desired.keep=5, current_keep=3` → `keep_target=5`; `current_keep=-1` / `True` / `"5"` → `ValueError`.
  - [ ] `is_empty` truth table: each single-divergence member flips it to `False` (4 cases, parametrized).
- [ ] Run `uv run --directory src/runtime pytest tests/unit/test_diff.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — diff ONLY

Story 4.4 computes the gap. It does **NOT** implement:
- Acting on the gap (setting wallpaper, pruning, pinning — p4-3-2 planner wiring)
- Wiring `diff_states` into any CLI command (`reconcile --plan` still shows the p4-1-1 policy preview; replacement is p4-3-2 scope)
- Resolving `current_keep` from anywhere (injected; Epic 3 CLI scope decides the source — CLI default today)
- Unpinning semantics (seed-pins are historical facts; `pins_absent` only reports them)

### Layering (AD-25, locked)

- `ChangeSet` in `domain/` (pure, `is_empty` derived predicate); `diff_states` in `application/` (pure function of two value objects + int)
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. Sorted/deterministic outputs (repo-wide snapshot-testability rule).
2. Strict int validation with bool rejection (p4-2-1 precedent).
3. AD-30 precedence (`code default 5 < desired declaration < CLI flags`) — `current_keep=5` default is the "code default" floor the desired declaration overrides.
4. `pins_absent` informational only — protection policy stays in exactly one place (prune/planner), never in the diff.
