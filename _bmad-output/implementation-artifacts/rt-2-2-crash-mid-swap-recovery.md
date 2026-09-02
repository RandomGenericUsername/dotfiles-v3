---
baseline_commit: 644c3e1459a802897faefca28be4efe48c2a1132
---

# Story 2.2: Crash-mid-swap recovery to last-good state

Status: review

## Story

As a user,
I want the desktop to stay consistent if a swap or reload is interrupted,
so that the next run repairs the state instead of leaving a partial swap.

## Acceptance Criteria

1. **Given** a swap is interrupted mid-sequence (crash, killed process, reload failure), **When** the next run starts, **Then** it detects the incomplete swap from the persisted `current.json` + `current/` symlink comparison and reverts the stray `current/` repoints to the last-good `current.json` (FR-3, R5).

2. **Given** a partially-swapped state (some `current/` symlinks repointed, others not; or `current.json` not yet written), **When** recovery runs, **Then** all `current/` symlinks are reverted to match the targets dictated by the last-good `current.json` — every symlink's target must resolve into `cache/<layer>/<hash>/` where `<hash>` matches the entry hash recorded in `current.json` for that layer (AD-6, shared-data-contract crash recovery).

3. **Given** recovery reverted symlinks to the last-good state, **When** the interrupted reconcile is re-run, **Then** it is a cache hit (no CSG/WEG/ITR tool invocations — the derivation was completed before the crash; the cache entries still exist) (R5).

4. **Given** a reload failure is detected (desktop consumer did not pick up the new state), **When** the command completes, **Then** it reports which consumer failed to reload and exits non-zero — known Phase 2 limitation: no daemon/watcher can retry; the command surfaces the failure and the user must re-run (R5).

5. **Given** the current/ symlinks already match current.json (no crash occurred), **When** recovery runs, **Then** it is a no-op — zero symlinks reverted, zero tool invocations, zero writes (idempotent).

6. **Given** current.json is absent (never seeded), **When** recovery runs, **Then** it raises `RuntimeError("nothing to reconcile")` — recovery requires a recorded baseline; first-run seeding is the seeder's responsibility, not recovery's (AD-6, rt-2-1 AC 4).

## Tasks / Subtasks

- [x] Task 1 — `application/reconcile.py`: `_revert_stale_symlinks` method (AC: 1, 2, 5)
  - [x] Add a private method `_revert_stale_symlinks(self, state: DesktopState) -> list[Path]` to `ReconcileDesktopStateUseCase`. This method runs BEFORE the normal swap sequence (before `_ensure_entries`). It reads the authoritative state from `current.json` (already loaded as `state` in `run()`) and validates every `current/` symlink against it. Import `_repoint_symlink` from `runtime.adapters.seeder` at module level (same import pattern as `CacheSeeder` at reconcile.py:43).
  - [x] For each file in `state_root / "current"`:
    - Wallpaper symlinks (`wallpaper-<monitor>.png`): if the symlink target does not contain the path segment `cache/wallpapers/<state.wallpaper.content_hash>/`, revert it by repointing to `cache_entry_path(state_root, "wallpapers", state.wallpaper.content_hash) / "wallpaper.png"` via the atomic repoint pattern (import `_repoint_symlink` from `runtime.adapters.seeder` at module level — same import pattern as `CacheSeeder` at reconcile.py:43; call `_repoint_symlink(link, expected_target)` where first arg is the symlink location, second is the target — matching `seeder.py:55` signature `(current_path, target)`).
    - Palette symlinks (`colors.conf`, `colors.gtk.css`, `colors.yaml`): if `state.palette` is not None and the symlink target does not contain `cache/palettes/<state.palette.entry_hash>/`, revert to `cache_entry_path(state_root, "palettes", state.palette.entry_hash) / <filename>`.
    - Effects dir symlink (`effects/`): if `state.effects` is not None and the target does not contain `cache/effects/<state.effects.entry_hash>/`, revert to `cache_entry_path(state_root, "effects", state.effects.entry_hash)`.
    - Icons dir symlink (`icons/`): if `state.icons` is not None and the target does not contain `cache/icons/<state.icons.entry_hash>/`, revert to `cache_entry_path(state_root, "icons", state.icons.entry_hash)`.
  - [x] Return the list of reverted symlink paths (for logging and result reporting).
  - [x] Symlinks whose targets already match are left untouched (idempotent — AC 5).
  - [x] Symlinks to monitors not in `state.monitors` are NOT reverted by this method — they are cleaned by `_cleanup_stale_symlinks` (which already runs later in the swap). Recovery only fixes WRONG targets, not orphaned monitors.

