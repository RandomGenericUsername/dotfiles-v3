# Story 1.2: Spine Input-Hash Walk Adapter vs meta.json

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 1 — Invalidation-Aware Regeneration (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 1.2)

## Story

As a developer,
I want an adapter that recomputes spine input hashes with Phase 2 canonicalization and compares them against `meta.json`,
so that stale layers are detected by hash-compare only.

## Acceptance Criteria

1. `src/runtime/src/runtime/adapters/invalidation.py` implements `IInvalidationQuery`: `recompute_input_hashes` hashes the four spine inputs (csg templates dir, weg catalog file, icon templates path, icon mappings path) with Phase 2 canonicalization; `compare_against_meta` reports fresh/stale per layer with the differing layer identified — templates→palette, catalog→effects, icon-inputs→icons (layer granularity: half-granularity inside icons has no downstream consumer since 1.4 regenerates per-layer) (AC 1, AD-21)
2. Canonicalization matches `shared-data-contract.md` exactly — dir → `canonical_hash_dir`, file → `hash_file` (the `_hash_path_input` rule from `application/derive.py`, re-implemented locally in the adapter, never imported across the layer boundary); no new formulas (AC 2, AR-1)
3. Stale-set computation uses recorded *input* hashes only — artifact-hash mismatch is NOT staleness; it is the corrupt-by-digest domain of Story 1.5 / doctor `--verify` (boundary pinned 2026-09-10) (AC 3)
4. All filesystem I/O lives in `adapters/` only (AC 4, AR-6)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/adapters/invalidation.py` (AC: 1, 4)
  - [x] Class `InvalidationQueryAdapter(IInvalidationQuery)`; ctor takes `state_root: Path` plus the four resolved spine inputs (`templates_dir`, `catalog_path`, `icon_templates`, `icon_mappings`: each `Path | None`, `None` = absent input)
  - [x] Composition owns discovery: the adapter does NOT import `find_*` from `application/derive.py` (layering: adapters never import application). Callers (1.3 CLI wiring / 1.4 use case) resolve via `derive.find_templates_dir / find_effects_catalog / find_icon_templates / find_icon_mappings` and inject. Document this seam in the class docstring
  - [x] Local `_hash_path_input` equivalent (dir → `canonical_hash_dir`, file → `hash_file` from `adapters/hashing.py`); comment cites `application/derive.py::_hash_path_input` as the canonicalization source so the two can never silently diverge
  - [x] `recompute_input_hashes()` returns per-layer spine hashes: `palettes` → template_set_hash; `effects` → catalog_hash; `icons` → `f"{templates_hash}\x00{mappings_hash}"` (`\x00`-join is an encoding, not a hash formula — same separator convention as `canonical_hash_dir` D2; AD-21 holds); any `None` input → that layer `None` (absent fails loud as stale per p3-1-1 semantics)
  - [x] `recorded_inputs(layer, entry_hash) -> str | None` reads `state_root/cache/<layer>/<entry_hash>/meta.json` and returns the recorded input encoding in the SAME field layout (`input_template_hash` / `input_catalog_hash` / `input_templates_hash\0input_mappings_hash`); missing `meta.json` → `None` (stale → regen rebuilds); unparseable `meta.json` → `ValueError` naming the entry (loud; corruption taxonomy belongs to doctor Story 2.1, not this story)
  - [x] `compare_against_meta(recorded, recomputed)` excludes the `wallpapers` layer from both mappings before delegating to domain `diff_input_hashes` + `close_stale_set`, documented loudly: wallpaper is content-addressed (a changed wallpaper is a NEW entry, never stale); its freshness is structural (entry existence, owned by doctor Story 2.1), not input-hash-compared
  - [x] `stale_set_with_cascade` pure-delegates to domain `close_stale_set`
  - [x] Per-layer recorded field map (from `cache.py` docstring + `shared-data-contract.md`): palette ← `input_template_hash`; effects ← `input_catalog_hash`; icons ← `input_templates_hash` + `input_mappings_hash`. Structural links (`source_wallpaper_hash`, `source_palette_hash`) are NEVER compared (entry identity, not staleness)
- [x] Create `src/runtime/tests/unit/test_invalidation_query_adapter.py` (AC: 1, 2, 3)
  - [x] Fixture `tmp_path` install spine (templates dir with 2 files, catalog file, icon templates dir, mappings file) + fixture cache entries with `meta.json`; zero tools, zero network
  - [x] Warm (matching) → stale set empty
  - [x] Edited template file → palette stale (+icons via cascade in the e2e assertion); catalog edit → effects only; mappings edit → icons only; differing input identified per layer
  - [x] `None` spine input (unresolved discovery) → that layer stale
  - [x] Missing `meta.json` → `recorded_inputs` returns `None`; corrupt `meta.json` → `ValueError`
  - [x] Canonicalization parity: adapter-computed hashes equal direct `canonical_hash_dir` / `hash_file` calls on the same fixtures (proves same formula, detects drift)
  - [x] Wallpapers-layer diffs ignored by `compare_against_meta` (pinned convention); artifact-hash mismatch NOT classified stale (boundary: construct entry with matching inputs but corrupt artifact → NOT stale here; Story 1.5/2.2 own it)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_invalidation_query_adapter.py tests/architecture/test_layering.py` and confirm green (AC: 4)

