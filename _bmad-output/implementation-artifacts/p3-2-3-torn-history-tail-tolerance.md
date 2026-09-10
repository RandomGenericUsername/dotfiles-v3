# Story 2.3: Torn-History-Tail Tolerance (AD-23)

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 2 — Doctor Drift Detection + Repair (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 2.3)

## Story

As a user,
I want history readers to survive a torn trailing line and only `doctor --repair`/the writer to heal it,
so that one short write never bricks every history consumer.

## Key design decision (AD-23 interpretation — Gate 1 review)

AD-23 says "only `doctor --repair` may truncate/quarantine the torn tail." The
2026-09-10 Gate-2 of Story 2.2 exposed a hard interaction: **any** append over
a torn tail — with or without a newline prefix — produces a non-JSON line
followed by content, which readers correctly treat as loud MIDDLE corruption
(bricking them). Story 2.2's `append_history` newline guard is therefore
insufficient and must be replaced.

Ratified interpretation: read commands (`doctor` check, `inspect history`)
NEVER mutate; the **writer** (`append_history`, the sole history writer per
rt-2-7) self-heals a torn tail before appending, and `doctor --repair` heals it
explicitly (even when otherwise clean). Both route through one adapter method.
This satisfies AD-23's intent ("one short write never bricks consumers") and
its invariant (plain checks never mutate). The writer-contract item in `Deferred`
(multi-`write(2)` interleave) stays accepted.

## Acceptance Criteria

1. Any history reader tolerates a non-JSON trailing line (skip + warn), reports clean otherwise, and never crashes (AC 1, FR-7/AR-4) — the existing `InspectHistoryUseCase` behavior, re-verified as the reader contract
2. `dotfiles-runtime doctor --repair` heals a torn trailing line: the raw pre-heal bytes are preserved in quarantine, the live file is truncated to the last complete newline, and the machine reports repaired (AC 2, AD-23)
3. Plain `doctor` (no `--repair`) and `inspect history` never mutate `history.jsonl` — a torn tail survives them byte-for-byte (AC 3, AD-23)
4. Writing a new history line over a torn tail is safe: the writer heals the tail first, then appends, so the resulting log is fully parseable (no middle corruption) (AC 4)
5. The writer's append-only guarantee is preserved: complete lines are never rewritten, only the incomplete trailing bytes are dropped; the quarantine copy is byte-identical to the pre-heal file (AC 5, AD-4)

## Tasks / Subtasks

- [x] Add `heal_torn_history_tail() -> Path | None` to `src/runtime/src/runtime/adapters/seeder.py` (AC: 2, 3, 5)
  - [x] Read `history.jsonl` bytes read-only; return `None` when: absent/empty, ends with `\n`, trailing bytes after the last `\n` are blank-only, or the trailing bytes already parse as JSON (complete-but-unterminated — not torn)
  - [x] Torn case: copy the ENTIRE pre-heal file to `cache/.quarantine/history-<UTCstamp>-<pid>.jsonl` (parent created; collision-safe suffix), then truncate the live file to the last `\n` (drop only the partial trailing bytes)
  - [x] Never `rm` the file; complete lines are preserved exactly; idempotent (second call → `None`)
  - [x] Return the quarantine path (for reporting)
- [x] Replace Story 2.2's newline guard in `append_history` with a pre-append `heal_torn_history_tail()` call (AC: 4)
  - [x] Heal BEFORE `os.open(..., O_APPEND)`; the guard's `\n`-prefix block is removed (it converts a tolerable torn tail into loud middle corruption)
  - [x] Append remains O_APPEND + fsync + short-write loop; writer contract otherwise unchanged
- [x] Heal in `DoctorRepairUseCase.repair()` (AC: 2, 3)
  - [x] Ctor gains `heal_history_tail: Callable[[], Path | None]`; `RepairResult` gains `history_tail_quarantined: Path | None`
  - [x] Call `heal_history_tail()` at the START of `repair()` (before the clean short-circuit). If state is clean and no entry drift but a tail was healed, return a repaired result with `history_trigger=None` + `history_tail_quarantined=<path>` (no reconcile needed)
  - [x] Existing drift path unchanged (quarantine entries → reconcile `trigger=doctor`); its append now runs on a healed log
