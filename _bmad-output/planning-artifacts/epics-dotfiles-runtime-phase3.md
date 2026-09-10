---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-09-07/prd.md
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-09-07/.memlog.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-07/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-07/.memlog.md
  - _bmad-output/planning-artifacts/phase3-state-awareness-diagrams.md
  - _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-09-10/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-07/delta-phase3-digest-2026-09-10.md
amended: 2026-09-10 (cache-integrity fold-in: FR-8/FR-9, AR-10/AR-11, Story 1.5; parent CE validation intact)
---

# dotfiles-repo-v3 - Epic Breakdown (Phase 3: State Awareness)

## Overview

This document provides the complete epic and story breakdown for dotfiles-repo-v3 Phase 3 State Awareness, decomposing the Phase 3 PRD (invalidation-awareness, self-heal, drift detection, bounded growth), the Phase 3 Architecture spine (AD-21..AD-25, inheriting parent AD-1..AD-20 read-only), and the MG phase3-state-awareness-diagrams into implementable stories on the Phase 2 runtime (`src/runtime/src/runtime/{domain,ports,adapters,application,cli}`).

## Requirements Inventory

### Functional Requirements

FR-1: `dotfiles-runtime reconcile --check-inputs` (or `doctor --check`) recomputes spine input hashes per shared-data-contract and reports stale layers without mutating. (CAP-1)
FR-2: Stale-layer regeneration reuses the Phase 2 pipeline (staging-dir, write-once, env-overrides) and regenerates the minimal set + cascade (wallpaper→palette+effects, palette→icons). (CAP-1)
FR-3: `dotfiles-runtime doctor` performs the three-way check (store vs symlinks vs cache entries), exits 0 clean / non-zero with machine-readable report on drift. (CAP-3)
FR-4: `doctor --repair` quarantines bad entries (rename-aside, never `rm -rf` user state), repopulates, repoints stray symlinks to last-good `current.json`, appends `history.jsonl` with `trigger: doctor`. (CAP-3)
FR-5: `inspect cache list --verify` adds per-entry health (hash recheck) without changing default list output. (CAP-2)
FR-6: `cache prune [--dry-run --keep N --prune-pinned=false]` removes only unreferenced, non-active, non-pinned entries; dry-run is default-safe; every removal logged. (CAP-4)
FR-7: History reader tolerates a torn trailing line (skip + warn, never crash) — implements rt-3-1 deferred item. (CAP-3)
FR-8: Digest enforcement at populate time — every artifact is hashed as it is written via `populate_via_staging`; mismatch vs recorded `artifact_hashes` raises `CorruptCacheError` before the staging rename. (fold-in 2026-09-10, AD-26)
FR-9: Legacy lazy annotation — entries without `artifact_hashes` stay usable (healthy-until-proven-corrupt); first `--verify` annotates them, never fails them. No migration. (fold-in 2026-09-10, AD-27)

### NonFunctional Requirements

NFR-1: Hexagonal, synchronous, FS-authoritative (AD-1/AD-3/AD-6/AD-12 hold). New port `IInvalidationQuery`; domain stays pure; `test_layering.py` keeps passing.
NFR-2: Runtime never writes under install spine except the AD-11 R2 symlink; provisioning never writes under `state_root`.
NFR-3: Atomicity as Phase 2 (tmp+rename, O_APPEND history); `doctor --repair` is idempotent and re-runnable.
NFR-4: Performance: `--check-inputs` on a warm cache completes without tool invocation (hash walk only); full verify bounded by single cache walk.

### Additional Requirements

