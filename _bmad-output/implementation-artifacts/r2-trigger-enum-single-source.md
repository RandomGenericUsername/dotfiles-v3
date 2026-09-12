# R‑2: Single‑Source the History Trigger Enum

Status: done

baseline_commit: eac14b7

Gate 1: approved (keep `force` reserved). Gate 2: applied — Items 1–4 (docstrings point at the source; test noise reverted; drift gate covers the embedded copy + symbol identity; error-message test, `repo_root` fixture, comment reword).

Epic: Phase 5 prerequisite remediation (see `epics-dotfiles-runtime-phase5.md`).

## Story

As a maintainer,
I want the history trigger enum defined once,
so the runtime can never again reject a trigger on one path that another path accepts
(the defect the schema prototypes caught).

## Context (the live defect)

The trigger enum is **duplicated**, and they already disagree:
- `application/reconcile.py:68` — `_VALID_TRIGGERS` = `seed,set,reconcile,force,regenerate,doctor` (**missing `prune`**; R‑1 added `prune` to history, so `reconcile` would reject it)
- `application/inspect.py` — `HistoryTrigger` `Literal` = 7 values (incl. `prune`)
- `contracts/schemas/history.schema.json` — `trigger.enum` = 7 values
- `adapters/seeder.py` — the enum is described in a docstring (prose)

AD‑44 says **enums are one code constant**. This story makes that true.

## Acceptance Criteria

1. One **pure domain constant** owns the accepted trigger values (no other Python copy). (AC 1)
2. `application/reconcile.py` and `application/inspect.py` reference that constant; `reconcile.py`'s private `_VALID_TRIGGERS` is deleted, and `reconcile` accepts `prune` — the live defect is fixed. (AC 2)
3. The `HistoryTrigger` `Literal` and the history JSON Schema's `trigger.enum` **both equal the constant**, enforced by an **executable** drift test (no prose). The schema's canonical copy and its embedded runtime copy stay byte‑identical (existing conformance test). (AC 3)
4. No behavior change for existing triggers: every value previously accepted by either path is still accepted, and historical lines still parse. (AC 4)

## Tasks / Subtasks

- [ ] Add the pure constant (e.g. `runtime/domain/history.py:HISTORY_TRIGGERS: tuple[str, ...]`) (AC: 1)
- [ ] Point `reconcile.py` and `inspect.py` at it; delete `reconcile.py`'s `_VALID_TRIGGERS` and its `valid = ...` message rework (AC: 2)
- [ ] Update `contracts/schemas/history.schema.json` enum + re‑copy into `runtime/adapters/schemas/` (byte‑identical) (AC: 3)
- [ ] Drift tests: constant == `get_args(HistoryTrigger)` == the schema's `trigger.enum` (executable) (AC: 3)
- [ ] Test: `reconcile` now accepts `prune` (the fixed defect); existing values unchanged (AC: 4)
- [ ] Run `uv run --directory src/runtime pytest` + `ruff` + `mypy` + `test_layering.py`

## Dev Notes

- **Where:** domain (pure, no I/O). `application/` and `adapters/` may import it; the `Literal` lives where typing needs it but must be asserted equal to the constant.
- **Schema is not the source here.** Per AD‑44, enums are a code constant; the schema consumes it and a drift test pins them together. (For the *wire* contract the source is XML — different contract type.)
- **`reactive`:** AD‑42 includes `reactive` (the daemon's trigger) in the enum. No writer exists yet; accepting it ahead of the writer is intended.
- **`force` (Gate‑1 sub‑decision):** the enum historically included `force`, which nothing writes. Keep it **reserved** (recommended — dropping it would make the reader reject any historical `force` line), or drop it if we confirm none exist.

## Gate‑1 sub‑decision

Keep `force` as a reserved (accepted, unwritten) value (recommended), or drop it?
