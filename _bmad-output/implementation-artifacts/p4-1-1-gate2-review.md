# Gate 2 Review — p4-1-1 `reconcile --plan` Preview

Date: 2026-09-11. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
22 findings (overlapping). Zero files changed — all items below are proposals.

Files: `main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_cli_reconcile_plan.py`.

---

## APPLY A — orphaned `--keep`/`--prune-pinned` rejected (Blind #1, Edge #1, Auditor #7)

**Situation.** `--keep`/`--prune-pinned` are accepted on ALL `reconcile`
modes but silently ignored outside `--plan` (`reconcile --keep 1` runs the
full mutating reconcile and drops the flags; same for `--check-inputs --keep`).

**Proposal** (next to the mutual-exclusion guard):
```python
# BEFORE
    modes = [check_inputs, regenerate_stale, plan]
    if sum(1 for mode in modes if mode) > 1:
# AFTER
    modes = [check_inputs, regenerate_stale, plan]
    if (keep != 5 or prune_pinned) and not plan:
        logger.error("reconcile: --keep/--prune-pinned require --plan")
        renderer.error(ErrorView(kind="MutuallyExclusiveOptions",
            message="--keep and --prune-pinned require --plan"))
        raise typer.Exit(code=2) from None
    if sum(1 for mode in modes if mode) > 1:
```

## APPLY B — prove flag forwarding + full parity (Blind #3, Edge #4, Auditor #3)

**Situation.** The shape-test fake swallows `keep`/`prune_pinned` (wiring bugs
pass); the JSON test bakes values into the stub instead of CLI flags; parity
covers only `removals`, not `kept`/`total_removable`; `--prune-pinned` has no
e2e.

**Proposal.** Capture kwargs in the fake (`calls.append((keep, prune_pinned))`),
invoke with `--keep 3 --prune-pinned`, assert both the captured args and the
payload; extend the parity test to `kept` + `total_removable` and add a
`--prune-pinned` parity case on both sides.

## APPLY C — snapshot the spine too (Blind #6, Edge #5, Auditor #5)

**Situation.** The zero-mutation snapshot covers only `state_root`; a plan-path
spine write would pass.

**Proposal.** Snapshot `(state_root, install)` before/after in the e2e tests
and assert both equal.

## APPLY D — test gaps batch (Blind #7, Edge #5, Auditor #1/#2/#4/#8/#10)

**Situation.** Missing: `check+regen` exclusion combo; negative `--keep`
(Typer `min=0` → exit 2); `ErrorView` kind assertions (only exit codes);
seed-guard tripwire for `--plan`; differential stale equality vs
`--check-inputs` on the same fixture; fresh+reclaimable and stale+clean
quadrants; corrupt-history → exit 1.

**Proposal.** Add one test each (all mirror existing patterns in this file):
`test_mutual_exclusion_check_regenerate`, `test_negative_keep_rejected`,
kind assertions folded into the three exclusion tests, `test_plan_never_seeds`
(monkeypatched `_run_seed_if_needed` + spine containing `default.png`),
differential `check-inputs` equality inside the template-edit e2e, a
fresh-with-leftovers e2e (warm, no edit → fresh + reclaimable), a stale-only
e2e (template edit, no old entries → stale + `total_removable == 0`), and a
corrupt-`history.jsonl` e2e → exit 1.

## APPLY E — canonical LAYERS render order (Edge #3)

**Situation.** The plan branch iterates `sorted(removals)` (alphabetical),
diverging from `inspect cache prune --dry-run` plain output which uses
canonical `LAYERS` order, and silently tolerating a missing/extra layer key.

**Proposal.**
```python
# BEFORE
        removals = {layer: sorted(hashes) for layer, hashes in plan_result.removals.items()}
        ...
            for layer in sorted(removals):
# AFTER
        from runtime.application.prune import LAYERS
        removals = {layer: sorted(plan_result.removals.get(layer, ())) for layer in LAYERS}
        ...
            for layer in LAYERS:
```

## APPLY F — story wording matches code (Auditor #6)

**Situation.** Story line 30 specifies converged text `fully converged:
nothing stale, nothing reclaimable`, but the implementation renders `all
layers fresh` / `nothing reclaimable` (tests pin the latter).

**Proposal.** Edit story line 30 to the implemented strings. No code change.

---

## DISMISS X1 — rewrite `except OSError, X:` to parenthesized form (Blind #2)

**Claim.** The comma form "catches only `OSError` and binds the instance to
the name" — i.e. a Python-2-semantics reading.

**Rebuttal (verified, not assumed).** On this repo's interpreter
(`/usr/bin/python3`, 3.14.7): `compile()` accepts the form, and `ast.dump`
shows `ExceptHandler(type=Tuple(elts=[OSError, ValueError]))` — tuple-catch
semantics, exactly what the code intends. Beyond that: the repo convention IS
comma-form (pre-existing `derive.py`, `hashing.py` use it), and `ruff format`
mechanically rewrites parenthesized tuples TO comma-form here (observed when
it reformatted my code) — so the proposed patch would be undone by the
formatter. No change.

## DISMISS X2 — redundant absent-state guard in composition (Blind #4, Edge #2)

**Claim.** `_run_reconcile_plan` should mirror `_run_prune`'s explicit
`load_current() is None` guard instead of relying on `CheckInputsUseCase`.

**Rebuttal.** The situations differ deliberately: prune's use case tolerates
absence by design (3.2), so its composition MUST guard; check's use case
rejects absence by contract (`ValueError`, pinned by 1.3 unit + e2e tests).
Adding a second guard creates two sources of truth for one behavior, and the
e2e `test_absent_state_never_seeds` already pins exit 1 end-to-end. No change.

## DISMISS X3 — snapshot/lock across check+prune reads (Blind #5)

**Claim.** Concurrent `wallpaper set` between the two reads can render an
inconsistent pair; snapshot once / lock.

**Rebuttal.** Directly contradicts the read-only no-lock design both
constituent commands were approved under (1.3 hash-walk-only, prune dry-run
takes no lock): a preview command must never serialize writers. Worst case is
a slightly stale report — never a mutation, never a crash. Documented as
accepted behavior, not a defect. No change.

---

## Item-to-finding index

| Item | Reviewer findings |
|------|-------------------|
| A | Blind #1, Edge #1, Auditor #7 |
| B | Blind #3, Edge #4, Auditor #3 |
| C | Blind #6, Edge #5, Auditor #5 |
| D | Blind #7, Edge #5, Auditor #1/#2/#4/#8/#10 |
| E | Edge #3 |
| F | Auditor #6 |
| Dismiss X1 | Blind #2 (rebutted: verified tuple semantics + convention + formatter) |
| Dismiss X2 | Blind #4, Edge #2 (rebutted: single source of truth + e2e pin) |
| Dismiss X3 | Blind #5 (rebutted: contradicts approved read-only design) |
