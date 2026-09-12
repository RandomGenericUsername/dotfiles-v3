# R‑5: Doctor Store↔History Divergence Detection + Repair

Status: done

baseline_commit: 39aab69

Gate 1: approved (lightweight append; store-wins; absent-history = diverged;
hashes-only projection; `kind="history"` vocabulary). Gate 2: applied —
Items 1–3 (pre-append tail re-verify + test; nine Auditor/Edge coverage
tests; this landing update). Verified: full suite 1039 passed, 2 skipped;
layering green; `make contracts-check` green; ruff/mypy no new issues.

Epic: Phase 5 prerequisite remediation (see `epics-dotfiles-runtime-phase5.md` R‑5;
AD‑41 required capability; Phase 5 spine re-validation H2).

## Story

As the operator,
I want `doctor` to detect and repair `current.json`↔`history.jsonl` divergence,
so a crash between the store save and the history append can never leave the
audit trail silently behind the store — especially once the daemon converges
without a human in the loop.

## Context (the live gap)

AD‑41 claims: *"`doctor` detects and repairs `current.json`↔history
divergence (a required capability, not yet implemented — see remediation
R‑5)."* Today nothing implements it:

- The swap sequence writes the store and the audit trail in **two separate
  steps with a crash window between them**: `reconcile.py` saves
  `current.json` (step 3, inside the seed lock) then appends `history.jsonl`
  (step 4, outside the lock — `O_APPEND` + `fsync` is atomic per line, but
  nothing makes save+append atomic together). `seed_cache.py` has the same
  save-then-append shape (`trigger="seed"`). A kill/crash/power loss in the
  window leaves `current.json` newer than the history tail.
- `DoctorUseCase.check()` compares **store vs symlinks vs cache entries**
  (+ input provenance, + torn-tail tolerance via `heal_torn_history_tail`),
  but it **never reads the history tail**, so this divergence class is
  invisible: `doctor` reports clean while the audit trail disagrees with the
  store.
- `DoctorRepairUseCase` quarantines bad entries and reconverges via
  `reconcile` (which appends a `trigger="doctor"` line), but only when the
  entry/symlink legs are dirty — a pure store↔history divergence triggers no
  repair at all.
- `regenerate` delegates convergence to `reconcile` (covered by the same
  window); `apply` persists `current.json` with no history line **by design**
  (the CLI capstone chains `reconcile` immediately after, which saves again
  and appends) — the detector must not false-positive on that transient.

The Phase 5 daemon's recovery path (converge-on-start, AD‑33/AD‑36) needs a
detector, not a claim: an unrepaired divergence compounds on every automated
converge.

## Acceptance Criteria

1. `doctor` (read-only check) **detects** store↔history divergence: it
   compares the `current.json` content projection against the newest
   `history.jsonl` record and reports a diverged item (clean=false) when
   they disagree; agreement keeps a clean report. (AC 1)
2. Existing history robustness is reused, not re-implemented: corrupt
   middle lines fail loud with the line number, a torn trailing line is
   tolerated, a symlinked `history.jsonl` is refused — all via the existing
   `InspectHistoryUseCase` reader. (AC 2)
3. `doctor --repair` **heals** a pure store↔history divergence by appending
   exactly one `trigger="doctor"` history line reflecting the current store
   (per the Gate‑1 mechanism decision); entry/symlink dirt still takes the
   existing full quarantine+reconverge path (which already appends the
   doctor line). (AC 3)
4. **No false positives:** a machine where `reconcile` just completed stays
   clean; `prune`/`reactive`/`details`-carrying lines compare on content
   hashes only (trigger value and `details` never dirty the verdict);
   timestamp/provenance churn (`applied_at`, `ts`, `source_path`) never
   dirties the verdict. (AC 4)
5. **Locking/layering:** the check stays read-only (no locks, no writes);
   the repair append reuses the locked append-only writer
   (`CacheSeeder.append_history`, AD‑31/AD‑4); domain stays pure, new logic
   lives in `application/` + `adapters/` per AD‑1/13/14. (AC 5)

