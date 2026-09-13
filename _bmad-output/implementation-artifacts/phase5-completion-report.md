# Phase 5 — Completion Report & Sign-off

Date: 2026‑09‑13
Branch: `master`
Reviewed/verified HEAD: `c9f2794` (working tree carries the review's
uncommitted fixes, tests, and docs — nothing committed, per the brief)
Scope: adversarial Gate‑2 review of the two most recent slices + real
end‑to‑end validation + bookkeeping reconciliation.

> **Honesty note.** Every number below is from a command executed in this
> workspace against `c9f2794` + the review's working-tree changes. Where a
> claim could not be validated in this environment it is listed explicitly
> under "Not validated". Nothing is asserted from prose.

## 1. Verification (exact)

| Gate | Command | Result |
| --- | --- | --- |
| Runtime full suite | `uv run --directory src/runtime pytest` | **1597 passed, 2 skipped** |
| Layering | `uv run --directory src/runtime pytest tests/architecture/test_layering.py` | **105 passed** |
| Contract conformance | `make contracts-check` | **29 passed** |
| Contracts diff | `git diff --stat -- contracts/` | **empty** (no contract change) |
| New E2E (private bus, real processes) | `pytest tests/integration/test_phase5_reactive_runtime_e2e.py` | **2 passed** |
| Provisioning unit (not touched) | `uv run --directory src/provisioning pytest tests/unit -q` | **545 passed** |
| Provisioning daemon role (not touched) | `pytest tests/unit/test_runtime_daemon_role.py` | **20 passed** |
| Lint (touched files) | `ruff check` / `ruff format --check` | clean |
| Types | `mypy src` | 6 pre-existing errors (models.py ×1, actual_state.py ×1, main.py ×4), **zero new** |

Baseline at review start: 1591 passed / 2 skipped; layering 105;
contracts-check 29. The +6 tests are the two E2E tests and four regression
tests added with the two fixes (one file contributes 2, one 3, one 1).

## 2. What is complete (commit + evidence)

| Capability | Commit(s) | Evidence |
| --- | --- | --- |
| Daemon unit + supervised user unit | `5e06485` | `test_daemon_run.py`, `test_runtime_daemon_role.py` (20); `daemon run --activate` E2E owns the name |
| Hub domain core (registry/leases/epoch) | `a82eb73` | `test_hub_registry.py` |
| Hub wire dispatch (job surface) | `2681e97` | `test_dbus_dispatch.py` |
| Hub event surface (Emit/GetTopicState/5 signals/JobsCleared/restart) | `b1674aa`, drain fix `0e95bd1` | `test_dbus_dispatch.py`, `test_dbus_conformance.py`, `test_emit_validation.py`; E2E `GetTopicState` |
| Event contract `org.dotfiles.Events1` | `b1674aa` | `test_event_contract_conformance.py`, `test_event_contract_drift.py` |
| Event contract `org.dotfiles.Job1` + fail-loud `Control` (N2) | `f31103a` | `test_control_channel.py`, `test_dbus_conformance.py`, `test_dbus_job_client.py`; E2E unknown-job → `org.dotfiles.Events1.UnknownJob` |
| Watch + reactive converge + persisted backstop | `b1674aa`, schema `63a2b07`, opt-in `eb06a61` | `test_watch_*`, `test_reactive_converge.py`, `test_converge_backstop.py`, `test_inotify_watch_source.py`; E2E: exactly one `reactive` line per change |
| Capture job host + control channel | `f31103a`, `c9f2794` | `test_capture_host_integration.py`, `test_job_hub_wiring.py`; E2E: real `capture` process + pause/resume/stop |
| Speed-test job | `b1674aa`, harden `93d79f0` | `test_speedtest_job.py` |
| ICME `icme.saved` event + provisioning deploy | `b1674aa`, `c5b87be` | `test_icme_saved.py`; `test_gui_tools_role.py` |
| Bar consumer binding + `(epoch,seq)` hydration | `b1674aa`, `f6544db`, deploy `c5b87be` | `event-bus-core.ts` subscribe-before-read; node drift test; `ags bundle` green |
| Reactive prune opt-in (default off) | `eb06a61`, R1 fix | `test_cli_reactive_converge.py::TestReactivePrunePolicy`; E2E: no deletion and no `prune` line by default, real removal + one `prune` line when opted in (R1 resolved) |
| Status surface (`inspect daemon` / kill-switch / audit) | `0e95bd1` | `test_cli_inspect_daemon.py`; E2E: real `inspect daemon --format json` reports present + epoch |
| `sd_notify` readiness + watchdog | `1f0fc67` | `test_systemd_notify.py`; unit template `WatchdogSec=30`, `NotifyAccess=main` |
| Session-scoped `state_root` | `1f0fc67` | `test_cli_state_root.py` |
| Provisioning wiring (daemon unit, GJS modules, verify) | `5e06485`, `1f0fc67`, `c5b87be` | `test_runtime_daemon_role.py`, `test_gui_tools_role.py`, `test_verify_role.py`, `test_compositor_configs_role.py` |

