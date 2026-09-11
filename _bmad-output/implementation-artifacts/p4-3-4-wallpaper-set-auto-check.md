# Story 4.7: Auto-Check Inputs on `wallpaper set`

Status: ready-for-dev

baseline_commit: 35cc54a

Epic: Phase 4 backlog sibling (Gate 1 ruling on p4-3-2, option b). Closes the Phase 3 deferred item "auto-check on `wallpaper set`".

## Story

As a user who just set a wallpaper,
I want the stale-input check to run automatically and report its result,
so a derivation input that changed concurrently is surfaced immediately instead of waiting for a manual `reconcile --check-inputs`.

## Acceptance Criteria

1. After a SUCCESSFUL `wallpaper set` (past the reload-failure gate), the invalidation check runs and its stale/fresh result is appended to the command output (plain + object views). Fresh → `"inputs: all layers fresh"`; stale → `"inputs stale: <layers> (fresh: <layers>)"`. Object view carries `inputs_stale`/`inputs_fresh`; on check failure `inputs_check_error` is set so the empty-list shape cannot masquerade as "fresh" (AC 1, Gate 2 Item 1)
2. A FAILED set (apply/reconcile error, or reload failures) runs NO check — the failure is reported, not masked by a check. Verified via injected-counter/absence, not output string alone (AC 2)
3. No new invalidation logic: the check is `_run_check_inputs` reuse (same `InvalidationQueryAdapter` + `CheckInputsUseCase` composition `reconcile --check-inputs` uses); no duplicated input discovery (AC 3)
4. The auto-check is INFORMATIONAL: it never changes the command's exit code (a stale input after a successful set exits 0; the reload-failure gate already owns failure). Re-check failure (e.g. OSError) is surfaced as a warning line, never swallowed silently and never converted into a set failure (AC 4)

## Tasks / Subtasks

- [ ] Wire the check into `wallpaper_set` in `src/runtime/src/runtime/cli/main.py` (AC: 1, 3, 4)
  - [ ] After the `reload_failures` gate and before rendering, call `_run_check_inputs()` (reuse) and append result lines to the existing summary + object payload. No new composition function — if reuse proves awkward, extract a tiny helper, do NOT re-inject adapters inline.
  - [ ] Wrap the check call in `except (ValueError, RuntimeError, OSError)` → append `"inputs check failed: <reason>"` warning line (log at warning). Never `raise`, never change exit code (AC 4).
  - [ ] Keep the existing render surfaces coherent: plain summary lines appended after the applied summary; object gains `inputs_stale` / `inputs_fresh` keys (empty lists when no check ran / fresh).
- [ ] Tests `src/runtime/tests/unit/test_cli_wallpaper_set_autocheck.py` (AC: 1–4)
  - [ ] Success fake (`_run_wallpaper_set` monkeypatched, `_run_check_inputs` returns stale set) → exit 0, stale line present, object `inputs_stale` populated.
  - [ ] Success + fresh → exit 0, "all layers fresh" line.
  - [ ] Reload-failure path → exit 1, check NOT called (counter), stale lines absent.
  - [ ] Apply/reconcile exception path → exit 1, check NOT called.
  - [ ] Check raising → exit 0 (set still succeeded), warning line, no traceback.
  - [ ] Real-composition guard: assert `_run_check_inputs` is the code path reused (monkeypatch it; do not reach adapters).
- [ ] Run full `uv run --directory src/runtime pytest` (CLI surface changed) + layering + ruff + format

## Dev Notes

### Scope boundary — auto-check ONLY

Story 4.7 surfaces staleness after a set. It does **NOT** implement:
- Auto-REGENERATION of stale layers (reconcile's job; a set is not a convergence pass)
- Any change to `CheckInputsUseCase`, `InvalidationQueryAdapter`, or the `reconcile --check-inputs` path
- A suppression flag / config toggle (always-on; add only if a real need appears)
- Exit-code changes (AC 4 — informational)

### Layering (AD-25, locked)

- All new code is CLI composition only (no new domain/application/ports). `test_layering.py` run, not modified.

### Conventions consumed (do not redefine)

1. `_run_check_inputs` reuse (p4-3-2 planner precedent: reuse pipelines, never parallel implementations).
2. Informational append pattern (`_render_converge` precedent): appended summary lines + object keys, exit code owned elsewhere.
3. Typed failure surfacing but non-fatal for informational sub-checks (warning + line, no raise).
4. Reload-failure gate stays the authority for set failure (R5).