AR-1 (AD-21): Invalidation is hash-compare only — recompute spine input hashes (csg templates, weg catalog, icon templates/mappings) with Phase 2 canonicalization, compare against `meta.json`; no new hash formulas, no cache layout change.
AR-2 (AD-21): Cascade rule pinned: wallpaper→palette+effects, palette→icons; regenerate the minimal stale set plus cascade.
AR-3 (AD-22): `DoctorUseCase` checks `current.json` vs `current/` targets vs `cache/<layer>/<hash>/` existence+health; repair quarantines by rename-aside (never `rm -rf`), repopulates via Phase 2 pipeline, repoints stray symlinks to last-good state, saves `current.json`, appends `history.jsonl` with `trigger: doctor`; idempotent and re-runnable.
AR-4 (AD-23): Torn history tail policy — readers skip a non-JSON trailing line with a warning and report clean; only `doctor --repair` (and the sole writer `append_history`, which self-heals before appending) may truncate/quarantine it; resolves rt-3-1 at the reader contract, with a writer self-heal added in Story 2.3 (amended 2026-09-10; a complete-but-unterminated JSON record is terminated, not truncated).
AR-5 (AD-24): Eviction keeps active + last-N per layer (default 5) + seed-pinned; prune is explicit, dry-run default-safe, every removal logged.
AR-6 (AD-25): New units land in existing layers — `IInvalidationQuery` in `ports/`; `DoctorUseCase`/`PruneUseCase` in `application/`; `doctor` + `cache prune [--verify]` in `cli/` composition root; all I/O in `adapters/`; `tests/architecture/test_layering.py` unchanged and green.
AR-7 (Inherited): Parent AD-1..AD-20 binding read-only (inward deps, layered content-addressed cache, JSON store FS authority, append-only history, runtime-owned `state_root`, symlink-only swap symlinks-leading, per-call env-overrides, SHA-256 versioned, staging-dir population, derivation graph, seed+R2 exception, sync imperative, nested-hexagon layout, domain purity, cross-package boundary, wallpaper hardlink, `current/` consumer wiring, backend abstraction, Typer CLI via `cli_output`, separate binary).
AR-8 (Non-goals, binding): No declarative diff engine (P4), no daemon/watchers (P5), no parallel execution/plugins (P6), no SQLite/multi-backend store, no hash-formula / cache-layout / derivation-semantics changes.
AR-9 (Deferred, binding): Auto-check on `wallpaper set` stays explicit in Phase 3 (OQ-2 decision: explicit now, auto in Phase 4 reconciler); Keep-N tuning and seed-pin UX beyond defaults deferred; writer-side history atomicity redesign deferred (multi-`write(2)` interleave accepted).
AR-10 (AD-26, fold-in 2026-09-10): Digest enforcement at populate — every artifact hashed at write time inside `populate_via_staging`; mismatch raises `CorruptCacheError` before the staging rename; write-once preserved (no in-place re-hash; correction via `DoctorUseCase` only); enforcement helper lives in `adapters/`, surfaced as data by `application/`.
AR-11 (AD-27, fold-in 2026-09-10): Legacy lazy annotation — pre-FR-8 entries without `artifact_hashes` stay usable (healthy-until-proven-corrupt); first `cache list --verify` annotates them in place; never hard-failed, no migration pass.

### UX Design Requirements

None — no UX design contract exists for Phase 3 (headless CLI state-awareness work; no DESIGN.md/EXPERIENCE.md inputs).

### FR Coverage Map

FR-1: Epic 1 - Input-hash recompute + read-only stale-layer report (`--check-inputs`)
FR-2: Epic 1 - Minimal selective regeneration + cascade via Phase 2 pipeline
FR-3: Epic 2 - Doctor three-way drift check with exit codes + machine-readable report
FR-4: Epic 2 - Doctor repair (quarantine, repopulate, repoint, `trigger: doctor` history line)
FR-5: Epic 3 - `cache list --verify` per-entry health, default list output unchanged
FR-6: Epic 3 - `cache prune` keep-policy eviction with dry-run safety + removal logging
FR-7: Epic 2 - Torn-history-tail tolerance (skip + warn; truncate only under `--repair`)
FR-8: Epic 1 - Digest enforcement at populate time (Story 1.5; AD-26)
FR-9: Epic 3 - Legacy lazy annotation on first `--verify` (Story 3.1; AD-27)