## 3. Gate‑2 verdicts

| Slice | Verdict | Notes |
| --- | --- | --- |
| Job control channel (`f31103a`) | **CHANGES-REQUIRED → RESOLVED** | Blocking **B1** (hub pump dropped the outer `Control` ack under interleaved calls → false `UnknownJob`) reproduced and fixed; regression test added. Post-fix: APPROVED-WITH-FOLLOWUPS. |
| Production capture host + re-entrancy (`c9f2794`) | **CHANGES-REQUIRED → RESOLVED** | Blocking **B2** (recorder-start failure leaked the hub lease and masked the real error) reproduced and fixed; 3 regression tests added. Non-blocking N1 (fire-and-forget launcher). Post-fix: APPROVED-WITH-FOLLOWUPS. |

Full review: `p5-4-job1-control-capture-host-gate2-review.md`.

Prior Phase‑5 Gate‑2 verdicts stand (all recorded beside their artifacts):
`p5-1-2b-ii-a/ii-b` CHANGES-REQUIRED (B1 heterogeneous-array drain) — **closed
by `0e95bd1`**, which guards the mapping in `_drain_signals`; `epic5-2` /
`epic5-3` / `epic5-4` APPROVED-WITH-FOLLOWUPS, with the earlier N1/N2
addendum closures now proven end-to-end on a real bus by this review.

## 4. End-to-end validation performed

New repeatable harness:
`src/runtime/tests/integration/test_phase5_reactive_runtime_e2e.py`
(guarded to skip when `dbus-daemon`, the `dotfiles-runtime` script, or
Linux/inotify are absent). It uses a **private** `dbus-daemon` session bus and
**real processes** — never the developer's live session bus or desktop. The
daemon's reloader binaries are shimmed on its `PATH`.

Exercised and passing:

- `dotfiles-runtime daemon run --activate` starts, owns
  `org.dotfiles.Events`; the real `dotfiles-runtime inspect daemon
  --format json` reports `daemon_present=true`, `bus_available=true`, and a
  non-null epoch.
- A watched spine input change (the relocated `desired.json`) triggers a
  reactive converge that appends **exactly one** additional `reactive`
  history line, and writes the `last-converged.json` backstop. (A fully-fresh
  seeded state is used so the composite's derivation steps are cache hits and
  no csg/weg/itr tool is invoked.)
- Reactive prune is **skipped by default**: no cache entry is removed
  anywhere and no `prune` history line is written (R1; see §6).
- With `--prune-on-reactive` the AD-30-bounded prune runs exactly once after
  the declarative step and writes exactly one `prune` line whose `removed`
  count equals the entries actually deleted.
- `dotfiles-runtime capture` registers a real `capture` job
  (`GetActiveJobs`), `Control` pause → `capture.state == paused`, resume →
  `recording`, stop → `idle`, the job disappears, and the capture process
  exits 0.