## Tasks / Subtasks

- [x] Add a store↔history comparison to `DoctorUseCase.check` (new
      `kind="history"` item(s), `ok`/`diverged` vocabulary — absent history
      reports `diverged` per the Gate‑1 rec, so `missing` is unused for this
      kind), reusing `InspectHistoryUseCase` for the tail read (AC: 1, 2, 5)
- [x] Define the comparison projection (4 content hashes only:
      wallpaper/palette/effects/icons, null-aware) (AC: 1, 4)
- [x] Define absent-history-with-store handling (`diverged`) (AC: 1)
- [x] Implement the repair path in `DoctorRepairUseCase` (lightweight
      single `doctor`-line append when entries/symlinks are clean, with a
      pre-append tail re-verify for concurrent converges; full reconverge
      otherwise, or when the seams are absent) (AC: 3, 5)
- [x] Wire CLI output for the new item kind (no change needed — the check
      renderer is generic over items; `_run_doctor_repair` passes
      `seeder.append_history` + `state_repo`) (AC: 1, 3)
- [x] Tests: diverged/absent/stale tail detected; matching tail clean;
      repair appends exactly one `doctor` line (full store payload asserted)
      and re-checks clean; corrupt-middle/symlink loud; torn-tail tolerated;
      prune/reactive/details/source_path lines don't false-positive;
      no-repoint/no-reload pinned; concurrent-converge skips duplicate;
      store-vanished and repair-path-corrupt loud; zero-mutation covers the
      new leg (AC: 1–4)
- [x] Run `uv run --directory src/runtime pytest` + `ruff` + `mypy` + layering
      gate (`tests/architecture/test_layering.py`) + `make contracts-check`

## Dev Notes

- **Where:** `application/doctor.py` owns both legs (check stays in
  `DoctorUseCase`, writers stay in `DoctorRepairUseCase` — the Story 2.2
  separation is preserved). `InspectHistoryUseCase` (`application/inspect.py`)
  is the tail reader; `CacheSeeder.append_history` is the only writer.
- **Precedent:** R‑1 made history schema-enforced; R‑2 single-sourced the
  trigger enum (`domain/history.py:HISTORY_TRIGGERS`); R‑4 enforced
  `current.json` on read. The comparison therefore operates on
  **validated** objects on both sides — no new parsing, no new schema.
- **Authority direction:** the store wins, history is repaired (Gate‑1
  decision 2). This matches the AD‑41 framing and the consistency
  convention that the audit trail follows the store; never rewrite
  `current.json` to match history.
- **No nested locks:** `append_history` locks internally (AD‑31); the
  repair path must not hold `.history.lock` across the call (same
  non-reentrancy rule as R‑1).
- **Out of scope:** the daemon itself (epics 5‑1..5‑4), `reactive` writes,
  backstop records, and any history rewrite/reorder (append-only, AD‑4).

## Gate‑1 sub‑decisions (owner ruling required)

1. **Repair mechanism:** (a) lightweight — pure history divergence appends
   one `doctor` line with no repopulate/repoint/reload *(recommended:
   cheapest, no desktop side-effects for an audit-only gap)* vs (b) always
   full reconverge (reuses the proven path, but repoints symlinks and
   reloads the desktop for a gap that needs none of it)?
2. **Authority direction:** store authoritative, history repaired
   *(recommended, per AD‑41)* vs history authoritative?
3. **Absent history + present store:** report `diverged` *(recommended —
   the store has state the audit trail never recorded)* vs a softer
   `missing`/informational status?
4. **Comparison scope:** the 4 content hashes only
   (wallpaper/palette/effects/icons, null-aware) *(recommended)* vs also
   `source_path` / monitors / timestamps?
5. **Item vocabulary:** new `kind="history"` item(s) with
   `ok`/`diverged`/`missing` statuses (mirrors entry/symlink legs) — confirm,
   or prefer a different shape for the CLI contract?
