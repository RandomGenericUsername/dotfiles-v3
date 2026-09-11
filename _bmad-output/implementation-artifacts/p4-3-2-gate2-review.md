# Gate 2 Review — Story p4-3-2 (Planner Wiring)

Status: DEV done, awaiting patch decisions. NOTHING APPLIED — no code changed since verification.

## Verification (pre-review, all green)

- New tests: `test_planner.py` (5) + `test_cli_planner_wiring.py` (7) — 12 passed.
- Plan/reconcile/layering subset: 105 passed. Full suite: 942 passed, 2 skipped.
- `ruff check` on story files: only pre-existing B008 ×2 (untouched lines 189/305). `ruff format`: clean. `mypy`: only pre-existing (cli_output stubs, `sections` redef).

## Review panel findings (3/3 reporting — patches required)

### Item 1 — `--prune-pinned` silently dropped in declarative branch (Blind Hunter B1 + Edge 10 agree: BUG)

**Problem (full):** Declarative `--plan` calls `build_actual_state(..., compute_keep)`, which hardcodes `PruneUseCase.run()` default `prune_pinned=False`. A user passing `--plan --prune-pinned` with `desired.json` gets pin-protected prunable rows while the flag promises pin inclusion — and the JSON echoes `"prune_pinned": true` while `prunable` was computed with `False` (payload lies twice). Same defect in `_run_converge.refresh_actual`. `build_actual_state` has no `prune_pinned` parameter, so the flag is unplumbable.

**Proposed patch:**
```python
# actual_state.py (additive optional param — no p4-2-2 behavior change)
def build_actual_state(..., keep: int = 5, prune_pinned: bool = False) -> ActualState:
    ...
    plan = usecase.run(prune_pinned=prune_pinned)
# main.py declarative branch
actual = build_actual_state(..., compute_keep, prune_pinned)
# main.py _run_converge.refresh_actual — plain reconcile rejects the flag
# without --plan, so execute-path semantics stay "always protected":
return build_actual_state(..., desired.keep, prune_pinned=False)
```

### Item 2 — Converge swallows wallpaper-pipeline reload failures (Blind Hunter B2: BUG)

**Problem (full):** `set_wallpaper` discards `_run_wallpaper_set`'s result. The `wallpaper set` command treats `reload_failures` as fatal; the converge path reports `converged wallpaper: <target>` regardless. Failed Hyprpaper/AGS reload recorded as success.

**Proposed patch:**
```python
def set_wallpaper(target: str) -> object:
    res = _run_wallpaper_set(Path(target))
    if res.reconcile.reload_failures:
        raise RuntimeError(f"reload failed for: {', '.join(res.reconcile.reload_failures)}")
    return res
```

### Item 3 — Plain `reconcile` mutates before malformed-intent failure (Blind Hunter B3: BUG)

**Problem (full):** `_run_reconcile()` (symlink repoint + `history.jsonl` append) executes fully, THEN `_run_converge()` reads `desired.json` and raises. A typo'd intent file causes a full imperative mutation before exit 1. AC4 demands loud failure; fail-fast demands it before mutation.

**Proposed patch** (validate before `_run_reconcile()`, in the plain path only):
```python
from runtime.adapters.desired_state_reader import read_desired_state
read_desired_state(_resolve_state_root())  # raises ValueError loud, pre-mutation
```

### Item 4 — Keep row renders `3 -> 3` (Blind Hunter B4)

**Problem (full):** With no CLI flag, `compute_keep == desired.keep == keep_target` whenever a keep gap exists (desired 3 vs default 5 renders `keep: 3 -> 3` — nonsensical). The row should show current (5) → target (3). `_DeclarativePlanResult` doesn't store `current_keep`, so correct rendering is currently impossible.

**Proposed patch:** add `current_keep: int` to `_DeclarativePlanResult` (set from the existing local), render `f"keep: {result.current_keep} -> {changeset.keep_target}"`.

### Item 5 — Empty-gap/prunable semantics + false docstring (Blind Hunter B5 + Edge 11)

**Problem (full):** `ConvergeUseCase.run` always deletes from the refresh, so "Read-only when the gap is empty (no calls)" is false whenever prunable is non-empty — and no test covers empty-ChangeSet + non-empty-prunable. Separately, `keep_target` in the execute-converged gate makes "already converged" unreachable whenever `desired.keep != 5` (nothing persists current keep; Edge 9): keep in the execute path is applied-policy info, not a pending action.

**Proposed patch:** fix docstring to "Read-only when the gap is empty AND nothing is prunable; AD-30 deletes run regardless of is_empty"; add empty-ChangeSet + non-empty-prunable test pinning deletes; drop `keep_target` from `_render_converge`'s already-converged gate and relabel the row `keep policy: {n} (in force)`.

### Item 6 — Partial-failure reporting (Edge 6 + Edge 7)

**Problem (full):** (a) `_run_wallpaper_set` raising mid-converge discards the already-completed imperative summary — user sees one error line, no record that repoint succeeded. (b) `remove_entry` raising mid-loop aborts the dict-comprehension; earlier deletes vanish from any report. Precedent `_run_prune` catches per-entry `OSError`, continues, raises `RuntimeError("prune removed X, failed Y")`.

**Proposed patch:** mirror the precedent — per-entry `try/except OSError` with `failures` list, `RuntimeError` with counts at the end; converge-failure message becomes `reconcile succeeded, converge failed: {exc}` preserving the partial-success fact.

### Item 7 — Missing story-required tests (Auditor + Blind Hunter B6)

**Problem (full):** (a) No golden byte-identical test for `--plan` without desired.json (story explicitly requires it; current proof is "legacy suite passes + extraction verbatim" — not a test). (b) No AD-30 floor fixture (`--keep 0 --prune-pinned` asserting active + undated survive). (c) No plain-`reconcile` malformed-desired CLI test (only `--plan` + direct `_run_converge`). (d) Tautological keep assert (`"keep: 3 -> 3" or "keep: 3 (converged)"` passes under either rendering — assert one exact string; resolves with Item 4).

**Proposed patch** (tests only): golden test comparing declarative-absent output against a recorded legacy transcript (or `_render_imperative_plan` output on a fixed `_ReconcilePlanResult` — locks the extraction byte-for-byte); floor fixture with active + undated entries under keep=0/prune_pinned через real `build_actual_state` + `PruneUseCase` path; plain malformed CLI test asserting exit 1 with file + field; exact keep-row string.

### Spec deviation to ratify (Auditor AC1 note)

Code gates "already converged" on `is_empty and total_removable == 0`; AC1 says "iff is_empty". The code is saner (otherwise "converged" prints above prunable rows). Ratify by amending AC1 to `is_empty and total_removable == 0` — no code change.

## Ballot (vote Approve / Request changes PER ITEM in chat)

- Item 1 (prune_pinned threading)?
- Item 2 (reload-failure raise)?
- Item 3 (pre-validate before mutation)?
- Item 4 (current_keep row)?
- Item 5 (docstring + gate + relabel + test)?
- Item 6 (partial-failure reporting)?
- Item 7 (four tests)?
- Spec deviation ratified (amend AC1)?
