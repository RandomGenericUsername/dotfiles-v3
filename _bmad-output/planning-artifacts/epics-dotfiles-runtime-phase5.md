# Phase 5 — Reactive Runtime: Epic Backlog

Status: reconciled against the Phase 5 architecture spine (validated; spine `final`).

Baseline: Phase 4 closed at `07b6753`; docs updated at the validate-gate Update.
Spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md`
(AD‑33..AD‑44 + AD‑12 delta). Contract: `contracts/event-contract.md|json`.

## Goal

Continuous reconciliation and shell reactivity: a supervised session-D-Bus daemon
triggers the **existing synchronous use cases** on declared-input change, and the
bar/jobs react to state through **one shared session-D-Bus event contract** — with
no polling anywhere.

## Prerequisite remediation (Phase 4 defects — do first)

| Story | Fix | Why first |
| --- | --- | --- |
| R‑1 prune audit line | A real prune appends one `history.jsonl` line `trigger="prune"` with counts; dry-run appends nothing. (AD‑30 was never implemented.) | The daemon auto-prunes; the audit trail must exist before automation |
| R‑2 trigger enum single‑source | One machine-checkable definition; values `seed|set|reconcile|regenerate|doctor|prune|reactive`; validator + `shared-data-contract` derive from it; drift test; drop dead `force`. (AD‑42/AD‑44) | Phase 5 adds `reactive`/`prune`; never extend a brittle doc |
| R‑3 derivation inputs spine‑only | `derive.find_*` resolves the spine only in production; repo fallback is an explicit opt‑in dev override; missing input fails loud; `verify` asserts input **content**; `doctor` provenance tripwire. (AD‑43) | Phase 5 watches spine roots; the spine must be complete and repo‑free |
| R‑4 machine‑enforced shared contracts | `current.json`/`meta.json`/history get a machine-checkable definition; prose descriptive; drift test. (AD‑44, beyond R‑2) | Removes the proven prose-drift class |
| R‑5 doctor store↔history divergence | `doctor` detects and repairs `current.json`↔history divergence (the save↔append crash window). (AD‑41 claims it; unimplemented today) | The daemon's recovery path needs a detector, not a claim |

## Epics

| Epic | Theme | Likely stories |
| --- | --- | --- |
| 5‑1 | Daemon foundation, observability & safety | systemd `--user` unit (`Type=dbus`+`BusName=org.dotfiles.Events`, `Restart=always`, `Requires=/After=dbus.socket`, `WantedBy=/After=graphical-session.target`) + provisioning enable via `graphical-session.target.wants/`; `daemon run` loop (`RequestName(DO_NOT_QUEUE)`, fail‑fast, never exit 0 before owning, release on SIGTERM); hub broker+registry (methods/signals/epoch/seq); converge‑on‑start with persisted backstop; observe‑only default; status + kill switch; trigger‑logged actions; delete audit |
| 5‑2 | Event contract & bus | runtime `IEventPublisher`/`IEventSubscriber` port + D‑Bus adapter; bar consumer binding; per‑language drift tests (names + schemas); structural validation (size/depth/rate caps); subscribe‑before‑read hydration |
| 5‑3 | Watch & reactive reconcile | spine‑only enumerated watched roots; inotify + coalesce + `IN_Q_OVERFLOW` re‑scan + bounded recursion + atomic‑replace re‑watch; relocate `desired.json` to `$XDG_CONFIG_HOME/dotfiles/`; persisted loop‑safety backstop; `reactive` history trigger; daemon joins `.seed.lock`/`.history.lock` per action |
| 5‑4 | Shell reactivity | capture controller becomes a resident lifetime job reporting via hub methods; bar recording indicator driven by domain events (poll removed); speed‑test job + animated wifi icon; ICME emits `icme.saved` on save |

## Dependencies / prerequisites

- Phase 4 provides desired/actual/diff/planner to trigger. ✅
- AD‑31 history lock and AD‑32 invalidation independence exist. ✅
- New capabilities: provision a **user systemd unit**; a Python D‑Bus client in the runtime; inotify watching; moving `desired.json` out of `state_root`; single‑sourced shared contracts.

## Non-goals

- Rewriting the runtime pipeline or CSG/WEG/ITR as daemons/events (AD‑35/AD‑37).
- Polling of any kind for state.
- Parallel execution, plugins, incremental graph, distributed cache (Phase 6).

## Risks

- **Surprise deletion** → AD‑30 floor + observe‑only first + trigger logs.
- **Feedback loop** → AD‑36 disjoint roots + persisted hash backstop.
- **Forged events** → accepted same‑UID trust; structural validation + bounded floor (AD‑38).
- **Env absence** (no systemd/bus/inotify) → absence/recovery conventions; reduced functionality, commands unaffected.
- **Contract drift** → machine‑enforced contracts + drift tests (AD‑44).