## Dev Notes

### Scope boundary — this story is the ADAPTER ONLY

Story 1.2 builds the hash-walk + compare mechanics. It does **NOT** implement:
- `--check-inputs` CLI report (Story 1.3 — consumes this adapter)
- Selective regeneration + cascade reconverge (Story 1.4)
- Digest enforcement at populate (Story 1.5)
- Doctor check/repair taxonomy (Stories 2.1/2.2)
- Any `application/` use case or `cli/` command

### Layering (AD-25, locked)

- New code lives in `adapters/` only; may import `domain`, `ports`, `adapters.hashing`
- MUST NOT import `application/derive.py` (neither `find_*` discovery nor private `_hash_path_input`) — adapters never import application; discovery is injected by the composition root
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions pinned by this story (later stories rely on them)

1. Icons two-input encoding is `\x00`-joined `templates\0mappings` — an equality-encoding, not a hash; recorded and recomputed sides must use identical field order.
2. `wallpapers` excluded from input-hash compare (content-addressed invariant).
3. Missing meta → `None` (stale); corrupt meta → `ValueError` (doctor classifies).
4. Structural hash links (`source_*`) never compared.

## Review Record (Gate 2, 2026-09-10)

Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
18 findings. Operator verdicts per-item ballot: apply A–L, dismiss X1–X3.

Applied:
- A: kind-specific spine hash helpers (`_hash_dir_input` / `_hash_file_input` / `_hash_path_input`); unreadable/misplaced spine input raises `RuntimeError` with path; `None` reserved for absent-by-config.
- B: meta-read three-way split — missing→`None`, is-dir→`ValueError` corrupt, other `OSError`→`None` (fail-safe toward regen).
- C: `""`/wrong-type fields normalize to `None` via `_present_str` at the I/O boundary.
- D: wallpapers `recorded_inputs` returns `None` (exclusion total on both sides).
- E (subsumed by I): absence parametrized over all four inputs with exact stale sets.
- F: wallpapers test proves exclusion (matching stays fresh, differing detected).
- G: branch pins — half-missing field, non-dict JSON, null fields, all-None spine, invalid entry hash, neither-dir-nor-file, wrong-kind paths, seed asserts, split maxsplit.
- H: `source_*` divergence with matching inputs stays fresh.
- J: missing/wrong-type fields → `None` tested.
- K: AC 1 narrowed to layer granularity (no port rework) + icon-templates-dir edit test.
- L: boxes checked; this record.

Dismissed:
- X1 degrade-spine-to-None — environment problems stay loud (superseded by A).
- X2 raise on `compare({},{})` — consistency with approved p3-1-1 D3 (vacuous-fresh).
- X3 port return-type change — approved port stability; no consumer for the detail.
