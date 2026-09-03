---
baseline_commit: 1d9babfe05bb026693f88d6f3bd4109d17a8ea7f
---

# Story rt-3.1: history.jsonl must-not-lose persistence

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want every desktop state transition recorded in an append-only, never-lost history,
So that I can audit what changed and when, even across restarts.

## Scope Reality (READ FIRST)

**This is a VERIFICATION + HARDENING story, not greenfield.** The history.jsonl writer already
exists and is tested: `CacheSeeder.append_history` shipped in rt-1-11, is called by all three
flows (seed/set/reconcile), and rt-2-7 added golden-file schema + byte-immutability tests.
Story 3.1's job is to (a) prove every epic AC is test-locked, (b) close the known durability
gap deferred from rt-2-1, and (c) pin the as-built design decisions. Do NOT rebuild, move, or
rewrite the existing writer.

## Acceptance Criteria

1. **Atomic append, pinned schema, pinned order** — Given a reconcile completes, when the state
   transitions, then a history.jsonl line is appended ATOMICALLY, one line per reconcile, in the
   pinned schema (7 fields, see Dev Notes), AFTER the swap and BEFORE reload is considered
   complete (AR-3, AD-4/NFR-5).
2. **Append-only immutability** — history.jsonl is never overwritten or rewritten — only
   appended; prior lines remain byte-identical after subsequent runs (AR-3).
3. **Restart survival** — the store survives restart: history persists across process runs,
   verifiable with fresh adapter instances on the same state_root (FR-4).
4. **Full persisted state** — `current.json` (written in Epic 1) + `history.jsonl` together form
   the full persisted state (index + history; `current/` filesystem remains the authority,
   NFR-3).
