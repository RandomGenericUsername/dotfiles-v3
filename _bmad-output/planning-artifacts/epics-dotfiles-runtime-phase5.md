# Phase 5 — Reactive Runtime: Epic Backlog

Status: reconciled against the Phase 5 architecture spine (Gate: spine `final`).

Baseline: Phase 4 closed at `07b6753`. Spine:
`_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md`
(AD‑33..AD‑42 + AD‑12 delta). Contract companion: `contracts/event-contract.md|json`.

## Goal

Introduce continuous reconciliation and shell reactivity: a supervised daemon
triggers the **existing synchronous use cases** on declared-input change, and the
bar/jobs react to state through **one shared session-D-Bus event contract** — with
no polling anywhere.

## Locked decisions (from the spine)

- **AD‑33** daemon = systemd `--user` service; provisioning owns config; runtime provides `daemon run`.
- **AD‑34** one shared, versioned event contract (`org.dotfiles.Events1`); runtime port + D‑Bus adapter; bar is a thin consumer.
- **AD‑35** orchestrate the core, choreograph the edges — core stays synchronous (AD‑12 narrowed to the core, not the edges).
- **AD‑36** loop safety: watched roots disjoint from runtime writes + in‑memory last‑converged hash backstop.
- **AD‑37** tool classification: batch commands stay CLIs; lifetime jobs own their child; interactive apps emit domain events on the meaningful moment; existing D‑Bus services are bound, never wrapped.
- **AD‑38** one hub owner (`org.dotfiles.Events`) + caller→topic authorization.
- **AD‑39/AD‑40** enumerated watched roots; coalescing + overflow re‑scan; no polling.
- **AD‑41** observability & safety: observe‑only first, status, kill switch, trigger‑logged actions, delete audit.
- **AD‑42** new `reactive` history trigger ships with the shared-data-contract + validator update.

## Epics

| Epic | Theme | Likely stories |
| --- | --- | --- |
| 5‑1 | Daemon foundation, observability & safety | systemd `--user` unit provisioning; `dotfiles-runtime daemon run` loop; hub process owning `org.dotfiles.Events`; `systemctl`/inspect status surface; observe‑only default; kill switch; trigger‑logged actions + delete audit |
| 5‑2 | Event contract & bus | author `contracts/event-contract.*`; runtime `IEventPublisher`/`IEventSubscriber` port + D‑Bus adapter; bar consumer binding; per‑language drift tests (names + schemas) |
| 5‑3 | Watch & reactive reconcile | enumerated watched roots (AD‑39); inotify watch + coalesce + `IN_Q_OVERFLOW` re‑scan (AD‑40); loop‑safety backstop (AD‑36); relocate `desired.json` to `$XDG_CONFIG_HOME/dotfiles/`; reactive reconcile runs the existing use cases; `reactive` history trigger (AD‑42) |
| 5‑4 | Shell reactivity | capture controller becomes a resident lifetime job (owns recorder) publishing `capture.state`; bar recording indicator driven by domain events (poll removed); speed‑test job + animated wifi icon; ICME emits `icme.saved` on save → daemon triggers regeneration |

## Dependencies / prerequisites

- Phase 4 provides desired/actual/diff/planner to trigger. ✅
- AD‑31 history lock and AD‑32 invalidation independence already exist. ✅
- New capabilities required: provisioning a **user systemd unit** (no role writes `~/.config/systemd/user/` today); a Python D‑Bus client in the runtime; inotify watching; moving `desired.json` out of `state_root`.

## Non-goals

- Rewriting the runtime pipeline or CSG/WEG/ITR as daemons/events (AD‑35/AD‑37).
- Polling of any kind for state.
- Parallel execution, plugins, incremental graph, distributed cache (Phase 6).

## Risks

- **Surprise deletion** by automation → AD‑30 floor + observe‑only first + trigger logs.
- **Feedback loop** → AD‑36 disjoint roots + hash backstop.
- **Bus-name contention / forged events** → AD‑38 single owner + caller→topic authorization.
- **Env absence** (no systemd/bus/inotify) → AD‑19 operational envelope + absence conventions.
