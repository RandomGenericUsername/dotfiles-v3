# P5‑1‑1: Daemon `run` Skeleton + Supervised Unit (Name-First, No Converge)

Status: done

baseline_commit: 6ac38c5

Gate 1: approved (recs as-is: fatal bus-absent, port+adapter, tuple
seed-skip, signal-paused idle, 5/60/3/90 tuning, split confirmed).
Gate 2: applied — Items 1–4 (StartLimit→[Unit] + enablement hardening;
release on all load failures + handlers-before-acquire; role test file +
signal/error-path tests; this landing note). Verified: runtime 1057
passed / 2 skipped; layering green; provisioning role+bootstrap tests
green; runtime-daemon --check dry-run green; ruff/mypy no new issues.

Known steady state until P5‑1‑2: the deferred adapter always fails
`acquire()` → exit 1 → bounded retries (3/60s start limit) → the unit
sits `failed (start-limit-hit)` after each login until the real D‑Bus
client lands. Expected, not a defect.
Accepted at Gate 2: SIGINT handled identically to SIGTERM (Ctrl-C
releases → exit 0); corrupt AND unreadable stores are fatal with release.

Epic: Phase 5 epic 5‑1 — Daemon foundation, observability & safety (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`;
spine `ARCHITECTURE-SPINE.md` status `final`, AD‑33/AD‑35/AD‑36/AD‑38/AD‑41).

## Story

As the operator,
I want `dotfiles-runtime daemon run` supervised as a `systemd --user` service
that acquires `org.dotfiles.Events` name-first and then idles,
so the daemon lifecycle (supervision, naming, startup routing) lands and is
testable before any hub, watch, or converge behavior is added.

## Context (why this slice first)

Epic 5‑1 as written is too big for one commit: unit + provisioning enablement
+ `daemon run` loop (name acquire/release, fail-fast, fatal-vs-recoverable) +
hub broker/registry (methods/signals/epoch/seq/leases) + converge-on-start
with persisted backstop + observe-only/status/kill-switch/trigger-logged
actions + delete audit. That spans AD‑33/34/35/36/38/41 and cannot stay
surgically landable (one commit, pytest/ruff/mypy/layering green).

Prior remediation is done at this baseline: R‑1 (prune audit line), R‑2
(single-sourced trigger enum), R‑3 (spine-only derivation inputs), R‑4
(schema-driven contracts), R‑5 (`doctor` store↔history divergence
detection+repair). The daemon's recovery path therefore has its detector; this
story starts the daemon itself from the smallest safe slice.

Current CLI shape (`src/runtime/src/runtime/cli/main.py`): the Typer `app`
composes `wallpaper` / `inspect` (+`cache`) sub-apps and top-level `doctor` /
`reconcile` / `version` commands. There is **NO `daemon` command yet** — this
story adds a `daemon` Typer sub-app with exactly one foreground command, `run`
(the systemd `ExecStart`; there are NO `start`/`stop` subcommands — `systemctl
--user` is the control surface per the memlog constraint). The `main_callback`
auto-seed gate currently skips seeding for `("reconcile", "inspect",
"doctor")`; `daemon` must join that skip (the daemon never seeds, AD‑11/C5).

What 5‑1‑1 deliberately does NOT include (later stories own it): hub
methods/signals/epoch/seq/leases (`Emit`/`BeginJob`/…), file watching
(inotify), converge-on-start and the persisted last-converged backstop, any
automatic mutation (`reconcile`/`regenerate`/`prune` invocation), `reactive`
history lines, status inspect surface beyond `systemctl`, kill-switch beyond
`systemctl stop`, trigger logging, delete audit. After owning the name, `run`
parks (signal-paused idle) — observe-only in the strongest sense: it does
nothing but hold the name until SIGTERM.

## Acceptance Criteria

1. `dotfiles-runtime daemon run` exists as a **foreground blocking** command
   (the unit's `ExecStart`); no `daemon start`/`stop` subcommands exist.
   (AC 1)
2. Name-first acquisition: `run` calls `RequestName(DO_NOT_QUEUE)` for
   `org.dotfiles.Events` (versionless bus name; interface `org.dotfiles.Events1`
   stays versioned per AD‑34/C4); on contention it **fails fast non-zero**;
   it **never exits 0 before owning the name** (false-success hole closed);
   on `SIGTERM` it releases the name and exits 0. (AC 2)
3. Startup routing is **fatal-vs-recoverable** (AD‑33/B3, AD‑41): fatal
   (bus unavailable, name contention, unrecoverable configuration) exits
   non-zero so the supervisor retries with backoff — a corrupt/partial state
   must never crash-loop the unit; **unseeded (no `current.json`) is a benign
   no-op**: log at info and idle (hold the name, do nothing), never an error,
   never a restart trigger (AD‑33/C5, AD‑11 — the daemon never seeds). (AC 3)
4. After owning the name, `run` performs **zero mutations**: no use-case call,
   no lock acquisition, no history append, no converge (converge-on-start
   belongs to P5‑1‑3). Name-first, then idle — the deferred non-gating
   converge slot is a marked extension point, not behavior. (AC 4)
5. Provisioning owns the unit file; runtime owns the executable (locked
   roles split). The unit sets **`Type=dbus` +
   `BusName=org.dotfiles.Events`**, `Restart=always` (name loss is a clean
   stop, so `on-failure` is insufficient), `RestartSec` backoff, tuned
   `StartLimitIntervalSec`/`StartLimitBurst`, `Requires=dbus.socket` +
   `After=dbus.socket`, `WantedBy=graphical-session.target` +
   `After=graphical-session.target`, and a `TimeoutStartSec` accommodating
   startup; enablement is via `graphical-session.target.wants/` and works
   with no live user manager (symlink fallback). `ExecStart` is exactly the
   foreground `daemon run`. (AC 5)
6. **Locking/layering:** the daemon acquires **no lock across any use-case
   call** — and in this story it makes no use-case call at all (AD‑35;
   `flock` non-reentrancy). Core stays synchronous (AD‑35/AD‑12 delta binds
   the core, not the edges); the D‑Bus dependency lives behind a port +
   adapter seam (core never imports D‑Bus, AD‑34), with the concrete Python
   D‑Bus client library choice **deferred** (a fake covers tests). (AC 6)
7. Surgical scope: one commit; `uv run --directory src/runtime pytest` +
   `ruff` + `mypy` + layering gate
   (`tests/architecture/test_layering.py`) green; no live bus/systemd in
   tests. (AC 7)

## Tasks / Subtasks

- [x] Add the `daemon` Typer sub-app + `run` foreground command in
      `src/runtime/src/runtime/cli/main.py` (precedent: `wallpaper_app` /
      `inspect_app` composition; `run` blocks until SIGTERM), with NO
      `start`/`stop` subcommands (AC: 1)
- [x] Add `daemon` to the `main_callback` auto-seed skip (AD‑11: the daemon
      never seeds; unseeded is benign idle, never auto-seed) (AC: 3)
- [x] Introduce the bus-name seam: a small `IBusNameOwner`-style port
      (pure) + D‑Bus adapter owning `RequestName(DO_NOT_QUEUE)` /
      fail-fast / release-on-SIGTERM, with an injected fake for tests; the
      concrete Python D‑Bus client library choice stays **deferred** (AC: 2, 6)
- [x] Implement startup routing: fatal (bus absent, contention, bad config)
      → non-zero exit; unseeded (no `current.json`) → info log + idle holding
      the name; never exit 0 pre-ownership; SIGTERM → release + exit 0
      (AC: 2, 3)
- [x] Park-after-own: post-ownership idle loop with a marked non-gating
      converge extension point (no call, no lock, no mutation in this story);
      document that P5‑1‑3 fills the slot (AC: 4)
- [x] Provisioning: author the `--user` unit (`Type=dbus` + `BusName`,
      `Restart=always` + backoff, start-limit tuning, `Requires`/`After`
      `dbus.socket`, `WantedBy`/`After` `graphical-session.target`,
      `TimeoutStartSec`, `ExecStart=<runtime> daemon run`) + enablement via
      `graphical-session.target.wants/` with the no-live-user-manager
      symlink fallback; runtime owns only the executable (AC: 5)
- [x] Tests: name-contention fail-fast non-zero; never-exit-0-before-own;
      SIGTERM release path; unseeded benign idle (no error, no exit, no
      mutation); fatal (bus-absent) non-zero; `daemon start/stop` absent;
      auto-seed skipped under `daemon`; layering (D‑Bus import only in the
      adapter); run `pytest` + `ruff` + `mypy` + `test_layering.py`
      (AC: 1–4, 6, 7)

## Dev Notes

- **Where:** CLI surface in `cli/main.py` (composition root only, per
  AD‑1/13/14/25 — same pattern as `_run_wallpaper_set`/`_run_reconcile`
  wiring); bus-name port under `ports/`, implementation under `adapters/`;
  domain stays pure; application layer untouched (no use-case call in this
  story). Unit file + enablement live in provisioning roles, never in the
  runtime package.
- **Layering (AD‑1/13/14/25):** the hexagon is unchanged; reactivity lives
  only at the edges (AD‑35). The core never imports D‑Bus (AD‑34); the
  adapter is the only module that may. Do not create a new store.
- **Lock non-reentrancy (AD‑35):** the daemon holds no lock across use-case
  calls (`flock` is non-reentrant; use cases own `.seed.lock` /
  `.history.lock`). Vacuously satisfied here — `run` acquires no lock and
  calls no use case — and the invariant must be preserved when P5‑1‑3 adds
  converge (converge calls the use case; the daemon must not pre-hold
  either lock).
- **Fatal-vs-recoverable (AD‑33/B3, AD‑41):** this story routes STARTUP
  only. Fatal → process exits non-zero (supervisor backs off and retries;
  never a tight crash-loop — hence `RestartSec` + start-limit tuning in the
  unit). Unseeded is explicitly NOT fatal (C5): log + idle. Later stories
  extend the routing to converge-time failures (corrupt/partial state,
  `ENOSPC` → logged, retried with backoff, surfaced — never crash-loop).
- **Name-first, non-gating converge:** readiness = name owned (`Type=dbus`
  makes systemd consider the service started only then). Converge must never
  gate readiness — so converge is absent here and arrives non-gating in
  P5‑1‑3 behind the extension point left by this story.
- **Observe-only first (AD‑35/AD‑41):** this story performs no automatic
  action at all; the strongest possible observe-only. Status is
  `systemctl --user` (+ process logs); kill switch is `systemctl stop`
  (SIGTERM → release). Richer status/inspect, trigger logging, and the
  delete audit arrive in P5‑1‑4.
- **Deferred (do NOT decide in this story):** Python D‑Bus client library
  choice (must fit the sync core — prefer GLib/sync over asyncio-first);
  inotify library (P5‑1‑3); `WatchdogSec`/`sd_notify` for a
  wedged-but-name-owning daemon; multi-session `state_root` scoping; unit
  enablement is implemented now (symlink fallback) but the no-live-manager
  edge stays covered by tests, not by a live manager.
- **Out of scope:** hub broker/registry (P5‑1‑2), converge + backstop
  (P5‑1‑3), status/kill-switch/audit surface (P5‑1‑4), event contract
  ports/adapters (epic 5‑2), watches (epic 5‑3), shell jobs (epic 5‑4).

## Gate‑1 sub‑decisions (owner ruling required)

1. **Bus-absent at startup:** fatal non-zero exit (supervisor retries with
   backoff) *(recommended — matches "daemon absent ⇒ reduced functionality;
   commands stay authoritative" while letting the supervisor heal a
   transient bus; never exit 0 pre-ownership)* vs benign-idle-without-name?
2. **Bus-name seam shape:** new minimal `IBusNameOwner` port + adapter with
   injected fake *(recommended — keeps the concrete D‑Bus library choice
   deferred and the core D‑Bus-free per AD‑34, testable with no live bus)*
   vs inline minimal adapter call in the CLI with a later extraction?
3. **Auto-seed skip:** add `daemon` to the `main_callback` no-seed tuple
   alongside `reconcile`/`inspect`/`doctor` *(recommended — AD‑11/C5: the
   daemon never seeds; unseeded is benign idle)* vs a dedicated guard inside
   `daemon run`?
4. **Post-ownership idle mechanism:** signal-paused blocking wait on the
   bus connection (no timers, no polling) *(recommended — zero CPU, no
   state polling, SIGTERM wakes cleanly)* vs a bounded sleep loop?
5. **Unit `RestartSec`/start-limit values + `TimeoutStartSec`:** adopt
   conventional backoff (e.g. `RestartSec=5s`, `StartLimitIntervalSec=60`,
   `StartLimitBurst=3`, `TimeoutStartSec` accommodating cold start)
   *(recommended as starting values — confirm exact numbers)* vs tighter /
   looser tuning?
6. **Confirm the split:** P5‑1‑1 as scoped here (no hub, no converge, no
   mutation) — confirm converge-on-start stays in P5‑1‑3 and is NOT
   smuggled into 5‑1‑1, and that provisioning (not runtime) authors +
   enables the unit file?
