# Story 3.2: `cache prune` Keep-Policy Eviction Core

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 3 — Cache Verify + Prune (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 3.2; AD-24/AR-5)

## Story

As a developer,
I want a `PruneUseCase` in `application/` enforcing keep active + last-N (default 5) + seed-pinned,
so that eviction is bounded and live/seed state can never be deleted.

## Key design decision (seed-pin mechanism — Gate 1 review)

No seed-pin mechanism exists today. Proposal: **seed pins are derived (read-only)
from the OLDEST `history.jsonl` line whose `trigger == "seed"`** — the first-run
seed records `wallpaper/palette/effects/icons` hashes, which become the pinned
`(layer, hash)` set. No new write path, no seed change, no new state file. If
history is absent/empty/no seed line, the pin set is empty (only active +
last-N protect) — a documented degradation, never a crash.

Recency source: `meta.json` timestamps (`generated_at` for palettes/effects/icons,
`imported_at` for wallpapers). An entry whose meta is missing/unparseable/undated
is **protected** (never pruned) — prune never deletes what it cannot classify.

## Acceptance Criteria

1. Active entries (referenced by `current.json` for the active wallpaper) are never removed (AC 1, AD-24)
2. The N most recent entries per layer (default N=5) are never removed (AC 2, AD-24)
3. Seed-pinned entries (derived from the seed history line) are never removed (AC 3, AD-24)
4. Only entries that are unreferenced AND outside last-N AND not seed-pinned are selected for removal; `PrunePlan` reports the candidate set and keep counts (per-removal reason strings are produced at removal time by Story 3.3's logging) (AC 4, AR-5)
5. The use case lives in `application/`, performs NO I/O itself (state via `IStateRepository`; entries + seed pins via injected callables implemented in `adapters/`), and `tests/architecture/test_layering.py` passes unchanged (AC 5, AR-6)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/application/prune.py` (AC: 1–5)
  - [x] `CacheEntryRef = (entry_hash: str, timestamp: str | None)` frozen dataclass (layer-agnostic entry + recency; `None` = undated → protected)
  - [x] `PrunePlan(removals: dict[str, tuple[str, ...]], kept: dict[str, int], total_removable: int)` — per-layer sorted hash tuples; no hashes outside the four layers
  - [x] `PruneUseCase(state_repo: IStateRepository, entries_for: Callable[[str], Sequence[CacheEntryRef]], seed_pins: Callable[[], Mapping[str, set[str]]], keep: int = 5)`
  - [x] `run() -> PrunePlan`:
    1. Active: `load_current()` (absent → active = ∅, NOT an error — prune still works on a cache with no state; documented), collect the four entry hashes per layer (wallpaper always; palette/effects/icons when non-null)
    2. Pins: `seed_pins()` → `{layer: {hash}}`
    3. Per layer: `entries_for(layer)`; sort by timestamp descending (undated last); compute the kept set = active ∪ pinned ∪ top-`keep` by recency ∪ undated; candidates = the rest
    4. Emit candidates (sorted) with deterministic order; `total_removable` = sum
  - [x] Zero I/O in this module: `state_repo` is a port; `entries_for`/`seed_pins` are injected; no `os`/`pathlib` FS calls, no adapter import (mirror `CheckInputsUseCase`)
- [x] Add an adapter source `src/runtime/src/runtime/adapters/prune_source.py` (AC: 5)
  - [x] `entries_for(state_root, layer) -> list[CacheEntryRef]`: list valid `<64hex>` entry dirs (reuse the `InspectCacheUseCase` name rule), read `meta.json` and extract `generated_at`/`imported_at`; missing/corrupt meta or unreadable → `CacheEntryRef(hash, None)` (→ protected); never raises for a single bad entry
  - [x] `seed_pins(state_root) -> dict[str, set[str]]`: read `history.jsonl`, find the OLDEST `trigger == "seed"` line, map its `wallpaper/palette/effects/icons` fields to `(wallpapers/palettes/effects/icons)`; absent/unparseable history → `{}`; torn tail tolerated (skip, reuse the existing reader policy semantics; no mutation)
- [x] Create `src/runtime/tests/unit/test_prune.py` (AC: 1–4)
  - [x] Pure use-case tests with fakes (no FS): active excluded; top-5 excluded; pinned excluded; old unreferenced selected; exactly the boundary (6th-oldest removed, 5th-oldest kept); undated protected; keep override (`keep=2`); absent state → all-but-recent/pruned; deterministic ordering; empty layer; no cross-layer leakage (same hash string in two layers is independent)
  - [x] Adapter tests with `tmp_path`: `entries_for` reads timestamps; corrupt meta → undated; `seed_pins` picks the oldest seed line and ignores later lines/triggers; absent history → `{}`
  - [x] Layering: `application/prune.py` imports only `domain` + `ports` (assert via the existing gate run)
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_prune.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — plan only, no deletion

Story 3.2 computes the removal set. It does **NOT** delete anything (Story 3.3 owns
the CLI, dry-run default, `rm`/quarantine, and per-removal logging), and does not
touch doctor/verify.

### Layering (AD-25, locked)

- `application/prune.py`: pure; `IStateRepository` + injected callables; no adapter import
- `adapters/prune_source.py`: all FS reads (cache dirs, metas, history); never writes, never deletes
- CLI wiring (3.3) composes the two; `test_layering.py` stays green

### Conventions consumed (do not redefine)

1. Valid entry-dir name = 64-char lowercase hex (same rule as the lister; staging/quarantine/symlinks skipped).
2. Recency = meta timestamp; undated/corrupt = protected (conservative).
3. Semantics: verifies but never mutates.
4. Keep-policy = active ∪ pinned ∪ top-N ∪ undated; everything else is a candidate. Idempotence and logging are Story 3.3's contract.

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-3-2-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; ~16 findings). Operator verdicts
per-item ballot: apply A–H, dismiss X1–X2 confirmed.

Applied:
- A (HIGH): timestamps canonicalized to fixed-width UTC in the adapter, so the lexicographic recency sort is chronologically correct (variable-precision `_now_iso_z` output previously mis-sorted, evicting newer entries first).
- B: `seed_pins` tolerates only a torn TRAILING line; mid-file corruption → no pins (fail safe, never pin a later seed).
- C: symlinked `cache/` root refused (mirrors `InspectCacheUseCase`).
- D: symlinked `meta.json` → undated (protected).
- E: history read via `O_NOFOLLOW` (closes the symlink TOCTOU).
- F: per-monitor `source_hash` wallpapers protected by the active set.
- G: tests — fractional/offset normalization, symlinked cache/layer/entry/meta, tie determinism, undated-does-not-consume-keep, corrupt-first-seed → no pins, monitor protection.
- H: story field `kept_layer_count` → `kept`; AC4 reason wording amended (Story 3.3 logging); boxes + this record.

Dismissed:
- X1 shared `_is_entry_name` domain helper — 3-line stable rule; cross-cutting refactor out of scope.
- X2 per-removal reason in `PrunePlan` — one policy reason for all candidates; per-item reasons belong to 3.3 logging (AC amended).

Verification: 751 unit/architecture + 68 integration passed, ruff + format
clean, mypy strict clean on prune.py + prune_source.py.