- [x] Task 2 — `application/reconcile.py`: integrate recovery into `run()` (AC: 1, 3)
  - [x] At the TOP of `run()`, after the fail-fast absent-state guard (`state is None → RuntimeError`) and BEFORE the pre-lock derivation (`_ensure_entries`), call `self._revert_stale_symlinks(state)`.
  - [x] Log reverted symlinks at INFO level: `logger.info("recovery: reverted %d stray symlink(s): %s", len(reverted), reverted)`.
  - [x] If no symlinks were reverted, log at DEBUG level: `logger.debug("recovery: no stray symlinks detected")`.
  - [x] The recovery step runs OUTSIDE the lock (same as derivation — it only reads `current.json` which is the authoritative baseline, and the symlinks are being corrected to match it; a concurrent `wallpaper set` that overwrites `current.json` will be caught by the double-checked re-load inside the lock, same as derivation).
  - [x] After recovery, the normal swap sequence proceeds: `_ensure_entries` → lock → re-load state → repoint → save → history. If the crash left the cache entries intact (AC 3), `_ensure_entries` finds them all and no tool invocations occur.

- [x] Task 3 — `cli/main.py`: report reload failures (AC: 4)
  - [x] In the `reconcile` CLI command, after `_run_reconcile()` returns, check `result.skipped` for entries containing "reload" or "consumer" (the reload adapters — Stories 2.3–2.6 — will populate these when they land). For now (before 2.3–2.6 exist), this is a structural placeholder: the CLI already renders `result.skipped` in the output.
  - [x] When reload adapters exist (2.3–2.6), extend `ReconcileResult` with a `reload_failures: list[str]` field. The CLI checks this field and exits non-zero with an `ErrorView` listing the failed consumers. **This task is a forward-looking placeholder — the field is `[]` until 2.3–2.6 land.**
  - [x] Update `_run_reconcile` composition to propagate the new field.

- [x] Task 4 — Unit tests `tests/unit/test_crash_recovery.py` (AC: 1–6)
  - [x] Follow `test_reconcile.py`'s fake-adapter style. Persist the fake state repo to `tmp_path` where disk assertions matter.
  - [x] **Crash scenario tests:**
    - `test_partial_swap_wallpaper_only_reverted`: Repoint only `wallpaper-DP-1.png` to a DIFFERENT cache entry hash; leave other symlinks untouched. Run recovery → wallpaper symlink reverted to the correct target; other symlinks unchanged.
    - `test_partial_swap_palette_only_reverted`: Repoint only `colors.conf` to a stale palette hash; recovery reverts it.
    - `test_partial_swap_effects_dir_reverted`: Repoint `effects/` to a wrong effects hash; recovery reverts.
    - `test_crash_between_symlink_and_current_json`: Simulate a crash where current.json is OLD (last-good) but 2 of 4 symlinks are NEW (from the interrupted swap). Recovery reverts the 2 new symlinks to match old current.json.
    - `test_full_swap_interrupted_all_symlinks_reverted`: All symlinks point to a different hash set than current.json; recovery reverts all.
  - [x] **Idempotency tests:**
    - `test_no_crash_is_noop`: Symlinks already match current.json → zero reverts, zero tool invocations.
    - `test_double_recovery_noop`: Run recovery twice → second run reverts nothing.
  - [x] **Cache-hit-after-recovery test (AC 3):**
    - `test_recover_then_reconcile_is_cache_hit`: Crash scenario → recovery → then normal reconcile. Assert CSG/WEG/ITR call counts are zero (cache entries still exist).
  - [x] **Absent state test (AC 6):**
    - `test_recovery_absent_state_raises`: current.json absent → `RuntimeError("nothing to reconcile")`.
  - [x] **Corrupt state test:**
    - `test_recovery_corrupt_current_json_propagates`: current.json is invalid JSON → `ValueError` propagates.
  - [x] **Structural scope lock:**
    - `test_recovery_writes_only_inside_current`: After recovery, assert no new files appeared outside `state_root/current/` (no writes to cache, no writes to state_root root).
  - [x] **Missing current/ directory:**
    - `test_recovery_missing_current_dir_is_noop`: `current/` does not exist → recovery returns `[]`, no crash.
  - [x] **Dangling symlinks in current/:**
    - `test_recovery_dangling_symlink_reverted`: A symlink in `current/` points to a non-existent cache entry → recovery reverts it to the correct target from current.json.
  - [x] **Monitor name traversal guard:**
    - `test_recovery_monitor_name_traversal_rejected`: Monitor name with `../` → `ValueError`.