- [x] Wire CLI (`main.py`): pass `heal_history_tail=lambda: seeder.heal_torn_history_tail()`; render the tail-heal in plain + JSON (`history_tail_quarantined`); `already clean` only when neither drift nor tail heal occurred (AC: 2, 3)
- [x] Create `src/runtime/tests/unit/test_history_tail_repair.py` (AC: 1–5)
  - [x] `heal_torn_history_tail`: torn tail → returns path; live file ends with `\n`; complete lines byte-identical; quarantine copy byte-identical to pre-heal; second call → `None`
  - [x] Non-torn cases → `None` and file untouched: absent, empty, trailing blank line, complete-but-unterminated JSON line
  - [x] `append_history` over a torn tail → heals then appends; every resulting line parses (count == complete_lines + 1); no middle corruption
  - [x] `doctor --repair` with torn tail on an otherwise clean machine → healed + reported; exactly zero history lines appended
  - [x] `doctor --repair` with torn tail + entry drift → tail healed, exactly one `doctor` line, full log parseable
  - [x] Plain `doctor` and `inspect history` on a torn-tail file → exit 0/clean, `history.jsonl` byte-identical (mutation pin)
  - [x] `inspect history` after heal → full count, no torn warning
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_history_tail_repair.py tests/unit/test_inspect_history.py tests/unit/test_doctor_repair.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — torn-tail only

- No reader semantics change (`InspectHistoryUseCase` already tolerates; add tests, don't rewrite)
- No eviction/prune (Story 3.x)
- No writer atomicity redesign (arch Deferred: multi-`write(2)` interleave accepted)

### Layering (AD-25, locked)

- Healing I/O lives in `adapters/seeder.py`; `DoctorRepairUseCase` receives it as an injected callable (no adapter import in `application/` except the existing allowlisted `adapters.hashing`); CLI composes.
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed

1. History is the sole-writer domain of `CacheSeeder.append_history` (rt-2-7) — healing belongs there.
2. Quarantine layout `cache/.quarantine/` (Story 2.2); history quarantine files live at its root.
3. Reader torn-tail rule: non-JSON + no newline + nothing non-blank after → skip+warn; anything else corrupt → loud.

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-2-3-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; ~18 findings). Operator verdicts
per-item ballot: apply A–G, dismiss X1–X2 confirmed.

Applied:
- A (blocker, reproduced): a complete-but-unterminated JSON record is now terminated (newline restored), not merged into the next append; non-object JSON scalars are treated as torn. The previous behavior concatenated two records into one unparseable line (reader `Extra data`).
- B: heal refuses a symlinked `history.jsonl` (mirrors writer O_NOFOLLOW / reader refusal).
- C: dedicated `flock` (`state_root/.history.lock`) serializes heal + append; heal-in-append uses a locked private helper (AD-4 must-not-lose).
- D: quarantine copy written from the same `raw` bytes (no second-read race); tmp preserves the original mode via `chmod`; `finally` unlink guarded.
- E: heal `OSError` in repair wrapped as typed `RuntimeError`.
- F: tests — append-over-unterminated, plain-doctor no-mutation pin, drift+tail full-log parse, CLI tail render.
- G: AD-23 + AR-4 amended to the ratified writer-self-heal interpretation; story boxes + this record.

Dismissed:
- X1 required `heal_history_tail` param — breaks the DONE 2.2 ctor; CLI always wires it.
- X2 stream large torn tails — a tail is one partial record; whole-file read only on the rare torn path.

Verification: 693 unit/architecture + 68 integration passed, ruff + format
clean (only pre-existing B008), mypy strict clean on seeder.py + doctor.py.
