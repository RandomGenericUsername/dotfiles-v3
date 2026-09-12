# Gate 2 Review — R‑1 (Prune History Audit Line)

Status: APPLIED — all items resolved and verified (981 passed, 2 skipped; ruff/mypy no new; layering green).

## Applied

- **A1** `failed` documented in `shared-data-contract.md` + the schema.
- **A2** kept AD‑30 literal — a real prune logs a line even with `removed: 0` (owner ruling; overrides the re-validation's "iff deleted").
- **A3** removal loop catches `(OSError, ValueError)` and still writes the audit line.
- **A4** an append error no longer masks a removal-failure report (both reported).
- **B** `json.dumps(..., allow_nan=False)` — non-finite details fail loud, never write invalid JSON.
- **C → schema-driven (owner chose b).** `contracts/schemas/history.schema.json` (draft‑07) is the single machine-checkable definition; an embedded copy under `runtime/adapters/schemas/` is enforced by the reader via `fastjsonschema` and kept byte-identical by the conformance test. The reader's hand-written field checks were removed.
- **D** tests: real-writer failure (history.jsonl as a dir), lock-order guard, CLI history JSON round-trip, `seed_pins` tolerance, missing-required-with-details, `details` value types, non-finite details.
- **E1** `seeder.append_history` caller note reconciled (CLI composition root may append an explicit audit line).

---

## Original review (pre-apply)

## Verification (pre-review)

- New/changed tests green: prune + history suites 55 passed; full suite **972 passed, 2 skipped**.
- `ruff`: only pre-existing B008 (main.py:190/306). `mypy`: only pre-existing (models.py:30, actual_state.py:71, cli_output stubs, `sections` redef). Layering 73 passed.
- Panel: Blind Hunter = patches required; Edge Hunter = 3 top fixes; Acceptance Auditor = **ACCEPT** (all 4 ACs) with follow-ups.

## Findings

### Item A — failure-path + no-op semantics (Blind Hunter B1/B2/B3 + Edge Hunter)

**Problem (full):** four coupled defects on the prune→audit path:
1. **Undocumented `failed` key.** `main.py` writes `details["failed"]` when a removal errors, but the shared-data-contract prose (edited in this same change) pins only `{removed, layers}` — self-inflicted AD‑44 drift.
2. **No-op real prune appends a line.** The append is unconditional, so an idempotent second `cache prune` writes `{"removed":0,"layers":{}}`. This contradicts the re-validation ruling (`reviews/reval-adversarial.md:229-231`): the `prune` line is emitted **iff at least one entry was deleted** (a line for a prune that didn't execute "corrupts exactly the audit trail R-1 exists to protect"). It also conflicts with AD‑30's literal "every real prune execution appends one line" — so this is a decision, not just a fix.
3. **Mid-prune `ValueError` skips the audit line.** `remove_entry` raises `ValueError` on every validation branch (`prune_source.py:151-179`), but the loop catches only `OSError` (`main.py:1746`) — a validation failure propagates out before `_append_prune_history`, so a partially-completed prune writes **zero** audit lines (AC1 violation).
4. **Append failure masks the deletion-failure report.** `_append_prune_history` runs *before* the `if failures: raise RuntimeError` (`main.py:1751-1755`); if the append raises, the removal-failure RuntimeError is lost.

**Proposed patch:**
- Gate the append on real work: `if removed or failures: _append_prune_history(...)` (no line for a true no-op). Amends AC1 to "a real prune that deletes ≥1 entry **or** hits a removal failure appends exactly one line; a no-op real prune and dry-run append nothing."
- Catch `(OSError, ValueError)` in the removal loop.
- On append failure, do not mask: capture the append exception and raise a combined error (or re-raise the deletion-failure with the append failure noted); never lose the "deletions happened, un-audited" fact.
- Document `failed` in `shared-data-contract.md` (and R‑4's schema) **or** drop it; if kept, it only appears on a failures run.

### Item B — `json.dumps` emits invalid JSON for NaN/Infinity (Edge Hunter)

**Problem (full):** `seeder.append_history` uses `json.dumps(record, ensure_ascii=False)` with default `allow_nan=True`; a non-finite float in `details` writes a bare `NaN`/`Infinity` — invalid strict JSON that other consumers (jq, other languages) reject, while Python's reader silently tolerates it. Pre-existing, but the new `details` path makes it reachable.

**Proposed patch:** `json.dumps(record, ensure_ascii=False, allow_nan=False)` (turns it into a surfaced `ValueError`).

### Item C — `details` value types unvalidated (Edge Hunter M3)

**Problem (full):** the reader validates that `details` is a dict of string keys but not the values; the contract pins `removed`/`failed` as `<int>` and `layers` as `str→int`, yet a hand-edited `{"removed":"lots"}` passes and breaks arithmetic consumers.

**Proposed patch:** validate value types in `_parse_record` (`removed`/`failed` int ≥ 0; `layers` object of str→int), or explicitly defer to R‑4's machine schema. Recommended: validate now — it's cheap and the contract already pins the types.

### Item D — test hygiene (Blind Hunter M4/M5/M6 + Edge)

**Problem (full):** (a) the append-failure test monkeypatches `CacheSeeder.append_history` (the brittle-mock anti-pattern flagged in `deferred-work.md`); (b) no test asserts the append happens outside `.seed.lock` (a future refactor folding it inside would deadlock under non-reentrant flock, uncaught); (c) no round-trip test through `inspect history`'s structured CLI output; (d) no test that `seed_pins` tolerates a preceding `prune`+`details` line; (e) no "missing required key + `details` present → reject" case.

**Proposed patch:** add those five tests; prefer exercising the real writer's failure path over the mock.

### Item E — stale `seeder` invariant "never called from the CLI" (Acceptance Auditor)

**Problem (full):** `seeder.py:812-814` documents the rt-2-7 invariant: `append_history` is called through Reconcile/Seed, **never from the CLI**. R‑1 now calls it from the CLI (`main.py:1777`). The mechanical layering guard passes, but a documented invariant is now false.

**Options:** (E1) reconcile the docstring to allow the **CLI composition root** to append an explicit audit line (the CLI already composes adapters); (E2) route the append through an application seam (e.g. a `PruneUseCase` method) to preserve the invariant strictly. Recommended **E1** (the prune audit is a composition-root action, not hidden derivation logic).

## Not in R‑1 (R‑2/R‑4 own)

- `force`/`reactive` contract-prose drift; enum single-sourcing; the R‑4 machine schema + drift test.

## Ballot (vote Approve / Request changes PER ITEM)

- Item A (failure-path + no-op semantics + `failed` key)?
- Item B (`allow_nan=False`)?
- Item C (validate `details` value types)?
- Item D (five tests)?
- Item E (E1 docstring reconcile, or E2 use-case seam)?