- Hub `Control` with no such job fails loud:
  `org.dotfiles.Events1.UnknownJob`.
- `GetTopicState("capture.state")` hydration returns the topic state
  including the reserved `_epoch`/`_seq` members.

## 5. Not validated (and why)

- **Live GJS/AGS bar end-to-end.** The bar's hydration core
  (`event-bus-core.ts`) is unit-tested under node and bundle-checked, and the
  hub's `GetTopicState` is E2E-verified here — but a live bar rendering
  `capture.state` over a real session was **not** run (would require a live
  graphical session and risks the real desktop; the repo guard forbids
  spawning real desktop binaries from tests).
- **Container-target provisioning integration**
  (`src/provisioning/tests/integration/test_apply_verify_container.py`): not
  run — needs podman/docker and a disposable target, unavailable/too heavy
  here.
- **Live user systemd manager.** The daemon unit is validated structurally
  (rendered unit, tasks, vars) and the daemon binary is E2E-validated on a
  private bus, but `systemctl --user`/`sd_notify` against a live manager was
  not exercised (no user manager in this harness). `sd_notify` is unit-tested.
- **The 2 "pre-existing unrelated provisioning unit failures"** reported in
  earlier artifacts (`test_compositor_configs_role`, `test_packages_role`)
  are **not reproducible at this HEAD**: the full provisioning unit suite is
  **545 passed**, and both files pass in isolation (25 and 20 tests). They
  were fixed by the Phase‑5 provisioning commits / their tests were updated;
  no residual failure remains. This report records the correction rather than
  repeating a stale claim.

## 6. Findings & residual risks

### E2E finding R1 — the declarative step trimmed beyond-keep entries even with `--prune-on-reactive` off — **RESOLVED**

Original defect: with 7 prunable palette entries and the opt-in flag **OFF**,
a reactive converge reduced the palette cache from 8 to 5 entries and wrote
**no** `prune` line. The deletions came from the declarative step
(`_run_converge` → `ConvergeUseCase`, which executed `prunable_hashes`), not
from `_run_prune`. With the flag **ON**, `_run_prune` ran but reported
`removed=0` (the declarative step had already deleted them) yet still wrote a
`prune` audit line — a surprise-deletion / misleading-audit risk relative to
AD‑30, and the opt-in did not protect data.

**Resolution (R1 fix).** The opt-in is now literally true and the double
deletion is gone:

- `_run_converge(*, suppress_history=False, allow_delete=True)`. With
  `allow_delete=False` the deletion executor is a no-op (returns `False`), so
  `ConvergeUseCase` plans the AD-30 removals but physically deletes nothing
  and reports no deleted hashes. The manual `reconcile` path keeps
  `allow_delete=True` — Phase 4 behavior unchanged.
- `_run_reactive_converge` always calls
  `_run_converge(suppress_history=True, allow_delete=False)`: the daemon's
  declarative leg never deletes.
- Deletion in the reactive path is solely the `_run_prune` leg, gated by
  `prune_on_reactive`. OFF (default): no `_run_prune`, no cache entry removed
  anywhere, no `prune` history line; the read-only INFO "would remove N" log
  (`_log_reactive_prune_skipped` / `_build_prune_plan`) is computed at the
  settled state. ON: `_run_prune(dry_run=False, keep=_keep(),
  prune_pinned=False)` runs exactly once after the declarative leg, producing
  exactly one `prune` line whose counts equal the entries actually removed
  (> 0 when entries are prunable).

Evidence (real, non-tautological — the declarative step is **not** faked):
`tests/unit/test_cli_reactive_converge.py::TestReactivePrunePolicy` (OFF:
palette entry set byte-identical + exactly one `reactive` line + no `prune`
line; ON: real deletion, `removed == 3 > 0`, one `reactive` + one `prune`
line, floor respected), the manual-reconcile guards in
`tests/unit/test_cli_planner_wiring.py`, and the private-bus real-process E2E
`tests/integration/test_phase5_reactive_runtime_e2e.py` (OFF: 8 → 8 entries,
no `prune` line; ON: real removal with the audit count matching). AD‑30,
AD‑35, AD‑40 and AD‑41 are preserved.