## Epic List

### Epic 1: Invalidation-Aware Regeneration

Operator edits a spine input (csg template, weg catalog, icon template/mapping) and a read-only check surfaces exactly the stale layers (+ cascade); regeneration rebuilds only those through the Phase 2 pipeline and the desktop reconverges. Populated entries carry enforced artifact digests so corruption is caught at write time, not discovered later.

**FRs covered:** FR-1, FR-2, FR-8

### Epic 2: Doctor Drift Detection + Repair

Operator runs one command to see `current.json ↔ current/ symlinks ↔ cache/` divergence (ok/missing/diverged/dangling) and repair it idempotently — bad entries quarantined (never deleted), stray symlinks repointed to last-good state, one `trigger: doctor` history line appended, torn history tail tolerated per AD-23.

**FRs covered:** FR-3, FR-4, FR-7

### Epic 3: Cache Verify + Prune

Operator verifies per-entry cache health without changing default list output, and explicitly prunes only unreferenced, non-active, non-pinned entries (keep active + last-N default 5 + seed-pinned), with dry-run default-safe and every removal logged.

**FRs covered:** FR-5, FR-6

<!-- End Epic List -->

---

## Epic 1: Invalidation-Aware Regeneration

Operator edits a spine input (csg template, weg catalog, icon template/mapping) and a read-only check surfaces exactly the stale layers (+ cascade); regeneration rebuilds only those through the Phase 2 pipeline and the desktop reconverges.
**FRs covered:** FR-1, FR-2
**CAPs covered:** CAP-1

### Story 1.1: IInvalidationQuery port + pure stale-set computation

As a developer,
I want a new `IInvalidationQuery` port with a pure stale-set + cascade computation over the domain derivation graph,
So that invalidation logic is testable without I/O and later adapters/CLI share one contract.

**Acceptance Criteria:**

**Given** the `ports/` layer with existing ABC ports
**When** `IInvalidationQuery` is added (abstract methods: recompute-input-hashes, compare-against-meta, stale-set-with-cascade)
**Then** it is an ABC with no concrete I/O, no `os`/`subprocess`/`shutil` FS calls
**And** the cascade rule is wallpaper→palette+effects, palette→icons (AR-2/AD-21) in a domain-pure helper
**And** `tests/architecture/test_layering.py` passes unchanged
**And** no hash formula or cache-layout constant is altered (AR-1)

### Story 1.2: Spine input-hash walk adapter vs meta.json

As a developer,
I want an adapter that recomputes spine input hashes (csg templates, weg catalog, icon templates+mappings) with Phase 2 canonicalization and compares them against `meta.json`,
So that stale layers are detected by hash-compare only.

**Acceptance Criteria:**

**Given** a warm cache with per-layer `meta.json` entries
**When** the hash-walk adapter recomputes input hashes and compares them to recorded values
**Then** matching layers report fresh and differing layers report stale with the differing input identified (templates vs catalog vs mappings)
**And** canonicalization matches `shared-data-contract.md` exactly (no new formulas, AR-1)
**And** the stale-set computation uses recorded *input* hashes only — artifact-hash mismatch is NOT staleness; it is the corrupt-by-digest domain of Story 1.5 / doctor `--verify` (boundary pinned 2026-09-10)
**And** all filesystem I/O lives in `adapters/` only (AR-6)

### Story 1.3: Read-only `--check-inputs` stale report

As a user,
I want `reconcile --check-inputs` (or `doctor --check`) to report stale layers without mutating anything,
So that editing a csg template surfaces exactly palette (+icons cascade) as stale before I commit to regeneration.

**Acceptance Criteria:**

**Given** a warm cache where a csg template was edited
**When** `dotfiles-runtime reconcile --check-inputs` runs
**Then** it reports palette stale plus icons via cascade, effects and wallpaper fresh
**And** it performs zero mutations (no cache writes, no symlink repoints, no JSON/history writes)
**And** on a warm cache it completes with zero csg/weg/itr invocations (hash walk only, NFR-4)

