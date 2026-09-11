# Gate 2 Review — Story p4-3-3 (History Append Lock)

Status: APPLIED — all items approved and implemented. Full suite 954 passed, 2 skipped; mypy clean; ruff clean.

## Applied

- Item A: append open/write + lock `mkdir`/`close` mapped to typed errors; `doctor.py` catches `(OSError, HistoryLockError)`; writer-level test (`history.jsonl` as dir).
- Item B: lock mode `0o600`; messages name operation (acquire / append open / append write).
- Item C: torn-tail heal-under-contention test, cross-process blocking waiter, output validated via `InspectHistoryUseCase`; symlinked-history test updated to typed error.
- Item D1: internal construction ratified (documented in story).
- Item D2: uniform seed mapping ratified (documented in story).
- Item E: dead `fd=None` removed; port `__all__` narrowed to `IHistoryMutex`; thread-exception-swallowing test replaced by process-exitcode check.

---

## Original review (pre-apply)

## Verification (pre-review, all green)

- New tests: `tests/unit/test_history_lock.py` — 3 passed (incl. 4 procs × 25 appends lossless).
- Full suite: 952 passed, 2 skipped. `mypy`: clean. `ruff`: only pre-existing `models.py:35` E501.
- Regression subset `-k "history or torn or seed_pin"`: 105 passed (per auditor).

## Context confirmed pre-dev (shapes this review)

Phase 3 already built a `.history.lock` blocking-flock around heal+append, inline and untyped. This story generalizes the mechanism, types the errors, and proves concurrency. ACs still bind as written.

## Review panel findings (3/3 reporting — patches required)

### Item A — Untyped failure paths (Blind Hunter BUG 2+3, Edge 7+11 agree)

**Problem (full):** Three `OSError` sources escape the typed contract: (a) `os.open`/`os.write`/`os.fsync` on `history.jsonl` inside the lock (`seeder.py:850-859`) — a directory-at-path, ENOSPC, or EACCES propagates raw, violating AC2's "acquire/append → HistoryLockError"; (b) `lock_path.parent.mkdir` in `_acquire` sits outside the `try` (raw `OSError` next to mapped `open`/`flock` — two error domains for adjacent syscalls); (c) `doctor.py:289-292` catches only `OSError` around heal, so the newly-typed heal failures bypass the `"history tail heal failed"` wrap (message regression, CLI still exits 1).

**Proposed patch:** wrap append open/write/fsync + `mkdir` into `make_error` mapping (uniform domains); `doctor.py` catches `(OSError, HistoryLockError)` preserving the wrap. Plus writer-level test (`history.jsonl` as a directory → `HistoryLockError`, no deadlock since it fails before blocking).

### Item B — Lock mode + message wording (Blind Hunter BUG 1 + edge 3)

**Problem (full):** Story task pins `0o600` (mirror seed lock); code carries forward pre-existing `0o644`. Either choice is defensible — but a choice must be made and the task checkbox ticked honestly. Note: `os.open` mode applies at creation only; existing Phase 3 `0644` files keep their mode regardless (verified — harmless drift either way, nothing reads lock files). Message `"history lock unavailable: {p}"` names path but not operation (task requires both).

**Proposed patch (recommended):** follow the task — drop the override (inherit `0o600`); message becomes `f"history lock {op} failed: {p}"`-shaped (operation threaded through the factory: acquire vs append context).

### Item C — Contention tests prove the wrong things (Auditor AC4 gaps + Blind Hunter BUG 4 + heal race)

**Problem (full):** (a) The 4×25 test appends to a clean file — heal is a fast no-op every time, so the suite would pass with NO lock (sub-PIPE_BUF `O_APPEND` writes are already atomic); the actual race (heal's `os.replace` vs append's fd) is untested. (b) The blocking waiter proof is threads-only; flock is cross-process — threads don't prove it. (c) Output validated with raw `json.loads`, not the repo's history reader/torn-tolerant parser as tasked. (d) The lock-held test targets the mutex, not `append_history` (which would hang by design) — resolved by Item A's writer-level test instead.

**Proposed patch (tests only):** seed a torn tail + run a healer process concurrently with appenders (assert healed + lossless); convert the waiter proof to processes (holder proc + appender proc with timeout-guarded join); validate the 100-line output through the existing history reader.

### Item D — Deviations to ratify (Auditor)

1. **No ctor plumbing** (story suggested required `history_mutex` param): lock constructed internally at both sites; zero call-site churn, single-writer invariant makes it safe. Cost: hidden dependency, uninjectable. Ratify as-built + document, or require injection.
2. **Seed open-error mapping**: generalization maps seed lock-file open failures to `SeedLockedError` (previously raw `OSError`), which the CLI logs as "skip quietly" instead of "seeding failed". Uniformity vs semantic precision — pre-existing port contract only knows one error. Ratify uniformity, or split error types (follow-up story scope).

### Item E — Cleanups (Blind Hunter minors)

Dead `fd: int | None = None` leftover (`seeder.py:847`); `HistoryLockError` in port `__all__` inviting split import canon (remove, keep canonical `domain.models` import); blocking-waiter test swallowing thread exceptions (capture `exc_info`).

## Ballot (vote Approve / Request changes PER ITEM in chat)

- Item A (typed paths + doctor catch + writer test)?
- Item B (0o600 + operation in message)?
- Item C (heal-race + cross-process waiter + reader validation)?
- Item D1 (ratify internal construction)?
- Item D2 (ratify uniform seed mapping, split is follow-up)?
- Item E (cleanups)?