### Other non-blocking findings (from the Gate‑2 review)

- N1 launcher is fire-and-forget; a failed recorder start is silent to the
  user (no liveness confirmation).
- N2 the real capture controller's transition errors are untyped (surface as
  `HubError`, not `NotControllable`).
- N3 `DbusControlChannel._pending` is single-thread-only (benign today).
- N4 `Control` after lease expiry can still reach a live endpoint.

## 7. Deferred items

1. Live GJS/AGS bar E2E (Section 5).
2. Container-target provisioning integration test (Section 5).
3. Live user-systemd `sd_notify`/watchdog validation (Section 5).
4. ~~E2E finding R1 (declarative trim vs. prune opt-in)~~ — **resolved**:
   the declarative leg is now plan-only in the reactive path and the opt-in
   gates the sole deletion pass (see §6).
5. Launcher liveness/error surface (N1).

## 8. Files changed by this review (uncommitted)

Production (2 files, both surgical):
- `src/runtime/src/runtime/adapters/dbus_event_bus.py` — `DbusControlChannel`
  reply stash (`_pending`/`_take_pending`/`_complete_reply`) + `_send_and_pump`
  stashing (B1 fix; +41/-7).
- `src/runtime/src/runtime/application/capture.py` — `CaptureController.start`
  ends the job on recorder-start failure before re-raising (B2 fix; +15/-1).

Tests (4 files):
- `src/runtime/tests/unit/test_control_channel.py` — interleaved-ack regression.
- `src/runtime/tests/unit/test_capture_controller.py` — recorder-failure regressions (×2).
- `src/runtime/tests/integration/test_capture_host_integration.py` — host-level recorder-failure regression.
- `src/runtime/tests/integration/test_phase5_reactive_runtime_e2e.py` — **new** repeatable E2E.

Docs (3 files):
- `_bmad-output/implementation-artifacts/p5-4-job1-control-capture-host-gate2-review.md` — **new** Gate‑2 review.
- `_bmad-output/implementation-artifacts/phase5-completion-report.md` — this report.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Phase‑5 states reconciled.

### R1 follow-up fix (this change, uncommitted)

Production (1 file):
- `src/runtime/src/runtime/cli/main.py` — `_run_converge(allow_delete=...)`
  no-op executor wiring; `_run_reactive_converge` passes `allow_delete=False`;
  corrected `daemon run` help + docstrings.

Tests (3 files):
- `src/runtime/tests/unit/test_cli_reactive_converge.py` — policy tests now
  exercise the **real** declarative step (no `_run_converge` fake).
- `src/runtime/tests/unit/test_cli_planner_wiring.py` — manual-reconcile
  `allow_delete=True` guard + `allow_delete=False` no-deletion guard.
- `src/runtime/tests/integration/test_phase5_reactive_runtime_e2e.py` — OFF
  asserts zero deletion; ON asserts the audit `removed` count matches actual
  removal.

`contracts/` is untouched.

## 9. Sign-off

Phase 5 is **functionally complete and validated** for the daemon/hub/event
contract/watch+reactive/capture+control/status/sd_notify/session-scope
surface: full runtime suite green (1597/2), layering 105, contract gate 29,
and real-process bus E2E green. Two blocking defects found by the adversarial
review were fixed surgically with regressions. The sign-off is qualified by
the explicitly deferred items above — most importantly the live GJS bar E2E.
Finding R1 (declarative-trim / prune-opt-in) was subsequently **resolved**:
with the opt-in OFF the reactive path performs no deletion at all, and with it
ON the AD-30-bounded prune runs exactly once and is audited (see §6), so the
prune opt-in is now a real data-safety guarantee.

Branch after verification: `master` (unchanged).
`git log --oneline -1`: `c9f2794 feat(runtime): production capture job host (dotfiles-runtime capture)`.
