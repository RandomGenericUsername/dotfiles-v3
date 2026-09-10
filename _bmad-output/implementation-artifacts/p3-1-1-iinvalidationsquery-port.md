# Story 1.1: IInvalidationQuery Port + Pure Stale-Set Computation

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 1 — Invalidation-Aware Regeneration (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 1.1)

## Story

As a developer,
I want a new `IInvalidationQuery` port with a pure stale-set + cascade computation over the domain derivation graph,
so that invalidation logic is testable without I/O and later adapters/CLI share one contract.

## Acceptance Criteria

1. `src/runtime/src/runtime/ports/invalidation_query.py` defines ABC `IInvalidationQuery` with abstract methods `recompute_input_hashes`, `compare_against_meta`, `stale_set_with_cascade` — no concrete I/O, no `os`/`subprocess`/`shutil` FS calls (AC 1, AD-25)
2. The cascade rule wallpaper→palette+effects, palette→icons (AR-2/AD-21) lives in a domain-pure helper `src/runtime/src/runtime/domain/invalidation.py` — stdlib allowlist only, zero I/O imports (AC 2, AD-25)
3. `tests/architecture/test_layering.py` passes unchanged — ports may import domain (inward), nothing new imports outward (AC 3, AD-25)
4. No hash formula or cache-layout constant is altered: `HASH_ALGORITHM` stays `"sha256"`, `palette_entry_hash` / `effects_entry_hash` / `icons_entry_hash` signatures and vectors unchanged (AC 4, AD-21)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/domain/invalidation.py` (AC: 2)
  - [x] Pure cascade helper over the derivation graph: given the set of layers whose recorded input hashes differ, return the stale set closed under cascade (wallpaper→palette+effects, palette→icons) per AR-2/AD-21
  - [x] Operate on layer names + hash strings only (no `Path`, no FS reads); import stdlib allowlist only (mirror `domain/models.py` import discipline)
  - [x] Canonical per-layer derivation input sets DOCUMENTED in the domain
  docstring per `shared-data-contract.md` (AC: 2) — field-level enforcement
  (which `meta.json` fields the adapter reads) lands in Story 1.2's adapter
- [x] Create `src/runtime/src/runtime/ports/invalidation_query.py` (AC: 1)
  - [x] ABC `IInvalidationQuery` with abstract `recompute_input_hashes`, `compare_against_meta`, `stale_set_with_cascade`; ABCs only, no concrete classes in `ports/`
  - [x] Port references domain types only (inward dependency, layering-clean)
- [x] Create `src/runtime/tests/unit/test_invalidation_query.py` (AC: 2)
  - [x] Pure computation tests with fakes — no tmp dirs, no FS, no subprocess: identical input sets → identical stale sets; template-set change → palette+icons stale, effects+wallpaper fresh; catalog change → effects stale only; mappings change → icons stale only
  - [x] Regression pin: existing hashing vectors unchanged (import `hashing` entry-hash helpers against known vectors)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_invalidation_query.py tests/architecture/test_layering.py` and confirm green (AC: 3, 4)

## Dev Notes

### Scope boundary — this story is the PORT + PURE COMPUTATION ONLY

Story 1.1 creates the contract that Stories 1.2–1.5 implement against. It does **NOT** implement:
- Spine input-hash walk adapter (Story 1.2)
- `--check-inputs` CLI report (Story 1.3)
- Selective regeneration + cascade reconverge (Story 1.4)
- Digest enforcement at populate (Story 1.5)
- Any `adapters/`, `application/`, or `cli/` changes

### Layering (AD-25, locked)

- `domain/invalidation.py`: pure helper, stdlib allowlist, no `os`/`pathlib`/`subprocess`/`shutil`
- `ports/invalidation_query.py`: ABCs only; may import `domain` (inward); must not import `adapters`/`application`/`cli`
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Stale vs corrupt boundary (pinned 2026-09-10 fold-in)

This story classifies **staleness** (recorded input hashes differ from recomputed spine inputs). **Artifact-hash mismatch is NOT staleness** — it is the corrupt-by-digest domain of Story 1.5 (`CorruptCacheError` at populate) and doctor `--verify` (Stories 2.2/3.1). Do not blur the two: `stale_set_with_cascade` consumes input-hash comparisons only.

## Review Record (Gate 2, 2026-09-10)

Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
No blockers. Operator approved: apply 1–7, dismiss 1–5.

Applied:
1. Port `recompute_input_hashes` → `Mapping[DerivationLayer, str | None]` (absence expressible).
2. `sorted(unknown, key=repr)` at both ValueError sites (mixed garbage keeps the ValueError contract).
3. `""` → stale (explicit); non-`str` → `ValueError` (fail-loud parity with unknown layers).
4. `close_stale_set` (+ port `stale_set_with_cascade`) annotation widened to `Collection` (honest contract, behavior unchanged).
5. 11 new tests: mutable-set + non-mutation, overlapping input, case-mismatch, recorded-None, both-None, empty-string, empty-compare pin, non-string raises, one-sided unknown, cascade-covers-every-layer + full-mapping equality, palette arg-order tripwire.
6. Story hygiene: boxes `[x]`, derivation-input subtask narrowed to doc-only (enforced in 1.2).
7. `LAYER_ORDER` comment reworded (no implied outward dependency, AD-25).

Dismissed:
1. Concrete port methods — Gate-1 story mandates abstract; pure-ABC convention is mechanically enforced; single 1.2 call site, no divergence risk.
2. `MappingProxyType` — `types` not in the domain allowlist (would fail `test_layering.py`); full-mapping equality test covers accidental rewiring.
3. Raise on `diff({}, {})` — unreachable (1.2 always passes 4 layers); vacuous-fresh pinned by test instead.
4. Broaden `type: ignore` codes — matches repo convention; no CI mypy-on-tests.
5. Extra `hashing.py` vectors — out of scope; owned by hashing's own suite.
