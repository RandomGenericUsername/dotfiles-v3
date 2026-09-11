# Gate 2 Review — Story p4-3-4 (Auto-Check Inputs on `wallpaper set`)

Status: APPLIED — all items approved and implemented. Full suite 966 passed, 2 skipped; ruff/mypy clean of new issues.

## Applied

- Item 1: `inputs_check_error` key added; set on typed and unexpected failure branches (empty lists now unambiguously "checked fresh"). AC1 amended.
- Item 2: `--format json` tests for stale (inputs_stale/inputs_fresh/error None), fresh, and failure (error populated).
- Item 3: `ValueError`/`RuntimeError` parametrized, generic `KeyError` (unexpected branch), all-stale `(fresh: none)` tests.

---

## Original review (pre-apply)

## Verification (pre-review, all green)

- New tests: `tests/unit/test_cli_wallpaper_set_autocheck.py` — 5 passed.
- Full suite: 959 passed, 2 skipped. Layering 73 passed, unmodified.
- `ruff`: only pre-existing B008 ×2. `mypy`: only pre-existing (stubs + `sections` redef). Format clean.
- Auditor verdict: production code satisfies AC1–AC4, no scope creep; rework is test-only + object-surface ambiguity.

## Review panel findings (3/3 reporting — patches required)

### Item 1 — Check failure is invisible in the object/JSON surface (Blind Hunter B1 + Auditor AC4 hole + Edge 10)

**Problem (full):** `obj` initializes `inputs_stale`/`inputs_fresh` to `[]`, and the failure branches never mark anything. The JSON renderer emits only `view.object`, so the appended `"inputs check failed"` line (summary-only) is discarded. A machine consumer sees `inputs_stale: []` / `inputs_fresh: []` — indistinguishable from "all fresh". Three states (fresh, check-failed, never-ran) are overloaded onto one empty-list shape; the story's "never swallowed silently" is violated in the structured view.

**Proposed patch:** add `"inputs_check_error": None` to `obj`; set it to `str(exc)` (typed branch) / a generic message (unexpected branch). Empty lists then unambiguously mean "checked and fresh". (Alternative `None` sentinel for stale/fresh also works, but an explicit error key is less disruptive to consumers.)

### Item 2 — Object view never asserted; mandated by the story task (Blind Hunter B2 + All three agree)

**Problem (full):** All 5 tests assert plain strings. `story:29` explicitly requires asserting object `inputs_stale` populated, and AC1 names the object surface. Stale/fresh object population is completely unverified.

**Proposed patch (tests):** add `--format json` tests — stale path asserts `inputs_stale == ["palettes"]`, `inputs_fresh == ["effects","icons"]`; fresh path asserts empty stale/fresh; check-failure path asserts `inputs_check_error` populated. (Requires `import json`.)

### Item 3 — Failure-branch coverage only exercises `OSError` (Edge 2, 4 + Auditor gap 2)

**Problem (full):** The `(ValueError, RuntimeError)` branch and the broad `except Exception` branch are untested; the all-stale `fresh_desc == "none"` path is untested. A `typer.Exit` (subclass of `RuntimeError`) would be demoted to a warning — arguably AC4-intended for a sub-check, but currently accidental and unasserted.

**Proposed patch (tests):** add `ValueError` and `RuntimeError` failure cases (assert exit 0 + warning line), a generic non-typed raise (e.g. `KeyError`) case, and an all-stale case asserting `(fresh: none)`.

### Advisory (no patch this story): redundant hash work

`_run_check_inputs` re-walks/hashes templates, catalog, icon templates, mappings immediately after apply already derived them. Correctness-neutral (read-only), but real cost on every successful set. Out of scope here; note for a future perf pass.

## Ballot (vote Approve / Request changes PER ITEM in chat)

- Item 1 (`inputs_check_error` object key on failure)?
- Item 2 (JSON object-view tests)?
- Item 3 (ValueError/RuntimeError/generic/all-stale branch tests)?
