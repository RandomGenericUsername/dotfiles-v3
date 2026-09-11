---
name: dotfiles-repo-v3 Phase 4 reconciliation-engine decision handoff
type: architecture-spine
purpose: build-substrate
altitude: feature
paradigm: hexagonal (ports & adapters)
scope: Phase 4 AD-30 auto/manual prune policy and AD-31 history writer locking
status: draft
created: 2026-09-11
updated: 2026-09-11
binds: [Phase 4 AD-30, Phase 4 AD-31]
sources: [docs/99-dotfiles-hexagonal-architecture.md, _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-09-11/addendum.md]
companions: []
---

# Architecture Spine — Phase 4 Reconciliation-Engine Decision Handoff

## Design Paradigm

Hexagonal, synchronous, filesystem-authoritative — inherited unchanged. These
two decisions add controlled deletion and serialized history writes without
introducing a daemon, async orchestration, event bus, distributed execution,
or a new store.

## Inherited Invariants

| Inherited | From parent | Binds here |
| --- | --- | --- |
| AD-24 eviction policy, as extended by AD-30 for undated entries | `architecture-dotfiles-repo-v3-2026-09-07` | Auto/manual deletion, last-N, seed-pinned entries, dry-run/logged behavior |
| AD-4 append-only history | `architecture-dotfiles-repo-v3-2026-08-18` | Writer locking must preserve append-only must-not-lose history |
| AD-12 synchronous imperative execution | `architecture-dotfiles-repo-v3-2026-08-18` | Preview/execute and repair flows remain synchronous |
| AD-1/AD-13/AD-14/AD-15/AD-20 hexagon, layout, purity, boundaries, binary | `architecture-dotfiles-repo-v3-2026-08-18` | Placement of prune/history behavior in domain, ports, adapters, application, and CLI |

## Invariants & Rules

### AD-30 — Hybrid automatic and manual prune policy

- **Binds:** Phase 4 planner delete steps and the explicit `prune` command
- **Prevents:** surprise deletion by automation while preserving deliberate manual cleanup
- **Rule:** prune policy resolves as code default `keep=5` < desired-state declaration < explicit CLI flags. Automatic prune may delete only candidates outside the protected floor: active entries, last-N per layer, seed-pinned entries, and undated entries. Manual `prune` may override policy aggressively via `--keep 0` and `--prune-pinned`, but active + undated entries survive every flag combination (whole-cache deletion is not offered). Every real prune execution appends exactly one `history.jsonl` line with `trigger="prune"` and counts; dry-run appends nothing. Automatic execution uses `reconcile --plan` preview followed by logged `reconcile` execution; no interactive prompt. [ADOPTED]

### AD-31 — Serialized history.jsonl writers

- **Binds:** every `history.jsonl` writer
- **Prevents:** torn-line interleaving from concurrent writers
- **Rule:** all history writers serialize through one OS-level file lock, scoped to local POSIX; lock-acquire/hold/release failures surface as typed errors. Append-only behavior is unchanged. [ADOPTED]

## Dependency Direction

```mermaid
flowchart LR
    CLI[cli: prune flags and reconcile preview/execution] --> APP[application: prune planning and history use]
    APP --> PORTS[ports: planning/history abstractions]
    PORTS --> DOMAIN[domain: protected-set and append-only rules]
    ADAPT[adapters: deletion, locking, and filesystem writes] --> PORTS
```

## Deferred

- Remaining Phase 4 scope: `desired state` shape, `actual state` projection, diff semantics, execution-plan ordering, and failure policy.
- Daemon/watchers (Phase 5), parallel execution/plugins, incremental dependency graph, and distributed cache.
- Favorites-style pinned data may later join the protected floor as desired-state data; no rule change is approved here.
