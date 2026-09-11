# Story 4.1: `reconcile --plan` Read-Only Preview

Status: done

baseline_commit: 816ac84

Epic: Phase 4 Epic 1 — Reconciliation Preview (first Phase 4 story; full Phase 4 PRD/epics pending — this story seeds them, it does not replace them)

## Story

As a user,
I want `reconcile --plan` to show the stale set plus the prune removal set without executing anything,
so that the future diff engine has a stable preview surface and I can review today what `reconcile` would change.

## Acceptance Criteria

1. `reconcile --plan` reports the stale layers (exactly as `--check-inputs`) PLUS the prune removal plan (exactly as `inspect cache prune --dry-run`), in one machine-readable object, performing zero mutations — no cache writes, no repoints, no JSON/history writes, no seeding, no reloads (AC 1)
2. `--plan` is mutually exclusive with `--check-inputs` and `--regenerate-stale` (exit 2 when combined — read vs mutate vs preview must not mix) (AC 2)
3. Absent state (no `current.json`) exits non-zero with a clear message, never seeds (AC 3)
4. Exit 0 whether or not anything is stale/reclaimable (preview is information, like `--check-inputs`) (AC 4)
5. `--keep N` (default 5) and `--prune-pinned` (default False) tune the removal portion with identical semantics to `inspect cache prune` (AC 5)

## Tasks / Subtasks

- [x] Wire `reconcile --plan` in `src/runtime/src/runtime/cli/main.py` (AC: 1–5)
  - [x] Add `plan: bool = typer.Option(False, "--plan", help=...)` plus `keep: int` (`min=0`, default 5) and `prune_pinned: bool` (default False) to the `reconcile` command, mirroring the prune CLI flag shapes
  - [x] Mutual exclusion: more than one of `--check-inputs` / `--regenerate-stale` / `--plan` → `ErrorView(kind="MutuallyExclusiveOptions")` + exit 2 (extend the existing two-flag guard to three)
  - [x] New composition helper `_run_reconcile_plan(keep, prune_pinned)` that composes the TWO existing read-only use cases (precedent: `_run_wallpaper_set` composes apply + reconcile): `CheckInputsUseCase` (repo + invalidation + recorded reader, spine paths via `derive.find_*`) for the stale set, then `PruneUseCase` (`entries_for`/`seed_pins` adapter callables) for the removal set. NO seeder, NO mutex (read-only like dry-run — takes no lock), NO derivation adapters, NO reloaders, NO history append
  - [x] No new `application/` unit: the Phase 4 diff engine will replace these internals; this story only fixes the CLI surface + composition. (Deliberate: minimal seam for the engine to land behind.)
  - [x] Render via `cli-output`: plain (`stale layers: …` / `all layers fresh` + `reclaimable: N …` / `nothing reclaimable`) + machine-readable object `{stale: [...], fresh: [...], removals: {layer: [...]}, kept: {...}, total_removable: N, keep: N, prune_pinned: bool}`; exit 0; absent state → `ErrorView` + exit 1 (via the check's `ValueError`)
  - [x] Confirm the existing `main_callback` seed guard covers the flag path (`ctx.invoked_subcommand == "reconcile"` → skip) — pin with a test, no new guard code
- [x] Create `src/runtime/tests/unit/test_cli_reconcile_plan.py` (AC: 1–5)
  - [x] Real end-to-end (no monkeypatched composition): tmp state + spine, warm seeded entries; edit a template; run `reconcile --plan --format json`; assert stale palette+icons AND removal set present, exit 0
  - [x] Zero-mutation pin: FS snapshot (v2 helper pattern: links + dirs + modes + mtimes + hashes) byte-identical before/after, including no `.seed.lock` (no lock taken) and no history append
  - [x] Mutual exclusion: `--plan --check-inputs`, `--plan --regenerate-stale`, all three → exit 2 each
  - [x] `--keep`/`--prune-pinned` passthrough changes the removal portion exactly as `inspect cache prune --dry-run` would (compare against the prune CLI on the same fixture)
  - [x] Absent state → exit 1, clear message, nothing seeded
  - [x] Flag-off default: plain `reconcile` still takes the swap path (extend the 1.3 tripwire pattern)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_cli_reconcile_plan.py tests/architecture/test_layering.py` and confirm green

## Review Record (Gate 2, 2026-09-11)

Full detail: `p4-1-1-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; 22 findings). Operator verdicts
per-item ballot: apply A–F, dismiss X1–X3 confirmed.

Applied:
- A: orphaned `--keep`/`--prune-pinned` without `--plan` → exit 2.
- B: fake captures forwarded kwargs; invocations use real flags; parity covers `kept`/`total_removable` + `--prune-pinned` case.
- C: e2e snapshots both `state_root` and install spine.
- D: 10 new tests (exclusion combo, orphaned flags, negative keep, kind asserts, seed tripwire, differential equality, both quadrants, corrupt history).
- E: removals render in canonical `LAYERS` order (missing keys default `()`).
- F: story line 30 wording matches implemented strings.

Dismissed:
- X1 comma-except rewrite — verified tuple semantics + repo convention + formatter-enforced.
- X2 redundant absent guard — check owns absent-rejection by tested contract; e2e pins exit 1.
- X3 read lock/snapshot — contradicts approved read-only no-lock design.

Verification: 800 unit/architecture passed, ruff clean (only pre-existing B008), mypy clean except pre-existing cli_output stubs + pre-existing no-redef.

## Dev Notes

### Scope boundary — preview surface ONLY

Story 4.1 fixes the CLI contract the diff engine will later fill. It does **NOT** implement:
- Desired-state file/schema (still deferred — preview uses code default + flags only)
- `actual state` projection beyond what check/prune already read
- A `diff` engine or `Planner` unit (the internals stay two composed use cases)
- Execution of anything (no derive, no delete, no repoint, no reload, no history)
- Changes to check/prune/regen/doctor/verify behavior (consumed read-only)

### Layering (AD-25, locked)

- CLI composition-root only (wiring + rendering), mirroring `_run_wallpaper_set` precedent
- No new `application/`, `ports/`, `domain/`, or `adapters/` units
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. Read-only discipline: no seeder/mutex/derivation/reloaders in the composition (dry-run precedent: no lock).
2. Stale-vs-corrupt, missing→stale, wallpapers-excluded, legacy, and keep-policy semantics all inherited unchanged from 1.2/1.3/3.2.
3. Exit codes: 0 informational, 1 operational failure/absent, 2 usage (mutual exclusion, bad `--keep`).
4. Seed guard: `ctx.invoked_subcommand` positional, already covering `reconcile`.