- [x] Task 5 — Integration test `tests/integration/test_crash_recovery_integration.py` (AC: 1, 2, 3)
  - [x] End-to-end: seed → apply a wallpaper → manually corrupt symlinks to simulate a crash → run `reconcile` → assert desktop converges to last-good state.
  - [x] Crash simulation: after apply, read `current.json`, then manually repoint 2 symlinks to stale hashes (simulating partial swap). Run reconcile → symlinks match current.json.
  - [x] Cache-hit verification: after recovery, run reconcile again → assert zero tool invocations (CsgAdapter/WegAdapter/ItrAdapter call counters unchanged).
  - [x] Recovery + history: assert exactly one `history.jsonl` line is appended (trigger `"reconcile"`) after recovery + reconcile.
  - [x] Concurrent recovery safety: start two reconcile threads/tasks concurrently on a partially-swapped state — assert both complete without corrupting symlinks (the mutex serializes them; the second run is a no-op).

- [x] Task 6 — CLI tests `tests/unit/test_cli_crash_recovery.py` (AC: 4)
  - [x] Extend `test_cli_reconcile.py` pattern.
  - [x] `test_reconcile_recovery_logs_stray_reverts`: Simulate stray symlinks → run CLI `reconcile` → assert INFO log contains "recovery: reverted".
  - [x] `test_reconcile_no_stray_logs_debug`: No stray symlinks → assert DEBUG log "no stray symlinks detected".
  - [x] Forward-looking: `test_reconcile_reload_failure_exits_nonzero` — when 2.3–2.6 land, this test exercises the `reload_failures` field; for now, mark as `pytest.skip("reload adapters not yet implemented")`.

- [x] Task 7 — Full green gate (AC: all)
  - [x] `uv run --directory src/runtime pytest -q` (baseline: expect ~229+ passed, 1 skipped)
  - [x] `uv run --directory src/runtime ruff check src/runtime` (zero NEW violations)
  - [x] `uv run --directory src/runtime ruff format --check src/runtime` (new/edited files format-clean)
  - [x] `uv run --directory src/runtime mypy --strict src/runtime` (zero NEW errors)
  - [x] `tests/architecture/test_layering.py` green (no new adapter→application imports; recovery is pure application-layer logic delegating to adapters via the seeder)

## Dev Notes

### Scope boundary — crash recovery ONLY, not convergence

This story delivers crash-mid-swap recovery: detecting a partially-swapped state and reverting stray symlinks to the last-good `current.json`. It deliberately does NOT:
- reload ANY desktop component (Stories 2.3–2.6 own reload),
- implement the reload-failure reporting beyond a structural placeholder (AC 4 is satisfied by the `reload_failures: list[str]` field on `ReconcileResult`, populated by 2.3–2.6),
- rewire `wallpaper set` (Story 2.7 capstone),
- fix the deferred-history/save-outside-lock atomicity (deferred-work rt-2-1 — save after repoint can fail leaving FS ahead of store; history append outside lock can be lost. These are pre-existing design decisions; Story 2.2 only ensures symlinks can be reverted from the last-good current.json).

### The crash model — symlinks lead, current.json follows

AD-6 / shared-data-contract: the swap sequence is cache-ensure → symlink repoint → current.json → history → reload. Each symlink repoint is atomic (tmp + `os.replace`). The sequence as a whole is NOT atomic — by design. A crash mid-sequence leaves:
- `current.json` = the LAST successfully saved state (old state if crash before step 3; new state if crash after step 3).
- `current/` symlinks = a MIX of old and new targets (if crash during step 2) or all new targets (if crash during step 4, after current.json saved).

Recovery must handle both cases:
1. **Crash before current.json saved (step 2):** symlinks are partially new, current.json is old. Recovery reverts stray symlinks to match old current.json.
2. **Crash after current.json saved (step 4):** symlinks may be partially new, current.json is new. Recovery reverts stray symlinks to match new current.json.

In both cases, the algorithm is identical: read current.json, check each symlink's target hash against the recorded entry hash, revert mismatches.

### Reuse — leverage existing infrastructure