### Story 1.4: Minimal selective regeneration + cascade + reconverge

As a user,
I want stale layers (plus cascade) regenerated through the Phase 2 pipeline and the desktop reconverged,
So that `doctor --repair` after a template edit rebuilds only what changed.

**Acceptance Criteria:**

**Given** the stale set from Story 1.3 (e.g. palette + icons cascade)
**When** regeneration runs
**Then** only the stale layers plus cascade are regenerated via the Phase 2 pipeline (staging-dir, write-once, per-call env-overrides; AR-3)
**And** fresh layers are untouched (no tool invocation for them)
**And** the run finishes with repointed `current/`, saved `current.json`, one history line, and consumer reload (PRD success signal)
**And** repair/regeneration is idempotent and re-runnable (NFR-3)

### Story 1.5: Digest enforcement at populate time (fold-in 2026-09-10)

As a developer,
I want every artifact hashed as it is written via `populate_via_staging`,
So that generator-level corruption raises before the entry becomes visible and later verify/repair have real digests to check.

Depends on Story 1.2 (same recorded `meta.json` input-hash fields); must land before Story 2.2 so doctor repair has corrupt-by-digest entries to classify.

**Acceptance Criteria:**

**Given** a `populate_fn` staging dir with artifacts + `meta.json`
**When** `populate_via_staging` finalizes the entry
**Then** every artifact listed in `artifact_hashes` is re-hashed at write time and a mismatch raises `CorruptCacheError` BEFORE the staging rename — the corrupt entry never becomes visible (FR-8/AR-10/AD-26)
**And** populated entries are never re-hashed in place (write-once preserved); correction flows only through `DoctorUseCase` repair (AD-22)
**And** the enforcement helper lives in `adapters/` (next to `cache.py`/`hashing.py`); `application/` surfaces the error as data, never an uncaught crash (zero-crash invariant)
**And** no hash formula or cache-layout constant is altered (AD-21 holds)
**And** `tests/architecture/test_layering.py` passes unchanged (AR-6)

---

## Epic 2: Doctor Drift Detection + Repair

Operator runs one command to see `current.json ↔ current/ symlinks ↔ cache/` divergence (ok/missing/diverged/dangling) and repair it idempotently — bad entries quarantined (never deleted), stray symlinks repointed to last-good state, one `trigger: doctor` history line appended, torn history tail tolerated per AD-23.
**FRs covered:** FR-3, FR-4, FR-7
**CAPs covered:** CAP-3

### Story 2.1: Doctor three-way check with machine-readable report

As a user,
I want `dotfiles-runtime doctor` to check `current.json` vs `current/` symlink targets vs `cache/<layer>/<hash>/` existence+health,
So that drift shows as ok/missing/diverged/dangling with a proper exit code.

**Acceptance Criteria:**

**Given** a consistent machine (warm cache, aligned symlinks, valid `current.json`)
**When** `dotfiles-runtime doctor` runs
**Then** it exits 0 and reports clean
**And** given a diverged machine (stray symlink, missing entry, corrupt `meta.json`, artifact-hash mismatch) it exits non-zero with a machine-readable report classifying each item ok/missing/diverged/dangling (FR-3)
**And** the check path performs zero mutations

### Story 2.2: Doctor repair — quarantine, repopulate, repoint, record

As a user,
I want `doctor --repair` to heal drift without ever deleting user state,
So that a corrupted `meta.json` heals without manual deletion and the desktop reconverges.

**Acceptance Criteria:**