5. **Crash-window gap closed** — the rt-2-1 deferred gap ("save after repoint can fail leaving FS
   ahead of store; history append outside lock can be lost") is either (a) covered by rt-2-2
   crash-repair and pinned with a test, or (b) explicitly re-scoped with rationale recorded in
   `deferred-work.md`. No silent acceptance.
   **Structural note (grounding for the verdict):** rt-2-2's recovery detects symlink-vs-`current.json`
   DIVERGENCE (`_revert_stale_symlinks`). In the save→append window they MATCH, so rt-2-2 **cannot
   detect this crash by construction**. For reconcile the line self-heals lazily only because every
   reconcile appends unconditionally; for the SEED flow the loss is PERMANENT (see Crash-window
   context). Any "covered, pinned" verdict must address this detection limitation head-on.
6. **Zero regressions** — full suite passes (`pytest`, `ruff check`, `ruff format --check`,
   `mypy --strict`, layering tests) with ZERO new violations; existing golden-file, trigger-enum,
   and negative-boundary tests remain green and untouched in semantics.

## Tasks / Subtasks

- [x] Task 1: AC verification sweep (AC: 1–4)
  - [x] Build the AC→test mapping table (Dev Notes §Test Map is the starting point); identify any AC lacking a pinning test
  - [x] Add missing tests only where a gap is found (do not duplicate existing coverage)
- [x] Task 2: Restart-survival test (AC: 3)
  - [x] Integration test: write history via one `CacheSeeder` instance, append again via a FRESH `CacheSeeder` + fresh `JsonStateRepository` on the same `state_root` (simulated new process); assert accumulation and prior-line byte-identity
- [x] Task 3: Crash-window verification — BOTH flows (AC: 5)
  - [x] Trace the RECONCILE window: reconcile.py:253 save → reconcile.py:265 append. Note: rt-2-2 recovery cannot detect a crash here (symlinks match current.json); reconcile self-heals only because every reconcile appends unconditionally
  - [x] Trace the SEED window (the worse half): seed_cache.py:229 save → :232 append. A crash there is PERMANENT: next run sees `load_current() != None` → seed is a no-op → the `trigger: "seed"` line is never written
  - [x] Pin with tests where a behavior exists to pin; otherwise record decision + rationale in `deferred-work.md` for both windows
- [x] Task 4: Design-decision pins (AC: 1, 2)
  - [x] Add a test asserting no `schema_version` field appears in history lines (pinned schema is exactly 7 fields)
  - [x] Confirm `append_history` stays on `CacheSeeder` (NOT promoted to `IStateRepository`); add/confirm a docstring-level note citing this story's decision
  - [x] Fix the stale docstring trigger example in `append_history` (seeder.py:582 cites `"apply"` as an example — `"apply"` is NOT a valid trigger per the pinned enum)
- [x] Task 5: Quality gates (AC: 6)
  - [x] `uv run --directory src/runtime pytest` — all green
  - [x] `uv run --directory src/runtime ruff check src` and `uv run --directory src/runtime ruff format --check` — zero NEW violations (pre-existing baseline: exactly 3 ruff in cli/main.py + domain/models.py). Do NOT run bare `ruff check` (unscoped picks up tests/repo root: 96+ errors)
  - [x] `uv run --directory src/runtime mypy --strict src` — zero NEW violations (baseline: exactly 4). Bare `mypy --strict` errors out ("Missing target module")
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v`
  - [x] Update `deferred-work.md` and this story's Dev Agent Record

## Dev Notes

### Pinned history.jsonl line schema (AR-9 — write/read EXACTLY, no extras)

`[Source: _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md#history.jsonl (append-only, must-not-lose)]`

```json
{"ts": "<ISO-8601-UTC>", "trigger": "seed|set|reconcile|force", "wallpaper": "<sha256-hex>", "palette": "<sha256-hex|null>", "effects": "<sha256-hex|null>", "icons": "<sha256-hex|null>", "source_path": "<abs-or-empty>"}
```

- **NO `schema_version` field** — the version field exists only in `current.json` (`schema_version: 2`). "Pinned schema" = these 7 fields, enforced by the contract doc, not an embedded version constant.
- `ts` as-built format: `datetime.now(UTC).isoformat().replace("+00:00", "Z")`
- `trigger` enum `seed|set|reconcile|force` — NEVER invent `"apply"`. Validation lives ONLY in `ReconcileDesktopStateUseCase.run(trigger=...)` (reconcile.py:148-150); `append_history` stays trigger-agnostic.
- Correction of a mistake = NEW line, never an edit.

### As-built mechanics (load-bearing — do not degrade)

`src/runtime/src/runtime/adapters/seeder.py:567-617` `CacheSeeder.append_history(trigger, wallpaper_hash, palette_hash=None, effects_hash=None, icons_hash=None, source_path="")`:

- `_O_APPEND = os.O_APPEND | os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW` (seeder.py:46) — O_NOFOLLOW rejects symlinked history.jsonl
- Path: `state_root / "history.jsonl"`, mode 0o644
- Full-write loop (`memoryview` over `os.write` — short writes would tear the JSONL line); `os.fsync(fd)` in the `try` body (seeder.py:615), `os.close` in `finally`
- `current.json` atomicity is tmp + `os.replace` via `JsonStateRepository._atomic_write` (json_state_repository.py:252-272) — NO fsync there; only history gets fsync. Do not add dir-fsync; that is beyond the architecture.

### Pinned swap order (AD-6 — history is step 4 of 5)

`[Source: shared-data-contract.md#Swap sequence (AD-6 ownership)]`

1. Ensure cache entries → 2. repoint `current/` symlinks → 3. write `current.json` → 4. **append history.jsonl** → 5. desktop reloads.

As-built: reconcile.py docstring "entries → symlinks → current.json → history → reload" (reconcile.py:130); history append outside the lock at reconcile.py:265-273 (comment: "O_APPEND + fsync is atomic"); reload loop at 275-284. Seed flow mirrors: seed_cache.py:220 → 229 → 232. `ApplyWallpaperUseCase` does NOT append history (apply_wallpaper.py:174-176).

### Callers of append_history (exactly 2 call sites / 3 flows reach history)

1. `application/seed_cache.py:231-239` — `trigger="seed"`, `source_path=""`
2. `application/reconcile.py:265-273` — `trigger` param (default `"reconcile"`), `source_path=saved.wallpaper.source_path`
3. Nothing else. `wallpaper set` reaches history only via `ReconcileDesktopStateUseCase.run(trigger="set")` (cli/main.py:264)

### Design decisions pinned by this story

- **History stays on the `CacheSeeder` adapter.** Do NOT add `append_history`/`load_history` to `IStateRepository` — rt-1-10 pinned the port minimal (`load_current`/`save` only, ports/state_repository.py:8-15) and reserved history methods for Epic 3 inspection use cases. The spine Deferred bullet ("Phase 2 ships load_current/save/history") is satisfied by the adapter seam; promotion to the port is a Phase 3 concern.
- **`CacheSeeder.append_history` is the ONLY history writer.** Call it through Reconcile/Seed, never directly from the CLI (rt-2-7 invariant).
- **Concurrent-seed guard preserved:** `ISeedMutex`/`FlockSeedMutex` (`.seed.lock`) + double-checked `load_current`; seed is a no-op when `load_current()` returns non-None; corrupt current.json raises loudly — never treated as absent, never fabricates a seed history line.
- **Negative-boundary pins to preserve (do not delete/reframe):** `JsonStateRepository.save` never writes history (test_json_state_repository.py:398-404); apply never appends (test_apply_wallpaper_integration.py:258-271); trigger-agnostic adapter vs validating use case (test_reconcile.py `TestReconcileHistoryTriggerParam`).

### Test Map (existing coverage — extend, don't duplicate)

| AC | Existing pin | Location |
|---|---|---|
| 1 atomic append + schema | `test_append_is_atomic`, valid JSON/ts-Z, symlink refusal | tests/unit/test_seed_cache.py:374-423 |
| 1 one-line-per-reconcile + schema | `TestReconcileHistory` | tests/unit/test_reconcile.py:666-734 |
| 1 trigger enum | `TestReconcileHistoryTriggerParam` | tests/unit/test_reconcile.py |
| 2 immutability (byte-identical) | capstone repeat test, timestamps regex-normalized | tests/integration/test_wallpaper_set_capstone_integration.py:307-322 |
| 1 AR-9 golden file | `TestCapstoneGoldenSchema` (`GOLDEN_HISTORY`) | test_wallpaper_set_capstone_integration.py:497-557 |
| 3 restart survival | PARTIAL: crash-recovery "exactly one reconcile line" runs in one process with reused instances, NOT fresh-process survival — Task 2's test is the real pin | tests/integration/test_crash_recovery_integration.py:207-248 |
| 4 index+history separation | negative guards (see above) | unit + integration |

### Test conventions (pass review or get bounced)

- Runner: `uv run --directory src/runtime pytest`; bar is zero NEW ruff/mypy violations
- No conftest.py — module-local helpers; `_make_state()` builders with deterministic `"a"*64` hashes; `tmp_path` as `state_root` via adapter injection
- Class-based grouping with AC/AD-citing docstrings (e.g. `class TestCacheSeederAppendHistory:` "(AD-4)")
- Golden tests: `_TS_RE.sub("<TS>", ...)` normalization; assert VALUES not key-presence (rt-2-7 review style)
- Pin TRANSIENT observables (caplog) not just final state — "a wrong-reason test is a review magnet"
- Contract-honest fakes with `.calls` counters; live-host CLI tests must monkeypatch all four reloader adapter modules
- Positive wiring tests in composition root (mis-wire passes green otherwise)

### Crash-window context (AC 5) — two-window analysis

Deferred from rt-2-1: "History/save outside lock inconsistency and crash-recovery atomicity — save after repoint can fail leaving FS ahead of store, history append outside lock can be lost [reconcile.py:183, reconcile.py:185] — deferred, pre-existing design; Story 2.2 owns crash-mid-swap recovery." Story rt-2-2 IS done (`rt-2-2-crash-mid-swap-recovery: done` in sprint-status).

The window exists TWICE, with different consequences:

- **Reconcile window** (reconcile.py:253 save → :265 append): a crash here leaves current.json matching the symlinks, so rt-2-2's divergence-based recovery CANNOT detect it. Self-heal is lazy: the next reconcile appends unconditionally, so history resumes — but the crashed transition's line is missing.
- **Seed window** (seed_cache.py:229 save → :232 append): PERMANENT loss. After a crash here, `load_current()` returns non-None → seed is a no-op forever → the `trigger: "seed"` line never gets written (a later reconcile would append a `"reconcile"` line, or nothing).

Pin-or-re-scope BOTH windows explicitly (AC 5).

### Project Structure Notes

- Package `dotfiles-runtime` at `src/runtime/` (nested src layout: `src/runtime/src/runtime/...`); Python >= 3.14, hatchling, mypy strict, ruff line-length 100 double-quotes
- Layering (AD-1/AD-14, mechanically enforced by tests/architecture/test_layering.py): domain (pure stdlib) → ports (ABCs, `I` prefix) → adapters → application → cli; cross-package import only `cli_output`
- State root: `$XDG_STATE_HOME/dotfiles/` (default `~/.local/state/dotfiles/`) — runtime-owned; provisioning never writes here (AD-5)
- Error conventions: `ValueError` = invalid input/contract; `RuntimeError` = state/dependency failure; `OSError` propagates; CLI maps all to `ErrorView` + exit 1
- Commit style: `feat(rt-3-1): <description>` + `docs(bmm): add story rt-3-1 ...` carrying story `.md` + `sprint-status.yaml`

### References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md#Story 3.1: history.jsonl must-not-lose persistence] (ACs 1-4 verbatim; Epic 3 R1 note line 102)
- [Source: ARCHITECTURE-SPINE.md#AD-4 — history.jsonl is must-not-lose], [#AD-5 — state_root], [#AD-6], [#Deferred]
- [Source: shared-data-contract.md#history.jsonl], [#current.json], [#Swap sequence (AD-6 ownership)]
- [Source: epics-dotfiles-runtime-phase2.md#Requirements Inventory] — FR-4, FR-7, NFR-3, NFR-5, AR-3, AR-9, AR-10
- [Source: _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md#Capabilities] — CAP-4, CAP-7
- [Source: _bmad-output/implementation-artifacts/rt-1-10-minimal-istaterepository.md#Dev Notes] — port-minimality rule, atomic-write patterns
- [Source: _bmad-output/implementation-artifacts/rt-1-11-first-run-self-seeding.md] — append_history origin, O_NOFOLLOW hardening, review decisions
- [Source: _bmad-output/implementation-artifacts/rt-2-7-full-wallpaper-set-capstone.md] — trigger semantics, golden-file guard, review learnings
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — rt-2-1 crash-window item (AC 5)

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash

### Debug Log References

- Baseline before any change: `pytest` 424 passed / 2 skipped; `ruff check src` exactly 3 (cli/main.py:166, cli/main.py:271, domain/models.py:35); `mypy --strict src` exactly 4 (domain/models.py:30 + 3 import-untyped in cli/main.py); layering 56 passed; format clean.
- After implementation: `pytest` 429 passed / 2 skipped (5 new tests); `ruff check src` still exactly 3 (confirmed no new); `mypy --strict src` still exactly 4 (no new); `ruff format --check` clean; `test_layering.py` 56 passed.

### Completion Notes List

- **Task 1 — AC verification sweep:** Built the AC→test mapping (all entries in Dev Notes §Test Map verified present). Only AC-3 restart survival was partial (crash-recovery test reused one in-process instance set); AC 1-4 otherwise pinned. **Gap found and pinned:** AC 1's "history BEFORE reload is considered complete" ordering had NO pinning test — added `TestCapstoneHistoryOrdering.test_every_reloader_observes_appended_history_line` (`_HistoryProbeReloader` asserts every reloader observes the new line already on disk), satisfying AR-3/AD-6 step-4 ordering.
- **Task 2 — Restart survival (AC 3):** Added `test_restart_survival_fresh_instances_accumulate_byte_identical` in `test_crash_recovery_integration.py` — full seed+apply via one adapter pair, THEN a FRESH `JsonStateRepository` + FRESH `CacheSeeder` on the same `state_root` (simulated new process) reconciles and appends; asserts prior lines remain byte-identical and exactly one new line lands.
- **Task 3 — Crash-window verification (AC 5):** Traced both windows against the as-built code:
  - RECONCILE: `reconcile.py:253` save → `reconcile.py:265` append. rt-2-2's `_revert_stale_symlinks` compares symlink targets vs current.json; in the save→append window these MATCH, so divergence recovery cannot detect a crash (structural). Reconcile self-heals lazily (every reconcile appends unconditionally).
  - SEED: `seed_cache.py:229` save → `:232` append. After a crash here `load_current()` is non-None → seed no-ops forever → `trigger:"seed"` never written (PERMANENT).
  - Pinned both: `test_crash_window_reconcile_save_append_lost_line_not_backfilled` (lost line NOT resurrected; exactly one new line appended) and `test_crash_window_seed_save_append_seed_line_permanently_lost` (seed re-run no-op; no seed line anywhere; a later reconcile appends a "reconcile" line). Decision + rationale recorded in `deferred-work.md` (append-only + atomicity is the guarantee; post-crash line reconstruction is re-scoped as ACCEPTED, out of AD-12 scope).
- **Task 4 — Design-decision pins (AC 1, 2):**
  - Added `TestCacheSeederAppendHistory.test_append_line_has_exactly_seven_fields_no_schema_version` — asserts the line key-set is EXACTLY `{ts, trigger, wallpaper, palette, effects, icons, source_path}` and `schema_version` is absent (AR-9, version lives only in current.json).
  - `append_history` stays on `CacheSeeder`; added a docstring-level note in `seeder.py` citing rt-3.1's decision (port stays minimal per rt-1-10; adapter seam serves Epic 3 inspection use cases; only writer; call via Reconcile/Seed).
  - Fixed stale docstring trigger example in `append_history` (`"apply"` → `"seed|set|reconcile|force"`).
- **Task 5 — Quality gates (AC 6):** full suite green (429 passed / 2 skipped), ruff 3 baseline / zero new, mypy 4 baseline / zero new, format clean, layering green. `deferred-work.md` + this record updated.

### File List

- `_bmad-output/implementation-artifacts/rt-3-1-history-jsonl-persistence.md` (this story — status/checkboxes/record)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status in-progress)
- `_bmad-output/implementation-artifacts/deferred-work.md` (crash-window verdict, AC 5 decision)
- `src/runtime/src/runtime/adapters/seeder.py` (append_history docstring: decision note + trigger enum fix)
- `src/runtime/tests/unit/test_seed_cache.py` (7-field schema pin)
- `src/runtime/tests/integration/test_wallpaper_set_capstone_integration.py` (AC 1 ordering pin)
- `src/runtime/tests/integration/test_crash_recovery_integration.py` (restart-survival + 2 crash-window pins)

## Change Log

- 2026-09-02: Implemented Story rt-3.1 (verification + hardening). Added 5 tests, fixed a stale docstring, recorded the AC-5 crash-window verdict in `deferred-work.md`. All quality gates green (429 passed/2 skipped; ruff 3 & mypy 4 at pre-existing baseline, zero new).