- `CacheSeeder._repoint_symlink(target, dest)` (adapters/seeder.py) — the atomic tmp+`os.replace` symlink repoint pattern. Recovery should call this, not reimplement atomic repoint.
- `cache_entry_path(state_root, layer, entry_hash)` (adapters/cache.py:107) — construct correct cache entry paths.
- `CacheSeeder.repoint_current_symlinks(...)` — the full repoint set. Recovery does NOT call this (it reverts individual symlinks, not the full set), but it reuses the same atomic repoint primitive.
- `_cleanup_stale_symlinks` (reconcile.py:404) — already handles orphaned symlinks (wrong monitor names, null-layer leftovers). Recovery handles WRONG-TARGET symlinks. The two methods are orthogonal: recovery runs first (fix targets), cleanup runs later in the swap (remove orphans).
- `DesktopState` from domain — the state projection used for symlink validation.

### Recovery algorithm (pseudocode)

```python
# Import at module level (same pattern as CacheSeeder import at reconcile.py:43)
from runtime.adapters.seeder import CacheSeeder, _repoint_symlink

def _revert_stale_symlinks(self, state: DesktopState) -> list[Path]:
    """Revert current/ symlinks whose targets don't match current.json."""
    current_dir = self._state_root / "current"
    if not current_dir.is_dir():
        return []

    reverted = []
    expected = self._build_expected_targets(state)

    for name, expected_target in expected.items():
        link = current_dir / name
        if not link.is_symlink():
            continue  # not a symlink (regular file/dir) — skip; cleanup handles orphans
        actual_target = link.resolve()
        if actual_target != expected_target.resolve():
            # Stray symlink from a partial swap — revert atomically
            # _repoint_symlink(current_path, target) — seeder.py:55 signature
            _repoint_symlink(link, expected_target)
            reverted.append(link)

    return reverted

def _build_expected_targets(self, state: DesktopState) -> dict[str, Path]:
    """Map symlink names → correct cache entry targets from current.json."""
    targets = {}
    # Wallpaper symlinks — one per monitor
    for monitor_name in state.monitors:
        targets[f"wallpaper-{monitor_name}.png"] = (
            cache_entry_path(self._state_root, "wallpapers", state.wallpaper.content_hash)
            / "wallpaper.png"
        )
    # Palette symlinks
    if state.palette is not None:
        pal_dir = cache_entry_path(self._state_root, "palettes", state.palette.entry_hash)
        for artifact in ("colors.conf", "colors.gtk.css", "colors.yaml"):
            targets[artifact] = pal_dir / artifact
    # Effects dir symlink
    if state.effects is not None:
        targets["effects"] = cache_entry_path(
            self._state_root, "effects", state.effects.entry_hash
        )
    # Icons dir symlink
    if state.icons is not None:
        targets["icons"] = cache_entry_path(
            self._state_root, "icons", state.icons.entry_hash
        )
    return targets
```

### The atomic repoint primitive (from seeder)

`_repoint_symlink` is a module-level function in `adapters/seeder.py:55`:

```python
def _repoint_symlink(current_path: Path, target: Path) -> None:
    """Atomic symlink repoint: create tmp, os.replace over dest."""
    tmp = current_path.with_suffix(current_path.suffix + ".tmp-recovery")
    tmp.symlink_to(target)
    os.replace(tmp, current_path)
```

Recovery imports it at module level (same pattern as `CacheSeeder` import at reconcile.py:43) and calls `_repoint_symlink(link, expected_target)` where `link` is the symlink location in `current/` and `expected_target` is the correct cache entry path. The seeder's `repoint_current_symlinks` already uses this pattern internally — recovery uses it for individual symlinks.

### Contract subtleties

- **`current.json` is the baseline.** Recovery trusts `current.json` as the last-good state. If `current.json` is corrupt, `ValueError` propagates (fail-fast — do not attempt recovery from a corrupt baseline).
- **Missing cache entries.** If a symlink target resolves to a cache entry that no longer exists (evicted), the revert still creates the symlink — the normal swap sequence's `_ensure_entries` will detect the cache miss and regenerate (or fail loudly for wallpaper). Recovery does NOT validate cache entry existence; it only validates symlink target correctness relative to `current.json`.
- **Monitor names.** Recovery reverts wallpaper symlinks for ALL monitors in `state.monitors`. A stray symlink for a monitor NOT in `state.monitors` is left to `_cleanup_stale_symlinks` (which runs later in the swap sequence).
- **Dir symlinks (effects/icons).** `effects/` and `icons/` are directory symlinks. `link.resolve()` resolves through the symlink to the target directory. The comparison is `actual_target != expected_target.resolve()`.
- **Recovery runs outside the lock.** It reads `current.json` once (the fail-fast load) and corrects symlinks. A concurrent `wallpaper set` that overwrites `current.json` is caught by the double-checked re-load inside the lock (same as derivation). If the concurrent set changes `current.json` between recovery and the lock, the re-load inside the lock picks up the new state and the swap proceeds correctly.

