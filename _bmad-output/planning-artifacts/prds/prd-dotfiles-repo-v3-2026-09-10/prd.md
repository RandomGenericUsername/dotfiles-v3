---
title: dotfiles-repo-v3 Phase 3 — State Awareness (reconciled with cache-integrity fold-in)
status: final
created: 2026-09-10
updated: 2026-09-10
parent: ../prd-dotfiles-repo-v3-2026-09-07/prd.md
---

# PRD — Phase 3: State Awareness (v2, 2026-09-10)

## Context

This PRD reconciles the Phase 3 PRD `2026-09-07` (FR-1..FR-7: invalidation-awareness,
self-heal, drift detection, bounded growth) with the operator-approved cache-integrity
fold-in (digest-at-populate enforcement, legacy lazy annotation). The 2026-09-07 PRD
stays read-only; this document is the build PRD. Phase 1 (provisioning) and Phase 2
(runtime + Epic 4 single-source + GTK theming) are done. Audience: solo operator
(juan david) on Arch Linux.

Inherited capabilities CAP-1..CAP-4 and FR-1..FR-7 from the parent PRD are unchanged:

- **CAP-1** invalidation on input change · **CAP-2** cache health · **CAP-3** drift
  detection + repair · **CAP-4** bounded cache.
- **FR-1** `--check-inputs` stale report · **FR-2** minimal regen + cascade ·
  **FR-3** `doctor` three-way check · **FR-4** `doctor --repair` ·
  **FR-5** `cache list --verify` · **FR-6** `cache prune` · **FR-7** torn-tail tolerance.

## New Functional Requirements (fold-in)

- **FR-8: Digest enforcement at populate time.** Every artifact in a cache entry is
  hashed as it is written via `populate_via_staging`; a mismatch between the computed
  digest and the `artifact_hashes` recorded in `meta.json` raises `CorruptCacheError`
  before the staging dir is renamed — generator-level corruption never enters the
  cache. Write-once invariant preserved: populated entries are never re-hashed
  in place; correction happens only through `doctor --repair`.
- **FR-9: Legacy lazy annotation.** Cache entries written before FR-8 (no
  `artifact_hashes` in `meta.json`) remain fully usable. The first
  `cache list --verify` annotates them (records digests) instead of failing them;
  they are treated as healthy-until-proven-corrupt. No cache-format migration.

## Non-Functional Requirements (unchanged + one addition)

- NFR-1..NFR-4 from the parent PRD hold (hexagonal/sync/FS-authoritative,
  spine/state_root separation, atomicity + idempotent repair, hash-walk-only
  performance).
- **NFR-5: Determinism.** Verify/repair verdicts are deterministic: same cache bytes
  ⇒ same verdict, no wall-clock inputs.

## Non-goals (binding, inherited)

No declarative diff engine (Phase 4). No daemon/watchers (Phase 5). No parallel
execution/plugins (Phase 6). No SQLite/multi-backend store. No hash-formula,
cache-layout, or derivation-semantics changes. No cache eviction policy beyond the
AD-24 keep-policy (prune stays explicit).

## Deferred (binding, inherited)

Auto-check on `wallpaper set` stays explicit (OQ-2: auto in Phase 4 reconciler).
Keep-N tuning and seed-pin UX beyond defaults deferred. Writer-side history
atomicity redesign deferred (multi-`write(2)` interleave accepted).

## Success signal

Parent success signal holds, plus: corrupting any artifact inside a cache entry then
running `doctor --repair` quarantines (rename-aside, never `rm -rf`) + repopulates
without manual deletion; injecting corruption in tests is detected 100% of the time;
repeated `repair` on a healthy cache is a byte-level no-op; legacy entries survive
first verify via annotation, never a hard fail.

## Open Questions (carried, unchanged)

- OQ-1: Keep-N default and seed-pin policy (N=5, seed pinned — confirmed AD-24).
- OQ-2: Explicit check in Phase 3, auto in Phase 4 reconciler (decided).
- OQ-3: Torn-tail skip+warn, truncate only under `--repair` (decided AD-23).
