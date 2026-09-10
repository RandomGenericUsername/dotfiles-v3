# Story 1.4: Minimal Selective Regeneration + Cascade + Reconverge

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 1 — Invalidation-Aware Regeneration (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 1.4)

## Story

As a user,
I want stale layers (plus cascade) regenerated through the Phase 2 pipeline and the desktop reconverged,
so that after a template edit only what changed rebuilds and the desktop picks it up.

## Acceptance Criteria

1. Given the stale set (e.g. palette + icons cascade from Story 1.3), regeneration rebuilds ONLY those through the Phase 2 pipeline (staging-dir, write-once, per-call env-overrides); fresh layers see zero tool invocations (AC 1, FR-2)
2. The run finishes with repointed `current/`, saved `current.json`, exactly one `history.jsonl` line (trigger `regenerate`), and consumer reload (AC 2)
3. Repair/regeneration is idempotent and re-runnable: a second run is a no-op (check fresh → nothing to do, zero invocations) (AC 3, NFR-3)
4. Absent state (no `current.json`) fails loud with `ValueError` (never seeds, never derives blind) (AC 4)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/application/regenerate.py` (AC: 1, 2, 3, 4)
  - [x] Frozen dataclass `RegenerateResult(regenerated, state: DesktopState, repointed=(), reload_failures=())` — absent state raises instead of returning `None` (`regenerated` = layer names rebuilt this run; empty = no-op)
  - [x] Class `RegenerateStaleUseCase` with collaborators `(check: CheckInputsUseCase, pipeline: DerivationPipeline, state_repo: IStateRepository, reconcile: ReconcileDesktopStateUseCase)` — all same-layer (`application/`) or ports; NO new ports; NO adapters constructed here (composition wires them)
  - [x] `run() -> RegenerateResult`:
    1. `check.run()` → stale set (absent state raises `ValueError` from the check; propagate, AC 4). Empty stale → return `RegenerateResult(regenerated=frozenset(), state=current)` — no-op, zero invocations (AC 3).
    2. Resolve the active wallpaper bytes from the cache (truth per AD-16 hardlink invariant): `cache_entry_path(state_root, "wallpapers", wh) / "wallpaper.png"` — the use case needs `state_root: Path`; missing file → `ValueError` (loud; repopulation belongs to doctor Story 2.2, not this story). NEVER fall back to `WallpaperEntry.source_path` (may be deleted; cache survives by design).
    3. If `palettes` stale: `palette_entry, _ = pipeline.ensure_palette(wallpaper_path, wh)` (changed inputs → new hash → miss → generate via staging-dir + env-overrides, inherited Phase-2 behavior; already-derived → hit, no tool run).
    4. If `effects` stale: `effects_entry, _ = pipeline.ensure_effects(wallpaper_path, wh)` (same miss/hit semantics).
    5. If `icons` stale OR palette was regenerated this run: `icons_entry, _ = pipeline.ensure_icons(new_palette_hash)` — the CASCADE, structural: icons key on `palette_hash`, so a new palette is an automatic miss. Pass the POST-step palette hash (fresh recorded one if palette untouched, new one if rebuilt). Never pass the stale recorded hash.
    6. Persist: `state_repo.save(dataclasses.replace(state, palette=..., effects=..., icons=...))` with ONLY the layers touched (fresh entries carried over unchanged).
    7. Converge: `reconcile.run(trigger="regenerate")` — re-ensures referenced entries (hits now), performs the swap sequence, saves `current.json`, appends the single history line, reloads all four consumers. Return `RegenerateResult(regenerated=<rebuilt layers>, state=reconcile.state)`.
  - [x] Fresh layers are untouched BY CONSTRUCTION: `ensure_*` short-circuits on cache hit (hash walk only, no tool invocation) — the minimality test below proves it with counting fakes; no special-casing per layer in this use case
- [x] Wire `reconcile --regenerate-stale` in `src/runtime/src/runtime/cli/main.py` (AC: 2, 4)
  - [x] Add `regenerate_stale: bool = typer.Option(False, "--regenerate-stale", help=...)` to `reconcile`, symmetric with `--check-inputs`; `--check-inputs` and `--regenerate-stale` together → `ErrorView` + exit 2 (mutually exclusive: read vs mutate)
  - [x] New composition helper `_run_regenerate_stale()` mirroring `_run_check_inputs` + `_run_reconcile` wiring: `state_root`/`install_spine` absolute; `JsonStateRepository`; spine paths via `derive.find_*`; `InvalidationQueryAdapter`; `CheckInputsUseCase`; `DerivationPipeline(state_root, seeder, csg, weg, itr, install_spine)` (mirror `_run_wallpaper_set`'s construction); `ReconcileDesktopStateUseCase` with `_build_reloaders(state_root)`; `CacheSeeder` + `FlockSeedMutex` shared instances
  - [x] Render via `cli-output`: plain summary (`regenerated: palette, icons` or `already converged: all layers fresh`) + machine-readable object `{regenerated: [...], repointed, reload_failures}`; reload failures surface per-consumer + exit non-zero exactly like the `reconcile` path (R5); absent state → `ErrorView` + exit 1
- [x] Create `src/runtime/tests/unit/test_regenerate_stale.py` (AC: 1, 2, 3)
  - [x] Use-case tests with fakes: counting csg/weg/itr adapters (record invocations), fake seeder/ports — template-stale fixture → csg invoked exactly once, itr invoked exactly once (cascade via NEW palette hash even though icon inputs unchanged — assert the icons call received the new palette hash), weg ZERO invocations (effects fresh); all-fresh fixture → zero invocations everywhere + empty regenerated
  - [x] Icons-cascade-target test: palette regenerated + icon inputs unchanged → `ensure_icons` called with the NEW palette hash (catches stale-hash pass-through, the load-bearing bug this story exists to prevent)
  - [x] Missing cached `wallpaper.png` → `ValueError` (no source_path fallback — assert by removing the cached file while keeping `source_path` valid)
  - [x] Idempotency test: run twice against the same fixture state; second run returns empty regenerated + zero tool invocations (structural: post-regen pointers match spine inputs → check fresh)
  - [x] History/reload at use-case level with fake reloaders: exactly one history line with trigger `regenerate`; reload failures propagate per-consumer (mirror R5 semantics via the composed reconcile fake)
  - [x] CLI shape tests (monkeypatched `_run_regenerate_stale`, mirroring 1.3): exit 0 + summary; `--check-inputs --regenerate-stale` together → exit 2; absent state → exit 1; flag-off default still takes the swap path (extend 1.3's test or replicate)
  - [x] NO real-desktop e2e at CLI level (reloaders would hit live binaries; the `conftest.py` no-desktop guard + Phase-2 integration coverage own that surface) — hermetic use-case e2e with `tmp_path` state/spine + real `DerivationPipeline` + fake tool adapters covers derive→save→reconcile(fake reloaders)→history end to end
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_regenerate_stale.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — this story is SELECTIVE REGEN + CONVERGE ONLY

Story 1.4 closes the Epic 1 loop (check → regen → reconverge). It does **NOT** implement:
- Digest enforcement at populate (Story 1.5 — populate path unchanged here)
- Doctor check/repair taxonomy (Stories 2.1/2.2 — 2.2 will CALL this use case programmatically for the repopulate step; keep it import-clean for that)
- Cache prune/eviction (Story 3.x — orphaned old-hash entries stay in cache; removal is eviction's job, never regen's)
- Daemon/watchers/auto-check (deferred: explicit now, auto in Phase 4)

### Layering (AD-25, locked)

- New use case in `application/`; composes same-layer units (`CheckInputsUseCase`, `DerivationPipeline`, `ReconcileDesktopStateUseCase`) + ports (`IStateRepository`); constructs NO adapters (composition wires everything)
- Keep the use case import-clean for Story 2.2 reuse: no CLI types, no `typer`, no `cli_output` in `application/regenerate.py`
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Load-bearing semantics (do not simplify away)

1. Regen converges to CURRENT-INPUT state; `reconcile` alone converges to RECORDED state (stale entries are hits, so reconcile without regen changes nothing) — this use case is the bridge, not a duplicate.
2. Cascade is structural (content-addressed keys), but the NEW-palette-hash pass-through is explicit code — the #1 regression surface; the cascade-target test pins it.
3. Write-once preserved: regen never deletes/overwrites entries (new hashes = new dirs); orphans are prune's domain.
4. Single wallpaper path: per-active-wallpaper derivation (Phase-2 `apply` semantics); monitors affect backends, not derivation.
5. History trigger string is exactly `regenerate` (new trigger alongside `set`/`reconcile`/`seed`/`doctor`).

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-1-4-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; 18 findings). Operator verdicts
per-item ballot: apply A–L, dismiss X1–X2.

Applied:
- A: CAS compares the derivation projection (wallpaper + 3 entry hashes), not wallpaper alone.
- B: unknown stale tokens raise `ValueError`.
- C: stale-but-absent palette/effects heal by derivation; icons guard kept as defensive invariant.
- D: no-op validates wallpaper bytes.
- E: seeder.py trigger docstring extended.
- F: absent test exercises the load-None branch.
- G: regenerate JSON object gains state hashes.
- H: repair-path docstring note (next reconcile repairs).
- I: e2e asserts repoint (non-empty + targets in new entries).
- J: R5 reload-failure passthrough test (no rollback).
- K: no-fallback proof with a valid source file.
- L: boxes checked; line 25 corrected; this record.

Dismissed:
- X1 same-hash skip — cryptographically impossible (new hash differs whenever inputs differ).
- X2 check/load reorder — no semantic effect post-projection-CAS.