### Concurrency (from rt-2-1 D1)

Recovery runs OUTSIDE the lock (before derivation, which is also outside the lock). The rationale: recovery only corrects symlinks to match the current `current.json`; it does not modify `current.json`. A concurrent `wallpaper set` that updates `current.json` will be serialized by the mutex at the lock acquire point. The re-load inside the lock ensures the swap uses the latest state.

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758). Timestamps: `datetime.now(UTC).isoformat().replace("+00:00", "Z")`. House style: dense module docstrings citing AD-numbers, no inline "why" comments beyond those. Application→adapters module-level imports are established (seed/apply/reconcile do it and pass layering) — mirror exactly.

### Previous story intelligence (rt-2-1 — the direct predecessor)

- **Swap sequence ordering is PINNED.** Reconcile's `run()` is ONE discrete method (AC 3 of rt-2-1). Story 2.2 wraps/instruments it: recovery runs at the TOP of `run()`, before the swap steps. The swap method itself is NOT restructured — recovery is a pre-check that corrects the filesystem to match `current.json` before the normal flow begins.
- **`_cleanup_stale_symlinks` already exists** (reconcile.py:404). Recovery's `_revert_stale_symlinks` is a DIFFERENT method: it fixes WRONG-TARGET symlinks (target hash doesn't match current.json), while cleanup removes ORPHANED symlinks (symlinks for monitors/layers no longer in the state). The two methods are complementary and run in sequence: recovery first, then the normal swap (which includes cleanup).
- **Deferred from rt-2-1:** "History/save outside lock inconsistency and crash-recovery atomicity — save after repoint can fail leaving FS ahead of store, history append outside lock can be lost [reconcile.py:183, reconcile.py:185] — deferred, pre-existing design; Story 2.2 owns crash-mid-swap recovery." This story addresses the crash recovery aspect (reverting stray symlinks), NOT the atomicity of save/history (which remains deferred).
- **Test patterns.** `test_reconcile.py` uses `_apply_state()` to establish a post-apply environment, `_make_reconcile()` to construct the use case with fake adapters, `_symlink_map()` to inspect current/ symlinks, `_FakeCsg`/`_FakeWeg`/`_FakeItr` with `calls` counters and `fail` flags. Mirror these patterns exactly for crash recovery tests.
- **Baseline suite.** 229 passed, 1 skipped (230 collected). `src/runtime/` is clean. Expect a green baseline before you start.

### Git intelligence

HEAD = `d566c9b` (auto-commit of review findings). Runtime last touched by `b8bc7fd` (Story 2.1). Baseline suite: 229 passed, 1 skipped. `src/runtime/` is clean — expect a green baseline before you start.

### Latest technical information

