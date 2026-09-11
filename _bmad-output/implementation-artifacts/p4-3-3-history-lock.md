# Story 4.6: History Append Lock (AD-31)

Status: ready-for-dev

baseline_commit: 2311733

Epic: Phase 4 backlog sibling (Gate 1 ruling on p4-3-2, option b). Implements AD-31 (`architecture-2026-09-11`).

## Story

As a user running `wallpaper set` while `reconcile` runs,
I want every `history.jsonl` append serialized through one OS-level file lock,
so concurrent writers never interleave or lose history lines.

## Acceptance Criteria

1. Exactly one lock guards all appends: `state_root/.history.lock` (POSIX `flock`, kernel-owned — auto-released on holder death, no stale-lock cleanup). Every `history.jsonl` writer routes through it; post-story grep for unlocked append paths is clean (AC 1)
2. Lock acquisition is BLOCKING with bounded critical section (append path is ms-scale; a concurrent CLI waits instead of failing — failing a `wallpaper set` over a millisecond-held lock is wrong UX). Lock/OS failures surface as typed `HistoryLockError` (`RuntimeError` subclass, mirroring `SeedLockedError` precedent), never a hang without cause and never a silent skip (AC 2)
3. Mechanism is not duplicated: either generalize `FlockSeedMutex` (lock path + error factory injected; existing `.seed.lock` call sites migrate) or prove duplication cheaper — do NOT run two divergent flock implementations (AC 3)
4. Concurrency is proven, not asserted: a test with contending appenders (threads AND processes — flock is cross-process; threads alone prove nothing) shows serialized, lossless lines; a test with the lock held shows the typed error path; Phase 3 torn-tail repair suite stays green (AC 4)

## Tasks / Subtasks

- [ ] Inventory writers (AC: 1)
  - [ ] `grep -rn "append_history" src/runtime/src/`: known callers `application/reconcile.py:282`, `application/seed_cache.py:245`, writer `adapters/seeder.py:806+` (`CacheSeeder.append_history`, O_APPEND + fsync). Confirm the inventory is exactly these; any other `history.jsonl` open-for-write is in scope.
  - [ ] Decision (b)east: generalize vs new adapter. Recommended: generalize `FlockSeedMutex` into path + error-factory parameters (same kernel mechanism, two files, two error types). Only if generalization churns existing call sites badly, a sibling adapter with a shared `_flock` helper is acceptable — reviewer must confirm no logic duplication.
- [ ] Plumb the lock (AC: 1, 2)
  - [ ] Lock acquisition lives INSIDE `CacheSeeder.append_history` (adapter owns its invariant — then Reconcile/Seed/CLI callers get serialization free, and future writers cannot forget). Lock file `state_root/.history.lock`, mode `0o600` (mirror seed lock), blocking acquire, release in `finally`.
  - [ ] `OSError` during acquire/append → `HistoryLockError` (new, `domain/models.py`, `RuntimeError` subclass next to `SeedLockedError`). Message names the lock path and the operation.
  - [ ] CLI composition: `CacheSeeder` is constructed in several `_run_*` helpers — if the mutex becomes a constructor parameter, update ALL construction sites (grep `CacheSeeder(`/); a missed site must fail loudly (required arg), never silently unlock.
- [ ] Tests (AC: 4)
  - [ ] `tests/unit/test_history_lock.py` (or integration — flock across processes needs real FDs; threads-only is insufficient, say which and why in the file docstring): N processes × M appends → all N×M lines present, parseable, none interleaved (validate with the existing history reader/torn-tail tolerant parser).
  - [ ] Lock-held contention: hold `.history.lock` from the test, assert append raises `HistoryLockError` (not hang — set a timeout guard via `pytest-timeout` if available, else `signal.alarm`/mp with join timeout; document the choice).
  - [ ] Regression: full Phase 3 history/torn-tail tests green (`-k "history or torn or seed_pin"` at minimum; full suite at the end).
- [ ] Run full `uv run --directory src/runtime pytest` + layering + ruff + format

## Dev Notes

### Gate 2 rulings (owner approved all items)

- Typed errors cover acquire AND append (`seeder.py` open/write/fsync → `HistoryLockError`; `doctor.py` catches `(OSError, HistoryLockError)` preserving the heal wrap).
- Lock file mode `0o600` (task-pinned; existing Phase-3 `0644` files keep their on-disk mode — `os.open` mode applies at creation only).
- Tests: multiprocess lossless (validated via `InspectHistoryUseCase`), torn-tail heal under contention, cross-process blocking waiter, writer-level typed-error (`history.jsonl` as dir). Symlinked-history test updated to expect `HistoryLockError` (typed contract supersedes raw `OSError`).
- D1 ratified: mutex constructed INTERNALLY at both seeder sites (single-writer invariant; zero call-site churn; documented trade-off: uninjectable).
- D2 ratified: seed lock-file open failures map uniformly to `SeedLockedError` (one error per port); splitting contention vs I/O is a follow-up, out of scope.

### Scope boundary — lock ONLY
Story 4.6 serializes history appends. It does **NOT** implement:
- Auto-check on `wallpaper set` (p4-3-4 backlog — separate story, separate Gate 2)
- Changing append semantics (O_APPEND + fsync stays; trigger enum stays; line format stays)
- Locking readers (`inspect`, `seed_pins` tolerate torn tails by design — Phase 3; locking reads would serialize the world for no gain)
- Any planner/diff/desired-state change

### Layering (AD-25, locked)

- `HistoryLockError` in `domain/` (pure); lock mechanism in `adapters/`; port in `ports/` IFF a new port is needed (generalization reuses `ISeedMutex` shape — prefer it); `test_layering.py` run, not modified

### Conventions consumed (do not redefine)

1. flock kernel-owned semantics (auto-release on death — the documented reason PID-files were rejected).
2. `0o600` lock files, `state_root`-scoped paths.
3. Typed errors over silent/hang failures (repo-wide).
4. `CacheSeeder.append_history` is the ONLY writer (rt-2-7 invariant) — the lock lives with the invariant, not scattered at call sites.
