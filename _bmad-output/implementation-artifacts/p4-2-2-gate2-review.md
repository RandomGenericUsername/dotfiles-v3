# Gate 2 Review — Story p4-2-2 (Actual-State Projection)

Status: DEV done, awaiting patch decisions. NOTHING APPLIED — no code changed since verification.

## Verification (pre-review, all green)

- New tests: `tests/unit/test_actual_state.py` — 5 passed.
- Story + layering: + `tests/architecture/test_layering.py` — 75 passed.
- Full suite: 909 passed, 2 skipped (pre-existing skips).
- `ruff check` on story files: clean (`models.py:35` E501 pre-existing, untouched).
- `ruff format`: applied to story files; post-format tests re-run green.

## Review panel findings (3/3 reporting; Auditor: ACCEPT, no scope creep)

### Item 1 — `seed_pins()` invoked twice, divergence risk (Blind Hunter + Edge Hunter agree: BUG)

**Problem (full):** `application/actual_state.py:56` calls `seed_pins()` for the `pinned_hashes` snapshot, then line 69 passes the raw `seed_pins` callable into `PruneUseCase`, which calls it again (`prune.py:59`). `pinned_hashes` and `prunable_hashes` can derive from different pin sets if the callable is counting, expensive, or non-idempotent (the real adapter reads disk). Tests mask it with `lambda: PINS` (pure constant).

**Proposed patch** (memoize once, pass the snapshot — single invocation, single policy source):
```python
    refs_by_layer = {layer: list(entries_for(layer)) for layer in LAYERS}
    pins_snapshot = seed_pins()
    pins = pins_snapshot
    ...
    plan = PruneUseCase(
        _LoadedStateRepository(current),
        lambda layer, _c=refs_by_layer: list(_c[layer]),
        lambda: pins_snapshot,
        keep,
    ).run()
```
(This also folds Blind Hunter B3: the lambda captures the cache by default-arg instead of late-binding the mutable name.)

### Item 2 — `keep < 0` performs I/O before raising (Blind Hunter: contract-level)

**Problem (full):** `entries_for` (4 calls) + `seed_pins` execute at lines 55-56 before `PruneUseCase.__init__` raises `ValueError` on `keep < 0` (`prune.py:45-46`). Validation is delegated but not fail-fast — a failing call still triggers adapter side effects. Test `test_negative_keep_raises` does not assert zero calls.

**Proposed patch** (construct the use case BEFORE listing — `__init__` validates without invoking callables, so no rule is duplicated):
```python
def build_actual_state(...):
    usecase = PruneUseCase(
        _LoadedStateRepository(current),
        lambda layer: refs_by_layer[layer],
        _memo_pins,   # or lambda: pins_snapshot per Item 1
        keep,         # raises here on keep < 0, before any listing
    )
    refs_by_layer = {layer: list(entries_for(layer)) for layer in LAYERS}
    ...
    plan = usecase.run()
```
Do NOT add `if keep < 0: raise` — that would create a second source for the rule (AC 3).

### Item 3 — Test hardening, no src change (Acceptance Auditor gaps + hunters' asserts)

**Problem (full):** Implementation correct, tests under-prove it: (a) `_monitors()` inserts `DP-1`,`HDMI-1` already sorted, so the `sorted()` call is unproven — no unsorted-input case; (b) single pin proves nothing about pin sorting (undated sorting IS proven with 2 elements); (c) `ActualState` frozen-immutability never asserted; (d) no `seed_pins` call-count assert (would have caught Item 1); (e) no zero-`entries_for`-calls assert on `keep < 0` (would have caught Item 2).

**Proposed patch** (tests only):
- `_monitors()` inserts `HDMI-1` before `DP-1`; expectation stays `("DP-1", "HDMI-1")`.
- Second pin in another layer (`effects`), asserting global sorted order.
- `test_model_is_frozen`: mutating any field raises `FrozenInstanceError`.
- Counting `seed_pins` fake; assert exactly 1 call per build.
- `keep=-1` test asserts `entries.calls` all zero.

## Ballot (vote Approve / Request changes PER ITEM in chat)

- Item 1 (memoize `seed_pins` + capture lambda)?
- Item 2 (construct-before-listing fail-fast)?
- Item 3 (test hardening additions)?
