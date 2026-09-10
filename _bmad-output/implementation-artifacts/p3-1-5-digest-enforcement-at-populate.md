# Story 1.5: Digest Enforcement at Populate Time

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 1 — Invalidation-Aware Regeneration (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 1.5; PRD v2 FR-8/FR-9; AD-26/AD-27)

## Story

As a developer,
I want every artifact hashed as it is written via `populate_via_staging`,
so that generator-level corruption raises before the entry becomes visible and later verify/repair have real digests to check.

Depends on Story 1.2 (same recorded `meta.json` input-hash fields); must land before Story 2.2 so doctor repair has corrupt-by-digest entries to classify.

## Acceptance Criteria

1. Every artifact listed in `artifact_hashes` is re-hashed at write time and a mismatch raises `CorruptCacheError` BEFORE the staging rename — the corrupt entry never becomes visible (AC 1, FR-8/AD-26)
2. Populated entries are never re-hashed in place (write-once preserved); correction flows only through `DoctorUseCase` repair (AC 2, AD-22)
3. The enforcement helper lives in `adapters/` (next to `cache.py`/`hashing.py`); the error type lives in `domain/` so `application/` CAN catch it without importing `adapters/` (surfacing/quarantine deferred to Story 2.2) (AC 3, AD-25)
4. No hash formula or cache-layout constant is altered (AC 4, AD-21)
5. `tests/architecture/test_layering.py` passes unchanged (AC 5, AR-6)

> DEV-time deviation from the epics-literal draft (for Gate 2 ratification):
> `artifact_hashes` ABSENT → verification SKIPPED (not an error). Evidence:
> 9 existing `test_cache.py` tests populate heterogeneous/legacy shapes
> (wallpaper metas keyed by `content_hash`) through the generic mechanism,
> and production wallpaper seeding bypasses `populate_via_staging` entirely
> (own hardlink + post-place re-hash in `seeder.import_wallpaper`). The
> mechanism stays shape-agnostic; presence of the map opts into full
> enforcement (all 3 production derive sites record it). Malformed map →
> still `CorruptCacheError`. Story 3.1 annotates map-less entries on read.

## Tasks / Subtasks

- [x] Define `CorruptCacheError` in `src/runtime/src/runtime/domain/models.py` (AC: 1, 3)
  - [x] New exception class next to `SeedLockedError` (error-type precedent: application must catch it WITHOUT importing `adapters/` — inward deps only). Docstring links AD-26 / Story 1.5 / consumer Story 2.2
  - [x] Pure `Exception` subclass, stdlib-only (layering: domain allowlist untouched)
