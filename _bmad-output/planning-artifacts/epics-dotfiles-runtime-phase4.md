# dotfiles-repo-v3 - Epic Breakdown (Phase 4: Reconciliation Engine)

## Overview

Phase 4 moves the runtime from imperative execution (`wallpaper set` → derive →
save → reconcile) to declarative convergence (`desired state` → `actual state` →
`diff` → `plan` → `execute`). This file is the reconciled story backlog. It
seeds — but does not replace — the full Phase 4 PRD/epics workflow
(`bmad-prd` → `bmad-architecture` → `bmad-create-epics-and-stories`).

Sources: `docs/99-dotfiles-hexagonal-architecture.md:1285` (Phase 4 goal),
`_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-09-11/`
(decision handoff), `.../architecture-dotfiles-repo-v3-2026-09-11/`
(AD-30/AD-31 draft), Phase 3 epics (deferred items: auto-check, diff engine).

Status convention mirrors `sprint-status.yaml`: `backlog` / `ready-for-dev` /
`in-progress` / `review` / `done`.

## Epic List

### Epic 1: Reconciliation Preview

Fix the CLI contract the diff engine will later fill. No desired-state file,
no diff engine, no execution changes.

| Story | Title | Status |
|---|---|---|
| p4-1-1 | `reconcile --plan` read-only preview | done |

### Epic 2: Declarative State

Define and load the two state documents. No behavior change to `reconcile`
yet — readers only.

| Story | Title | Status |
|---|---|---|
| p4-2-1 | Desired-state file + schema + loader | backlog |
| p4-2-2 | Actual-state projection | backlog |

### Epic 3: Diff + Plan Execution

Compute the gap and converge through it. This is where imperative `reconcile`
gains its declarative core.

| Story | Title | Status |
|---|---|---|
| p4-3-1 | Diff engine (desired vs actual → change set) | backlog |
| p4-3-2 | Planner wiring (execute plan incl. AD-30 delete steps) | backlog |

## Cross-Epic Contracts (locked)

- **AD-30** (`architecture-2026-09-11`): hybrid prune — `code default keep=5`
  < `desired-state` declaration < explicit CLI flags. Auto deletes only outside
  the floor `active + last-N + seed-pinned + undated`. Manual `--keep 0` +
  `--prune-pinned` still excludes `active + undated` (no whole-cache delete).
  B2: `reconcile --plan` previews, `reconcile` executes + logs, no prompt.
- **AD-31** (`architecture-2026-09-11`): all `history.jsonl` writers serialize
  through one OS-level file lock (local POSIX scope); failures are typed errors.
- **Phase 3 deferred, now in scope:** auto-check on `wallpaper set`
  (fold into the planner, not a flag), declarative diff engine.
- **Still deferred:** daemon/watchers (Phase 5), parallel execution/plugins,
  incremental dependency graph, distributed cache, favorites-as-data (joins the
  floor as desired-state data, no rule change).

## Epic 1 Detail (closed)

- p4-1-1 (`p4-1-1-reconcile-plan-preview.md`, done): `--plan`/`--keep`/
  `--prune-pinned` on `reconcile`, mutual exclusion (exit 2), `_run_reconcile_plan`
  composing `CheckInputsUseCase` + `PruneUseCase`, JSON `{stale, fresh,
  removals, kept, total_removable, keep, prune_pinned}`, exit 0, no mutations.
  No new `application/` units — the diff engine replaces these internals.
