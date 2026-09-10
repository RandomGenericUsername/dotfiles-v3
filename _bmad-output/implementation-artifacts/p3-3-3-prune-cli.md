# Story 3.3: Prune CLI — Explicit, Dry-Run-Safe, Logged, Idempotent

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 3 — Cache Verify + Prune (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 3.3; AD-24/AR-5)

## Story

As a user,
I want `cache prune [--dry-run --keep N --prune-pinned]` to be explicit and safe by default,
so that `--dry-run` reports reclaimable entries and real prunes remove only what was reported.

## Scope note (Gate 1)

- Command path: the existing cache commands are nested (`inspect cache list`), so prune lands at **`inspect cache prune`** (consistent with `--verify` on `inspect cache list`). The epics' `cache prune` shorthand is satisfied.
- `--prune-pinned` is a boolean flag defaulting FALSE (epics' `--prune-pinned=false`): by default seed-pinned entries are protected; setting it opts into pruning them too.
- Removals are DELETIONS (`rmtree`) — prune's purpose is reclaiming space; doctor's rename-aside quarantine is for corrupt entries, not eviction.

## Acceptance Criteria

1. `inspect cache prune --dry-run` reports the reclaimable entries (per Story 3.2's `PrunePlan`) and removes nothing (AC 1, FR-6 default-safe)
2. `inspect cache prune` (no `--dry-run`) removes EXACTLY the planned set; every removal is logged; re-running is a no-op success (idempotent) (AC 2, AD-24/NFR-3)
3. `--keep N` overrides the default 5; `--prune-pinned` (default False) when set allows seed-pinned entries to be pruned; active + recent + undated remain protected regardless (AC 3, AD-24)
4. Removal validates each target (known layer, 64-hex hash, real dir under `cache/<layer>`, not a symlink/escape) and never touches anything outside the plan (AC 4)
5. Prune runs under the seed mutex so it cannot race a concurrent `wallpaper set`/reconcile into deleting a just-activated entry (AC 5, R3)
6. The use case stays `application/`-pure; removal I/O lives in `adapters/`; `test_layering.py` passes unchanged (AC 6, AR-6)

## Tasks / Subtasks

- [x] Extend `PruneUseCase.run()` in `src/runtime/src/runtime/application/prune.py` (AC: 3)
  - [x] `run(prune_pinned: bool = False)`; when `prune_pinned` is True, omit the seed-pin layer from the protected set (active + top-N + undated still protected)
- [x] Add `remove_entry(state_root, layer, entry_hash) -> bool` to `src/runtime/src/runtime/adapters/prune_source.py` (AC: 2, 4)
  - [x] Validate: known layer, 64-char lowercase hex, `cache/layer` not symlinked, target resolves inside `cache/<layer>`, target is a real dir (not symlink); any violation → `ValueError` (never a silent delete)
  - [x] Absent target → `False` (idempotent no-op); present → `shutil.rmtree`, log one `logger.info("prune: removed cache/%s/%s", layer, entry_hash)`, return `True`
  - [x] Never follow symlinks; never delete outside the validated path
- [x] Add `inspect cache prune` to `src/runtime/src/runtime/cli/main.py` (AC: 1, 2, 5)
  - [x] Flags: `--dry-run` (bool, default False), `--keep N` (int, default 5), `--prune-pinned` (bool, default False)
  - [x] `_run_prune(dry_run, keep, prune_pinned)` composition: resolve `state_root`; build `PruneUseCase` with the `entries_for`/`seed_pins` adapter callables; acquire `FlockSeedMutex(state_root/".seed.lock").hold(blocking=True)` around plan + removals; when not dry-run, `remove_entry` each planned hash
  - [x] Render via `cli-output`: plain (`reclaimable: N` + per-layer hashes for dry-run; `reclaimed: N` for real) + machine-readable object `{dry_run, kept, removals, total_removable, removed, removed_count}`; exit 0 (idempotent success), `ValueError`/`OSError` → `ErrorView` exit 1
- [x] Create `src/runtime/tests/unit/test_prune_cli.py` (AC: 1–5)
  - [x] Use case: `prune_pinned=True` moves seed-pinned entries into removals; default keeps them
  - [x] Adapter `remove_entry`: removes a valid dir + logs; absent → False; unknown layer / bad hash / symlinked entry / symlinked `cache` → `ValueError`; never deletes outside
  - [x] CLI (real tmp state): `--dry-run` removes nothing (FS snapshot identical) but reports; real prune deletes exactly the planned set; second real prune is a no-op (exit 0, removed_count 0); `--keep 1` changes the set; `--prune-pinned` includes pins; exit-code mapping; mutex-held structural check
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_prune_cli.py tests/unit/test_prune.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary

- No repair/verify changes; no new policy — prune consumes Story 3.2's plan verbatim.

### Layering (AD-25, locked)

- `application/prune.py` stays pure; `remove_entry` + sources in `adapters/prune_source.py`; CLI composes + locks; `test_layering.py` green.

### Conventions consumed

1. `PrunePlan` is authoritative — removal iterates its `removals` only.
2. Entry-dir validity = 64-lowercase-hex (shared rule).
3. Mutating commands are explicit and logged; dry-run is the safe default path.
4. Idempotence = a second run finds nothing to remove.

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-3-3-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; ~20 findings). Operator verdicts
per-item ballot: apply A–I, dismiss X1 confirmed.

Applied:
- A: `remove_entry` hardened — resolve-name check, refuse mid-race symlink, `rmtree(target)` (named inode), vanish → idempotent `False`.
- B: `--dry-run` takes NO mutex (was creating `state_root` + `.seed.lock`).
- C: partial removal accumulates failures, reports the count, then raises (no silent abort).
- D: `removed_count` + `removed_hashes` in the object; removed hashes listed in plain output; root logging configured at INFO when unset.
- E (Medium): `seed_pins` fails CLOSED on mid-file history corruption (raise) — no longer unpins seed defaults.
- F: `--keep` `min=0` (usage error).
- G: refuse to prune when `current.json` is absent (fail-closed).
- H: `prune_source` docstring updated (no longer "read-only, never deletes").
- I: tests (removal races/escape/squatter, absent-state refusal, invalid keep, removed_count, failure → exit 1, dry-run side-effect-free) + story hygiene.

Dismissed:
- X1 top-level `cache` alias — nesting (`inspect cache prune`) is the established Story 3.1 contract; documented in the story Scope note.

Verification: 771 unit/architecture + 68 integration passed, ruff + format
clean (only pre-existing B008), mypy strict clean on prune.py + prune_source.py.
