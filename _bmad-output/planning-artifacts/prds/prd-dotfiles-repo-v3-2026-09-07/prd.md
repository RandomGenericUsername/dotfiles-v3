---
title: dotfiles-repo-v3 Phase 3 — State Awareness
status: final
created: 2026-09-07
updated: 2026-09-07
---

# PRD — Phase 3: State Awareness

## Context

Phase 1 (provisioning) and Phase 2 (runtime: `dotfiles-runtime wallpaper set / reconcile / inspect`, layered `cache/` + `current/` + `current.json/history.jsonl`, Epic 4 single-source) are done. `docs/99 §27` Phase 3 planned "content hashing, artifact metadata, cache validation, selective regeneration" — the first two shipped in Phase 2 (SHA-256 `wh/ph/eh/ih` keys, per-layer `meta.json`, staging-dir population). Phase 3 therefore owns what Phase 2 deferred: **invalidation-awareness, self-heal, drift detection, bounded growth**. Diagrams: `../phase3-state-awareness-diagrams.md`.

Audience: solo operator (juan david) on Arch Linux. Downstream: `bmad-architecture` (AD-21+), then epics/stories.

## Capabilities

- **CAP-1 Invalidation on input change.** When spine inputs (csg templates, weg catalog, icon templates/mappings) change, only stale layers regenerate (with cascade palette→icons, wallpaper→palette+effects).
- **CAP-2 Cache health.** Corrupt/missing `meta.json` or artifact-hash mismatch never bricks a layer permanently; `cache verify` reports per-entry health.
- **CAP-3 Drift detection + repair.** One command shows and repairs `current.json ↔ current/ symlinks ↔ cache/` divergence (ok/missing/diverged/dangling), including torn-history tolerance policy.
- **CAP-4 Bounded cache.** `cache prune` enforces a pinned keep-policy (active + last-N + seed-pinned); list stays default, prune is explicit.

## Functional Requirements

- FR-1: `dotfiles-runtime reconcile --check-inputs` (or `doctor --check`) recomputes spine input hashes per `shared-data-contract.md` and reports stale layers without mutating.
- FR-2: Stale-layer regeneration reuses the Phase 2 pipeline (staging-dir, write-once, env-overrides) and regenerates the minimal set + cascade.
- FR-3: `dotfiles-runtime doctor` performs the three-way check (store vs symlinks vs cache entries), exits 0 clean / non-zero with machine-readable report on drift.
- FR-4: `doctor --repair` quarantines bad entries (rename-aside, never `rm -rf` user state), repopulates, repoints stray symlinks to last-good `current.json`, appends `history.jsonl` with `trigger: doctor`.
- FR-5: `inspect cache list --verify` adds per-entry health (hash recheck) without changing default list output.
- FR-6: `cache prune [--dry-run --keep N --prune-pinned=false]` removes only unreferenced, non-active, non-pinned entries; dry-run is default-safe; every removal logged.
- FR-7: History reader tolerates a torn trailing line (skip + warn, never crash) — policy decision pinned here, implements rt-3-1 deferred item.

## Non-Functional Requirements

- NFR-1: Hexagonal, synchronous, FS-authoritative (AD-1/AD-3/AD-6/AD-12 hold). New port `IInvalidationQuery`; domain stays pure; `test_layering.py` keeps passing.
- NFR-2: Runtime never writes under install spine except the AD-11 R2 symlink; provisioning never writes under `state_root`.
- NFR-3: Atomicity as Phase 2 (tmp+rename, O_APPEND history); `doctor --repair` is idempotent and re-runnable.
- NFR-4: Performance: `--check-inputs` on a warm cache completes without tool invocation (hash walk only); full verify bounded by single cache walk.

## Non-goals

Desired-state diff engine / declarative convergence (Phase 4). Daemon/watchers/reactive (Phase 5). Parallel execution/plugins (Phase 6). SQLite or multi-backend store. Changing hash formulas, cache layout, or derivation semantics.

## Success signal

On a machine with a warm cache: editing a csg template then running check surfaces exactly the palette (+icons cascade) as stale; `doctor --repair` regenerates only those, desktop reconverges, `history` gains one `doctor` line; corrupting a `meta.json` then running `doctor --repair` heals without manual deletion; `cache prune --dry-run` reports reclaimable entries and prunes only unreferenced ones.

## Open Questions

- OQ-1: Keep-N default and seed-pin policy values (propose N=5, seed always pinned — confirm in architecture).
- OQ-2: Whether `wallpaper set` auto-runs the input-check (cheap) or stays explicit (decision: explicit in Phase 3, auto in Phase 4 reconciler).
- OQ-3: Torn-history repair (truncate tail vs quarantine line) — propose skip+warn, truncate only under `--repair`.