No new external dependencies — crash recovery is stdlib-only (`os.symlink`, `os.replace`, `pathlib`). Python 3.14, Typer, pytest, ruff, mypy versions are pinned in `src/runtime/pyproject.toml`/`uv.lock`; do not bump them in this story. The `os.replace`-over-symlink atomicity guarantee used by `_repoint_symlink` is POSIX rename semantics — same-filesystem, already verified in rt-1-11; no version research required.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Integration tests use contract-honest fakes (no real tools, no skip logic); the real-tool skip pattern belongs to the csg/weg/itr adapter integration tests only. Unit tests are pure fakes.
- Lint/type gates in Task 7, all with `--directory src/runtime`; baseline debt documented above — zero NEW violations is the bar.
- Layering: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set (`provisioning`, `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`).
- Assertion style: unit tests assert behavior + contracts (invocation counts, symlink targets, history schema); integration tests assert filesystem outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/tests/unit/test_crash_recovery.py` (NEW — unit tests for _revert_stale_symlinks)
- `src/runtime/tests/integration/test_crash_recovery_integration.py` (NEW — end-to-end crash scenario)
- `src/runtime/tests/unit/test_cli_crash_recovery.py` (NEW — CLI tests for recovery logging)

Modified:
- `src/runtime/src/runtime/application/reconcile.py` (add `_revert_stale_symlinks`, `_build_expected_targets`, integrate into `run()`, add `reload_failures: list[str]` field to `ReconcileResult`)
- `src/runtime/src/runtime/cli/main.py` (forward-looking reload failure check in reconcile command)

No changes: `domain/`, `ports/`, `adapters/` (reuse seeder as-is — `_repoint_symlink` imported at module level, not modified), `pyproject.toml`, `SeedCacheUseCase`, `ApplyWallpaperUseCase`, provisioning.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 2 intro, Story 2.2 ACs, Implementation notes R5
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-6 (swap = repoint symlinks, symlinks lead), AD-17 (consumer wiring), AD-18 (per-monitor)
- Shared data contract: same folder `shared-data-contract.md` — Swap sequence section (crash recovery: "on next run, ReconcileDesktopStateUseCase reads current.json and re-derives the current/ symlinks from it (idempotent repair)")
- Existing code: `src/runtime/src/runtime/application/reconcile.py` (ReconcileDesktopStateUseCase, _cleanup_stale_symlinks, _derive_skipped, ReconcileResult), `adapters/seeder.py` (repoint_current_symlinks, `_repoint_symlink` at line 55), `adapters/cache.py` (cache_entry_path at line 107)
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-1-atomic-symlink-repoint.md` (swap sequence, scope boundary, D1 mutex protocol, deferred crash-recovery item)
- Deferred ledger: `_bmad-output/implementation-artifacts/deferred-work.md` — rt-2-1 entry (history/save atomicity deferred, crash recovery owned by this story)

## Dev Agent Record

### Agent Model Used

muse-spark-1.2-contributor-free (opencode/muse-spark-1.2-contributor-free)

### Debug Log References

- Implementation of `_revert_stale_symlinks` and `_build_expected_targets` in `application/reconcile.py` with monitor traversal validation and atomic `_repoint_symlink` primitive.
- Integration of recovery call at top of `run()` with INFO/DEBUG logging outside mutex.
- CLI placeholder for `reload_failures` field and non-zero exit handling.
- Unit / integration / CLI tests created and green: 281 passed, 2 skipped.

### Completion Notes List

- Task 1: Added `_revert_stale_symlinks` + `_build_expected_targets` to `ReconcileDesktopStateUseCase`; validates monitor names, compares resolved symlink targets via `_repoint_symlink`, handles missing `current/` and dangling symlinks, idempotent.
- Task 2: Integrated recovery into `run()` before `_ensure_entries`, outside lock, with logging `recovery: reverted %d stray symlink(s)` at INFO and `recovery: no stray symlinks detected` at DEBUG.
- Task 3: Extended `ReconcileResult` with `reload_failures: list[str] = field(default_factory=list)` and updated `cli/main.py` reconcile command to surface reload failures with `ErrorView` and exit 1; structural placeholder for 2.3-2.6.
- Task 4: Created `tests/unit/test_crash_recovery.py` with 15 tests covering partial-swap per layer, full interrupt, idempotency, cache-hit-after-recovery, absent/corrupt, scope lock, missing dir, dangling, traversal guard.
- Task 5: Created `tests/integration/test_crash_recovery_integration.py` with 3 end-to-end scenarios (e2e recovery, history line, concurrent safety).
- Task 6: Created `tests/unit/test_cli_crash_recovery.py` with INFO/DEBUG log assertions and skipped reload-failure placeholder.
- Task 7: Green gate verified — pytest 281 passed 2 skipped, ruff check zero new violations, ruff format clean, mypy strict zero new errors, layering 50 passed.

### File List

- `src/runtime/src/runtime/application/reconcile.py` — added `_revert_stale_symlinks`, `_build_expected_targets`, `reload_failures` field, recovery logging, import `_repoint_symlink`
- `src/runtime/src/runtime/cli/main.py` — reload failure placeholder handling and `reload_failures` in output
- `src/runtime/tests/unit/test_crash_recovery.py` — NEW unit tests
- `src/runtime/tests/integration/test_crash_recovery_integration.py` — NEW integration tests
- `src/runtime/tests/unit/test_cli_crash_recovery.py` — NEW CLI tests

### Change Log

- 2026-09-02: Implemented crash-mid-swap recovery (AC 1-6), CLI placeholder, tests, and green gate.