- [x] Implement `verify_staging(staging: Path) -> None` in `src/runtime/src/runtime/adapters/cache.py` + hook into `populate_via_staging` (AC: 1, 2, 4)
  - [x] Call AFTER the existing guards (non-empty staging, `meta.json` present — both stay `RuntimeError`) and BEFORE `os.rename`. Raise inside the `try` so the existing `try/finally` + outer `finally` clean staging on every failure path (no orphan `.staging-*`, no partial target)
  - [x] Read `staging/meta.json` (unparseable → `CorruptCacheError`, never a raw `json` crash); require `hash_algorithm == "sha256"` ALWAYS (a declared non-sha256 is writer corruption, map or no map); require `artifact_hashes` to be a `str→str` map WHEN PRESENT (malformed → `CorruptCacheError`); ABSENT map → return without verification per deviation above (heterogeneous/legacy shape; Story 3.1 annotates on read)
  - [x] For each recorded `(relpath, hash)`: `staging/relpath` must exist as a file with `sha256(bytes) == hash` (chunked reads, symlink-following like `hash_file`; broken link / missing file / mismatch → `CorruptCacheError` naming the staging dir, relpath, and reason)
  - [x] Strict both-ways: every FILE under staging (recursive `rglob`, covering WEG's nested `<stem>/effect/*.png` structure) except exactly `staging/meta.json` must be recorded (extra unrecorded file → `CorruptCacheError`); empty dirs ignored (carry no bytes; drain cleanup owns them)
  - [x] No new hash formulas (reuse `adapters/hashing.py` chunked reads), no cache-layout change, no behavior change to the write-once / rename-race / orphan-sweep paths (AD-21 holds)
- [x] Flip AD-26/AD-27 to `[ADOPTED]` in `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-07/delta-phase3-digest-2026-09-10.md` (adoption was gated on this story landing)
- [x] Create `src/runtime/tests/unit/test_populate_enforcement.py` (AC: 1, 2, 4)
  - [x] Happy path: populate_fn writes 2 files + correct meta → `True`, entry published with identical bytes
  - [x] Tampered artifact (meta records wrong hash) → `CorruptCacheError`; target dir NOT created; no `cache/.staging-*` orphan left behind
  - [x] Recorded-but-absent file → `CorruptCacheError`
  - [x] Extra unrecorded file → `CorruptCacheError`
  - [x] Absent `artifact_hashes` map → skip (heterogeneous/legacy); malformed map / wrong `hash_algorithm` / unparseable `meta.json` → `CorruptCacheError` (each, not a raw crash)
  - [x] Nested-subdir artifacts verified by relpath (WEG shape: `staging/<stem>/effect/a.png` recorded as relpath → passes; tampered nested file → `CorruptCacheError`)
  - [x] `meta.json` itself never hashed (entry with only meta + recorded artifacts passes)
  - [x] Existing behavior pinned unchanged: second populate returns `False` (write-once); empty staging → `RuntimeError` (guard order preserved: empty/meta-absent checks run BEFORE digest verify)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_populate_enforcement.py tests/unit/test_cache.py tests/architecture/test_layering.py` and confirm green

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-1-5-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; 16 findings). Operator verdicts
per-item ballot: apply A–J, dismiss X1 confirmed.

Applied:
- A: `UnicodeDecodeError` caught as corrupt (zero-crash complete).
- B: algorithm check precedes the absent-map return (universal pin).
- C: up-front relpath validation + hardened resolve catch.
- D: extras-walk enumeration/relative_to guards.
- E: TOCTOU assumption documented (no behavior change).
- F: orphan asserts everywhere + traversal/UTF-8/nested/algorithm tests.
- G: story :41 rewritten to absent→skip.
- H: AC3 narrowed to placeability (surfacing deferred to 2.2).
- I: AC5 layering appended (epics mapping 1:1).
- J: delta frontmatter adopted.

Dismissed:
- X1 meta.json-as-dir reclassification — equally loud, identical cleanup; guard semantics stand.

DEV-time deviation ratified here: absent-map → skip (see story deviation
note; epics-literal, 9-test evidence, 3.1 annotates on read).

## Dev Notes

### Scope boundary — this story is POPULATE-TIME ENFORCEMENT ONLY

Story 1.5 closes the Epic 1 loop (check → regen → enforced writes). It does **NOT** implement:
- Legacy lazy annotation reads (Story 3.1 — READS pre-FR-8 entries; this story only governs WRITES, which are all new)
- Doctor check/repair taxonomy (Stories 2.1/2.2 — 2.2 catches `CorruptCacheError` / quarantines corrupt entries; this story only RAISES it)
- Cache prune/eviction (Story 3.x)
- Any CLI command, any `application/` use-case change, any change to derive/seed/reconcile call sites (the 3 `populate_via_staging` callers in `derive.py:400,451,505` are untouched — enforcement is inside the shared path)
- Wallpaper import path (`hardlink_or_copy` — link-is-same-inode; no `artifact_hashes` involved; out of scope per epics AC)

### Layering (AD-25, locked)

- Error type in `domain/` (inward-visible to both `adapters/` and `application/`); verification + hook in `adapters/cache.py` only
- `application/` untouched: derive failure policy already exists (palette hard-raise, effects/icons graceful) and now also fires on corruption — desired, no code change
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. Staging layout: artifacts (+ meta.json) at staging root or nested (drain-preserving); meta at root only.
2. Write-once + staging-sibling + rename-race + orphan-sweep semantics unchanged — verify inserts one step, alters none.
3. Equality (not hex-format validation) decides mismatch: computed digests are always hex, so a non-hex recorded value can never match — no extra validator needed.
