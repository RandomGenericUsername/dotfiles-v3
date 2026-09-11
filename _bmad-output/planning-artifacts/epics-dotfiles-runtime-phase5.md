# Phase 5 — Reactive Runtime: Planning Draft (Gate 1)

Status: DRAFT — awaiting Gate 1 approval. No stories are ready-for-dev; no
code may start until the AD decisions below are ruled and this backlog is
reconciled.

Baseline: Phase 4 closed at `07b6753` (Reconciliation Engine, 7/7 stories,
AD-30/31/32 adopted).

Source: `docs/99-dotfiles-hexagonal-architecture.md` §"Phase 5 — Reactive
Runtime" (filesystem watchers, daemon, reactive updates, runtime
reconciliation). PRDs through Phase 4 explicitly exclude daemon/watchers.

## Goal

Introduce continuous reconciliation: instead of only converging when the user
runs a command, a long-lived runtime keeps the desktop converged — watching the
declared intent (`desired.json`) and the spine derivation inputs, and
reconciling on change.

## Why this is a planning gate, not a story draft

§22 ("Initial Runtime Execution Model") deferred daemons, async orchestration,
event buses, and distributed execution. Phase 5 reintroduces exactly one of
those (a daemon) and must do so without violating the inherited invariants
(AD-1..AD-32). Locked decisions already in place that Phase 5 must honor:

- AD-12 synchronous imperative execution — the existing commands stay synchronous; the daemon is additive, never required.
- AD-21 / AD-32 — invalidation and reconciliation remain independent hash-compares; the daemon must not trust cached computed state.
- AD-30 — automatic prune floor; a daemon is the highest-risk path for surprise deletion, so its delete authority must be the same floor, previewed/logged.
- AD-31 — one history lock; the daemon joins the existing writer serialization.
- AD-11 seed mutex and the `reconcile`/`wallpaper set` mutex — the daemon must serialize against CLI invocations, not race them.

## Proposed Architecture Decisions (Gate 1 rulings required)

Each is a proposal; the owner rules before stories are drafted.

- **AD-33 — Daemon lifecycle & supervision.** Proposed: a user-scoped, foreground-capable process supervised by a user systemd unit (or run under the existing session), with a `runtime daemon start/stop/status` CLI surface. No root, no always-on root daemon. Consequence: the runtime grammar gains a `daemon` command group; process state lives under `state_root` (pidfile + lock, kernel-owned release).
- **AD-34 — Watch strategy.** Proposed: a single coarse watcher over a bounded set of roots (state_root `desired.json`, spine input dirs/files) using inotify (`inotifywait`/`watchdog`), coalesced with a debounce window (AD-xx value to be pinned). No per-file watcher fan-out; no recursive watch of the entire config tree. Polling fallback must be defined for environments without inotify.
- **AD-35 — Reactive execution policy.** Proposed: a change event triggers exactly the same use cases the CLI composes (`check-inputs` → `reconcile`, or `reconcile` converge when desired.json changed), never a new execution engine. Events coalesce; overlapping reconciles are dropped, not queued unboundedly. Failures are logged and retried with backoff, never crash-loop.
- **AD-36 — Loop safety / conflict.** Proposed: the daemon never holds locks across sleeps; it acquires the existing mutexes per action. A dirty-marker (or hash of last-converged actual state) prevents self-triggering loops (reconcile writes `current.json`/history, which the watcher must not treat as an intent change). This is the single biggest correctness risk of the phase and needs an explicit decision.

## Candidate Epics (shape only — refine after AD rulings)

| Epic | Theme | Likely stories |
| --- | --- | --- |
| 5-1 | Daemon foundation | process lifecycle + lock/pidfile, `daemon start/stop/status`, systemd user unit, structured logging |
| 5-2 | Watch + coalesce | bounded root watcher, debounce, inotify-vs-poll fallback, self-trigger suppression |
| 5-3 | Reactive reconcile | event → CLI-equivalent use-case composition, retry/backoff, conflict with CLI via mutex, history trigger `reactive` |
| 5-4 | Observability & safety | `daemon status`/`inspect` surface, delete-audit under AD-30, dry-run/observe-only mode, kill-switch |

## Dependencies / prerequisites from Phase 4 (satisfied or flagged)

- Desired/actual/diff/planner exist (p4-2-1..p4-3-2) — the reactive path has a real converge action to invoke. ✅
- History lock (AD-31) and invalidation independence (AD-32) — the daemon introduces the concurrency these were built for. ✅
- **Missing:** a persisted "last converged" marker to suppress self-trigger loops; a decision on daemon process supervision; a `history` trigger value for reactive events (the pinned enum is `seed|set|reconcile|force|regenerate|doctor` — adding `reactive` touches the shared data contract and the inspect reader's validator).

## Explicit non-goals (this phase)

- Parallel execution, plugin interfaces, incremental dependency graph, distributed cache (Phase 6).
- Async orchestration/event bus as a general framework — only the minimal change→reconcile loop.
- Replacing synchronous CLI behavior; commands remain the source of truth and must work with the daemon absent.
- Multi-user / system-wide daemon.

## Risks

- **Surprise deletion** by an automatic daemon (highest). Mitigation: AD-30 floor is the only delete authority; default the daemon to observe/reconcile-only unless explicitly enabled.
- **Self-triggering loop** (watcher sees its own writes). Mitigation: AD-36 dirty-marker + ignore-list.
- **Lock contention / thundering herd** between daemon and interactive CLI. Mitigation: existing mutexes + coalescing + drop-not-queue.
- **Portability** of inotify. Mitigation: polling fallback.
- **History contract drift** if a new trigger value is added carelessly. Mitigation: shared-data-contract update is part of the AD ruling, not an implementation detail.

## Gate 1 asks

1. Approve Phase 5 as the next phase, or defer in favor of pending `gt-*` GTK theming remediation.
2. Rule AD-33..AD-36 (or send back with changes).
3. Confirm whether a Phase 5 PRD delta is required before epics, or whether this spine + the existing PRDs suffice (Phases 3/4 used a PRD delta — precedent suggests one is).