**Given** a drifted machine (corrupt/missing `meta.json` or artifact-hash mismatch, stray symlink)
**When** `dotfiles-runtime doctor --repair` runs
**Then** bad entries are quarantined by rename-aside (never `rm -rf`), repopulated via the Phase 2 pipeline, stray symlinks repointed to last-good `current.json` state
**And** corrupt-by-digest entries (artifact-hash mismatch per Story 1.5, FR-8) are quarantined + repopulated identically to corrupt-`meta.json` entries — one repair path for all corruption classes (fold-in 2026-09-10)
**And** `current.json` is saved (tmp+rename) and `history.jsonl` gains exactly one line with `trigger: doctor` (O_APPEND)
**And** re-running `doctor --repair` is a no-op success (idempotent, NFR-3)
**And** repair never writes under the install spine except the AD-11 R2 symlink (NFR-2)

### Story 2.3: Torn-history-tail tolerance (AD-23)

As a user,
I want history readers to survive a torn trailing line and only `doctor --repair` to heal it,
So that one short write never bricks every history consumer (rt-3-1).

**Acceptance Criteria:**

**Given** a `history.jsonl` with a non-JSON trailing line
**When** any history reader (`inspect history`, `doctor` check, reconcile) runs
**Then** it skips the torn line with a warning, reports clean otherwise, and never crashes (FR-7/AR-4)
**And** only `doctor --repair` truncates/quarantines the torn tail (plain check never mutates it)
**And** the writer contract is unchanged (multi-`write(2)` interleave stays accepted per arch Deferred)

---

## Epic 3: Cache Verify + Prune

Operator verifies per-entry cache health without changing default list output, and explicitly prunes only unreferenced, non-active, non-pinned entries (keep active + last-N default 5 + seed-pinned), with dry-run default-safe and every removal logged. Legacy entries are annotated, never failed.
**FRs covered:** FR-5, FR-6, FR-9
**CAPs covered:** CAP-2, CAP-4

### Story 3.1: `cache list --verify` per-entry health

As a user,
I want `inspect cache list --verify` to add per-entry health (artifact-hash recheck, `meta.json` validity),
So that corrupt entries are visible without changing the default list.

**Acceptance Criteria:**

**Given** a cache with one corrupt entry (artifact-hash mismatch or bad `meta.json`)
**When** `dotfiles-runtime inspect cache list` runs without flags
**Then** output is byte-identical to the Phase 2 default list (FR-5)
**And** when run with `--verify` each entry carries a health verdict (ok/corrupt/missing) from a single bounded cache walk (NFR-4)
**And** legacy entries without `artifact_hashes` are lazily annotated in place on first `--verify` (digests recorded, FR-9/AR-11/AD-27) — never hard-failed, no migration pass
**And** verify performs zero mutations beyond the annotation write (fold-in 2026-09-10)

### Story 3.2: `cache prune` keep-policy eviction core

As a developer,
I want a `PruneUseCase` in `application/` enforcing keep active + last-N (default 5) + seed-pinned,
So that eviction is bounded and live/seed state can never be deleted.

**Acceptance Criteria:**

**Given** a cache with active entries (referenced by `current.json`), recent entries, old unreferenced entries, and seed-pinned entries
**When** the prune use case computes the removal set with defaults (`--keep 5`, seed pinned)
**Then** active, last-5-per-layer, and seed-pinned entries are all excluded; only unreferenced, non-active, non-pinned entries are selected (AR-5/AD-24)
**And** the use case lives in `application/`, I/O stays in `adapters/`, `test_layering.py` passes unchanged (AR-6)

### Story 3.3: Prune CLI — explicit, dry-run-safe, logged, idempotent

As a user,
I want `cache prune [--dry-run --keep N --prune-pinned=false]` to be explicit and safe by default,
So that `cache prune --dry-run` reports reclaimable entries and real prunes remove only what was reported.

**Acceptance Criteria:**

**Given** the removal set from Story 3.2
**When** `dotfiles-runtime cache prune --dry-run` runs
**Then** it reports reclaimable entries and removes nothing (default-safe, FR-6)
**And** when run without `--dry-run` every removal is logged, only the reported set is removed, and re-running is a no-op success (idempotent)
**And** `--keep N` overrides the default 5 and `--prune-pinned=false` default keeps seed-pinned entries protected
