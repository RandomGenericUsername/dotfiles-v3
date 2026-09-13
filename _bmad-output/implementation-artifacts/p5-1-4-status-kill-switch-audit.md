# P5‑1‑4: Daemon Observability & Safety Surface (status / kill switch / trigger logs / delete audit)

Status: done

Baseline commit: `b1674aa`

Epic: Phase 5 epic 5‑1 — Daemon foundation, observability & safety (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`; spine
`ARCHITECTURE-SPINE.md` status `final`, AD‑41, AD‑33, AD‑35, AD‑38, AD‑42,
AD‑44). AD‑41 binds: observe-only first; `systemctl --user` status + a
read-only inspect surface; a kill switch stops the unit; every automatic
action is logged with its trigger; the prune delete-audit line is retained;
fatal-vs-recoverable routing.

## Story

As the operator, I want to see the reactive daemon's presence/health and the
persisted last-converged state **without needing the daemon**, stop it with
the standard supervisor command, and trust that every automatic mutation
leaves a trigger-tagged log line and (for deletion) an audit line — so
automatic convergence is never invisible or unrecoverable.

## Context / what P5‑1‑1..5‑4 left

- `daemon run` owns `org.dotfiles.Events` name-first, serves the hub surface
  (job + event), converges-on-start non-gating, watches AD‑39 roots, and
  releases on SIGTERM (P5‑1‑1..P5‑1‑3).
- Observe-only is the shipped default (`--activate` opts in).
- `_run_reactive_converge` runs the composite and appends exactly one
  `trigger="reactive"` line. The daemon prune pass (`_run_prune`) is
  **opt-in, default off** (Gate‑2 N1 resolution, `--prune-on-reactive` /
  `$DOTFILES_REACTIVE_PRUNE`): when opted in it appends exactly one
  `trigger="prune"` line with counts (AD‑30/R‑1); when off there is no
  deletion and no `prune` line. Neither path logged its trigger structurally,
  and there was **no read-only status surface beyond `systemctl`**, and the
  persisted backstop record carried only the input hash (no timestamp).

## Acceptance Criteria (all met)

1. **Read-only status/inspect surface** — `dotfiles-runtime inspect daemon`
   reports, without requiring the daemon: whether `org.dotfiles.Events` is
   owned, the hub epoch (hydrated via `GetTopicState`'s reserved `_epoch`
   when reachable — the contract has no `GetEpoch`), active jobs (via
   `GetActiveJobs` when reachable), the persisted last-converged backstop
   record (inputs hash + timestamp), and the resolved AD‑39 watch-root set.
   Absence of the daemon/bus **degrades explicitly** to
   "absent / reduced functionality" and exits 0 — never an error. ✅
2. **Kill switch** — `systemctl --user stop dotfiles-runtime-daemon` is the
   switch (`SIGTERM → release name → exit 0`); no new self-managed stop
   mechanism, no `daemon stop`/`start` subcommands. The release-on-SIGTERM
   path is pinned twice (existing real-signal loop test + a focused handler
   test). ✅
3. **Trigger-logged automatic actions** — the reactive-converge path logs one
   structured line `automatic action: trigger=reactive action=converge
   outcome=… source=…` (covers the regenerate step inside the composite), and
   the prune path logs `trigger=prune action=prune outcome=… removed=…
   failed=…`. Fields ride both the message and the `LogRecord` (`extra=`).
   ✅
4. **Delete-audit retention** — when the daemon-initiated prune is opted in
   (the real `_run_prune` invoked by `_run_reactive_converge`), it writes
   exactly one `history.jsonl` line `trigger="prune"` with counts; a new
   end-to-end test exercises that daemon path (the existing coverage was the
   manual CLI command, not the daemon composite). The prune leg is opt-in
   (default off, Gate‑2 N1): with it off no delete-audit line is written
   because no deletion occurs. ✅
5. **Observe-only remains the default** — `daemon run` still ships
   observe-only; `--activate` opts in. No default changed. ✅
6. **Story artifact** — this file. ✅

## Tasks / Subtasks

- [x] `adapters/daemon_status.py` (new) — `probe_session_bus` (jeepney,
      defensive: bus absent / name absent / per-call failure all fold into a
      snapshot; no raise) + `assemble_daemon_report` (pure: snapshot +
      backstop record + watch roots → `DaemonReport`). D‑Bus import stays in
      `adapters/` only (AD‑34); name ownership is read (AD‑38), never taken.
- [x] `adapters/converge_backstop.py` — add `BackstopRecord` +
      `read_record()`; `write()` persists an additive `converged_at` UTC
      ISO‑8601 Z timestamp; `read()` stays hash-only so the reactive use case
      contract is unchanged. Pre-timestamp (v1) records still read
      (backward compatible).
- [x] `cli/main.py` — `_run_inspect_daemon` composition + `inspect daemon`
      command (plain/JSON/rich render; exits 0 on degraded).
- [x] `cli/main.py` — `_log_automatic_action` helper; reactive converge logs
      `trigger=reactive` with outcome + watch source; prune logs
      `trigger=prune` with removed/failed counts (dry-run too).
- [x] Kill-switch documentation on `daemon_run` (systemd is the only control
      surface; SIGTERM releases) + focused handler test.
- [x] Tests (new `tests/unit/test_cli_inspect_daemon.py`): report assembly
      present/absent/watch-roots; probe degradation (no bus); CLI exit 0 +
      JSON fields; backstop hash+timestamp surfaced; no stop subcommand;
      SIGTERM handler releases; reactive + prune trigger logs; daemon-path
      prune audit line with counts. Updated `test_converge_backstop.py` for
      the additive timestamp + `read_record`.

## Dev Notes

- **Where:** status adapter under `adapters/` (the only layer allowed to
  import `jeepney`, AD‑34); the pure assembly is bus-free so it is testable
  without a live bus. Composition stays in the `cli/main.py` composition root
  (precedent: `_run_doctor_check`, `_run_inspect_status`).
- **Daemon-independent status (AD‑41):** the probe never raises; no daemon
  and no bus are expected outcomes. `inspect daemon` therefore always exits 0
  unless a genuinely unexpected local error occurs.
- **Epoch read path:** there is no `GetEpoch` in the contract. The hub's
  reserved `_epoch` member on `GetTopicState(topic)` is the read-only
  hydration path; `_STATUS_EPOCH_TOPIC` (`icme.saved`) is only a vehicle for
  it. No contract change (AD‑44 additive-only).
- **Backstop timestamp (AD‑36/AD‑44):** `converged_at` is additive on the
  v1 record; `read_record()` treats a missing timestamp as `None`. The
  machine-checkable JSON Schema now exists:
  `contracts/schemas/last-converged.schema.json` (v1: required `version` +
  `input_hash`, optional additive `converged_at`), embedded byte-identically
  under `src/runtime/src/runtime/adapters/schemas/` and enforced on read via
  `fastjsonschema`. A record that violates it — unknown version, missing
  required field, or mistyped timestamp — is logged and treated as changed
  (never fatal). See Follow-ups (closed).
- **Kill switch (AD‑41):** the unit is `Type=dbus`; `systemctl --user stop`
  sends SIGTERM, the installed handler releases the name, and the process
  exits 0. No `ExecStop`, no self-managed stop, no `daemon stop` subcommand.
- **No lock across use-case calls (AD‑35):** unchanged. The status surface
  takes no lock and invokes no use case; the trigger logging wraps existing
  calls; the daemon prune (when opted in) still holds `.seed.lock` only for
  plan+deletions and appends after release (unchanged).
- **Observe-only default (AD‑41):** unchanged — `_run_reactive_converge`
  remains `observe_only=True` unless `--activate`.
- **Reactive prune opt-in (AD‑30/Gate‑2 N1):** the daemon prune pass is gated
  by `--prune-on-reactive` / `$DOTFILES_REACTIVE_PRUNE` (default false); with
  it off `_run_reactive_converge` does no deletion and writes no `prune` line,
  logging the read‑only would‑be count at INFO. Inert while observe-only. No
  contract change (`prune` is already in the trigger enum).
- **Layering:** no new third-party deps; `daemon_status.py` imports
  `jeepney` (already declared) and sibling adapters only.

## Verification (exact)

- `uv run --directory src/runtime pytest` → **1388 passed, 2 skipped**
  (baseline as queued: 1372 passed, 2 skipped; this story adds 12 tests in the
  new `test_cli_inspect_daemon.py` + 3 `read_record`/timestamp tests in
  `test_converge_backstop.py`, all green).
- `uv run --directory src/runtime ruff check src` → **3 errors, all
  pre-existing and unrelated** (2× B008 `typer.Option` defaults in
  `cli/main.py` `main_callback`/`version`; 1× E501 in `domain/models.py`);
  new/changed files (incl. the new test file) are ruff-clean.
- `tests/architecture/test_layering.py` → **101 passed**.
- `make contracts-check` → **22 passed**.
- `uv run --directory src/runtime mypy src` → same **6 pre-existing errors**
  (domain/models.py, application/actual_state.py, cli_output stubs,
  `main.py` `sections` redefinition in untouched `inspect_cache_list`); the
  new `daemon_status.py` / `converge_backstop.py` are mypy-clean.

## Files

New:
`src/runtime/src/runtime/adapters/daemon_status.py`,
`src/runtime/tests/unit/test_cli_inspect_daemon.py`.

Changed:
`src/runtime/src/runtime/cli/main.py`,
`src/runtime/src/runtime/adapters/converge_backstop.py`,
`src/runtime/tests/unit/test_converge_backstop.py`.

Untouched by this story: `src/provisioning/`,
`src/runtime/src/runtime/adapters/bar_subscriber.py`, all of `contracts/`
(machine definitions); the daemon unit already carries no `ExecStop` and needs
no change for the kill switch (SIGTERM default).

## Follow-ups

- **Backstop schema (AD‑44) — done (follow-up):**
  `contracts/schemas/last-converged.schema.json` (v1: required `version` +
  `input_hash`, optional `converged_at`) is the machine definition; embedded
  byte-identically under `adapters/schemas/`, enforced on read by
  `fastjsonschema`, and pinned by
  `tests/unit/test_contract_schema_conformance.py` and
  `tests/unit/test_backstop_schema.py` under `make contracts-check`.
- **Unit `--activate` + `WatchdogSec`/`sd_notify` — done (follow-up, P5):**
  provisioning appends `--activate` when `runtime_daemon_activate` is true
  (default observe-only) and the unit sets `WatchdogSec=30` +
  `NotifyAccess=main`; the daemon sends `READY=1`/`WATCHDOG=1`/`STOPPING=1`
  (no-op without `NOTIFY_SOCKET`). The reactive prune is a separate opt-in:
  `runtime_daemon_prune_on_reactive` (default `false`) appends
  `--prune-on-reactive`. See `epic5-3-watch-reactive.md` → "P5 follow-up
  closed" and "Reactive prune policy (Gate‑2 N1 resolution)".
- **Degraded watch set is now surfaced (AD‑40, P5 follow-up):**
  `inspect daemon` reports `watch health: unknown|ok|degraded (N unwatched: …)`
  and names each unwatched root (JSON `watch_health`), read from the daemon's
  atomically-persisted `<state_root>/watch-health.json`; `doctor` appends the
  one-line summary without changing its exit code. The status surface stays
  read-only and daemon-independent (no new D-Bus contract).
- **`inspect daemon` rich rendering:** plain/JSON are exact today; rich
  mirrors plain (consistent with the other inspect commands).
