# R‑1: Prune History Audit Line

Status: done

baseline_commit: 6d41feb

Gate 1: approved (option A — optional `details`). Gate 2: applied — A1 document `failed`; A2 log every real run (AD‑30 literal); A3 catch `(OSError, ValueError)` and still write; A4 report both; B `allow_nan=False`; **C → schema-driven (owner choice (b))**: the history line is enforced by `contracts/schemas/history.schema.json` (embedded in the runtime, validated in the reader via fastjsonschema); D robustness tests; E1 reconciled the seeder caller note.

Epic: Phase 5 prerequisite remediation (Phase 4 defect) — see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md` (R‑1).

## Story

As the operator,
I want every real `cache prune` to append exactly one auditable `history.jsonl` line,
so that automatic and manual deletions are traceable (AD‑30) — especially once the
reactive daemon can prune without a human in the loop.

## Context

AD‑30 requires: *"Every real prune execution appends exactly one `history.jsonl`
line with `trigger="prune"` and counts; dry-run appends nothing."* It was never
implemented: `append_history` is called only from `reconcile.py` and
`seed_cache.py`; the prune path writes no history. Two obstacles:

1. `_VALID_HISTORY_TRIGGERS` (`application/inspect.py:71`) does **not** include
   `prune`, so a `prune` line would be rejected by the reader.
2. The history line schema pins **exactly 7 keys** (`_HISTORY_FIELDS`:
   `ts, trigger, wallpaper, palette, effects, icons, source_path`) and the reader
   raises on any key mismatch — so there is **nowhere to put counts** today.

## Acceptance Criteria

1. A **real** (non-dry-run) `inspect cache prune` appends exactly **one** `history.jsonl` line with `trigger="prune"`; `--dry-run` appends **nothing**. Prune's existing behavior (plan, removal, output) is otherwise unchanged. (AC 1)
2. The appended line is **schema-valid and readable**: the `inspect` history reader accepts it without error, and `prune` is part of the single-sourced trigger enum (coordinates with R‑2 — R‑1 adds the value; R‑2 owns the single-sourcing). (AC 2)
3. The line records **what was reclaimed** (total and per-layer counts) per the Gate‑1 mechanism decision (see below). (AC 3)
4. The append reuses the existing **locked, append-only** writer (`CacheSeeder.append_history`, AD‑31 / AD‑4); a failure to append is **surfaced** (never silently swallowed), and no partial/half line is ever produced. (AC 4)

## Gate‑1 mechanism decision (owner ruling required)

The 7-key schema cannot carry counts. Choose:

- **(A) Optional `details` object (recommended).** Extend the history line with an
  optional `details` map carrying trigger-specific data (`{removed: N, layers: {...}}`).
  Requires: shared-data-contract update + reader accepts an optional `details` key
  (lenient-unknown handling for that one field) + the R‑4 machine-enforced schema.
  Honors AD‑30's "with counts"; sets the pattern for future trigger data.
- **(B) Log-only counts.** Append a schema-valid prune line carrying the current
  post-prune state hashes; record counts in the structured log. No schema change,
  but AD‑30's "in history" is unmet.

## Tasks / Subtasks

- [ ] Add `prune` to the trigger enum (single-sourced once R‑2 lands; transiently in the validator) (AC: 2)
- [ ] Implement the append in the real-prune path only (compose through `_run_prune`; dry-run returns before any append) (AC: 1)
- [ ] Record reclaimed counts per the Gate‑1 choice; if (A), extend the history schema + reader + contract (AC: 3)
- [ ] Reuse `append_history` (locked, append-only); surface append failure (AC: 4)
- [ ] Tests: real prune appends one `prune` line (readable by the inspect reader); dry-run appends none; counts/fields correct; append-failure surfaced (AC: 1–4)
- [ ] Run `uv run --directory src/runtime pytest` + `ruff` + `mypy`; run `test_layering.py`

## Dev Notes

- **Locking:** `append_history` already takes `.history.lock` (AD‑31). The prune
  path must **not** hold the lock itself — call `append_history` and let it lock
  (no nested acquisition; see the Phase 5 spine's non-reentrancy rule).
- **Reader leniency:** today the reader enforces exact keys. If (A) is chosen,
  the reader must tolerate the optional `details` key while still rejecting truly
  unknown keys — and R‑4 makes that schema machine-checked.
- **Shared data contract:** a history-schema change is a shared-contract change
  (AD‑44) — update the machine-checkable definition and its drift test in the
  same change.
- **Out of scope:** the daemon, the reactive trigger, and R‑2's broader
  single-sourcing (R‑1 only needs `prune` accepted).

## Open question for Gate‑1

Mechanism **(A)** optional `details` object, or **(B)** log-only counts? Recommendation: **(A)**.
