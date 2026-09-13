# Gate 2 Review — P5‑4 job control channel (`f31103a`) + production capture host (`c9f2794`)

Verdict: **CHANGES-REQUIRED → RESOLVED** — two **blocking** defects were
reproduced by execution and fixed surgically during this review; everything
else is non-blocking. Overall post-fix disposition:
**APPROVED-WITH-FOLLOWUPS**.

Reviewed at `c9f2794` (tree clean at review start), plus the two fixes and
regression tests landed by this review (uncommitted, per the no-commit
constraint). Reviewer performed independent execution, not prose reading.

Reviewed slices:

| Slice | Commit | Content |
| --- | --- | --- |
| A — job control channel | `f31103a` | `org.dotfiles.Job1.Control` on the job's unique connection; hub-side `DbusControlChannel`; request/response delegation outside the dispatcher lock; fail-loud `Control` (N2 closure) |
| B — production capture host | `c9f2794` | `dotfiles-runtime capture` (resident host: BeginJob/RenewJob/EndJob/Emit + `Job1.Control` serving + degrade-to-local); launcher spawns the host; re-entrancy fix (symmetric single-thread pumping) |

## Verification (executed by reviewer)

| Check | Result |
| --- | --- |
| `uv run --directory src/runtime pytest` (full, post-fix) | **1597 passed, 2 skipped** (pre-fix baseline 1591/2; +6 new tests) |
| `tests/architecture/test_layering.py` | **105 passed** |
| `make contracts-check` | **29 passed** |
| `contracts/` diff | **empty** (no contract change) |
| `ruff check` (touched files) | clean (repo-wide: 3 pre-existing: 2× B008 `main.py`, 1× E501 `models.py`) |
| `mypy src` | **6 pre-existing errors**, zero new (models.py ×1, actual_state.py ×1, main.py ×4) |
| New E2E (private `dbus-daemon` bus, real procs) | **2 passed** (see `tests/integration/test_phase5_reactive_runtime_e2e.py`) |
| Adversarial repros | B1/B2 reproduced deterministically, then re-run green after the fixes |

## Claims verified (file:line)

**Slice A — job control channel**

- The served job surface (`Control(action:s)`, path, interface) is
  single-sourced and contract-pinned: `JOB_OBJECT_PATH`/`JOB_INTERFACE`/
  `JOB_METHODS` (`dbus_event_bus.py:101-110`), served by the job client
  (`dbus_job_client.py:217-259`), and both `test_dbus_conformance.py` and
  `test_event_contract_drift.py` pin them against the XML/JSON Job node.
- The hub validates the action against the domain allowlist under the lock,
  then delegates **outside** the lock: `HubService._dispatch_control`
  (`dbus_event_bus.py:605-622`) — the lock is released before
  `channel.send_control`, so a job callback cannot deadlock the dispatcher
  (pinned by `test_outbound_call_runs_outside_the_dispatcher_lock`).
- Success only on the job's ack; no channel ⇒ typed `UnknownJob` (N2):
  `dbus_event_bus.py:618-622`; typed job errors cross via
  `_raise_typed_error` (`:900-914`). Live proof: E2E `Control("no-such-job")`
  → D‑Bus error `org.dotfiles.Events1.UnknownJob`.
- Endpoint bookkeeping is bus-attested: `BeginJob`'s sender becomes the
  control endpoint and `EndJob` / `NameOwnerChanged` drop it
  (`dbus_event_bus.py:1114-1119`, `:1061-1066`); pinned by
  `TestOwnerControlWiring`.
- Re-entrancy: the hub pumps interleaved messages while awaiting the ack
  (`_send_and_pump`, `dbus_event_bus.py:829-882`) and the job stashes
  non-matching replies (`DbusJobClient._call` / `_take_pending`,
  `dbus_job_client.py:109-149`). Real-bus E2E: pause/resume/stop each return
  `< 0.1 s` and the `capture.state` transitions land.

**Slice B — production capture host**

- `dotfiles-runtime capture` composes the tested controller over an injected
  `IControllableJobClient` + `IRecorderProcess`
  (`application/capture_host.py:49-129`, `cli/main.py:1640-1717`); it never
  imports jeepney and never constructs a signal (AD‑34/AD‑38; layering green).
- One bus probe, never a poll; absent daemon ⇒ local reduced mode
  (`cli/main.py:1584-1606`, `adapters/local_job_client.py`). E2E: recorder
  runs, capture job registers, control round-trips.
- The launcher delegates target/backend resolution and spawns the host as the
  single recorder owner; legacy `stop|pause|resume|status` retired
  (`src/gui-tools/capture-tool/bin/capture-tool:161-192`). No remaining
  `capture-tool stop|pause|resume|status` callers (grep across `dotfiles/`
  and `src/`).
- `dotfiles-runtime capture` exits non-zero on a real failure
  (`cli/main.py:1710-1717`); `_run_capture_host` owns the stop/close/restore
  sequence in a `finally` (`cli/main.py:1678-1688`).

## Blocking findings (both reproduced, both fixed in review)

### B1 — hub pump dropped an outer `Control` ack under interleaved calls → false `UnknownJob`

**Reproduced deterministically** (`/tmp` repro, not committed): with two
interleaved `Control` calls on one connection, the outer pump served an
interleaved message that started a *nested* `Control`; the nested pump read
the **outer** ack first and passed it to `serve`, where `_route_message`
ignores non-method-call replies — the outer ack was silently dropped and the
outer `Control` raised `UnknownJob` even though `Control` had been sent.

- Evidence: pre-fix, `_send_and_pump` handled only `reply_serial == serial`
  and otherwise unconditionally `serve(msg)` (`f31103a` version). The job side
  already stashed such replies (`dbus_job_client.py:130-132`) — the hub side
  was the asymmetric half of the "symmetric pumping" claim.
- **Fix** (`dbus_event_bus.py:857-882, 884-895`): mirror the job client —
  stash non-matching method_return/error replies in `_pending`, check
  `_take_pending(serial)` at the top of the wait, and share the typed-error
  handling in `_complete_reply`. Regression:
  `test_control_channel.py::TestDbusControlChannel::test_outer_ack_is_stashed_across_a_nested_pump`.
- Severity: requires two concurrent/pipelined `Control` callers; the bar's
  synchronous `call_sync` alone does not trigger it. Still wire-reachable by
  two consumers, so blocking on a correctness contract ("never reports
  success for a delivery that did not happen" also implies never reporting a
  false failure).

### B2 — recorder-start failure leaked the hub lease and masked the real error

**Reproduced deterministically**: `CaptureController.start` allocated the job
(`begin`) then called `_recorder.start()`; when the recorder raised
("recorder backend exited during startup"), `_job_id` stayed set with
`_state == "idle"`.

- Live result pre-fix (real `_run_capture_host` with a failing recorder):
  `RAISED: RuntimeError -> cannot stop capture: no active recording`;
  `active jobs after failure: {'job-1': 'capture'}` — the lease leaked for
  the full TTL (default 3600 s), `CaptureHost.stop`'s documented
  "never raises" was false, and `_run_capture_host`'s `finally` skipped
  `client.close()` + signal-handler `restore()` because `host.stop()` raised.
- **Fix** (`application/capture.py:94-109`): wrap `_recorder.start()`; on
  failure end the just-begun job (`EndJob(job_id, 1)`, contained), clear
  `_job_id`, and re-raise the original error. `host.stop()` then observes no
  job and returns, so teardown completes and the real error surfaces.
  Regressions:
  `test_capture_controller.py::TestRecorderStartFailure` (2 tests) and
  `test_capture_host_integration.py::TestRecorderStartFailureHost`.
- This closes the earlier `epic5-4` N5 ("leak if recorder fails") into a
  concrete production defect once the host started using the controller.

## Non-blocking findings

- **N1 — the launcher is fire-and-forget with no liveness confirmation.**
  `bin/capture-tool start_recording` spawns `dotfiles-runtime capture`
  detached and immediately emits `{"state":"recording"}` with exit 0
  (`bin/capture-tool:182-192`). If the recorder backend dies during startup
  the host now exits non-zero (B2 fix), but the launcher's caller
  (`CaptureWindow.tsx:16-22`) ignores the JSON and the bar indicator is
  event-driven, so a failed start is silent to the user. Not a strand (no
  false indicator), but no error surface. Follow-up: confirm the job appeared
  (or surface a nonzero exit) before reporting success.
- **N2 — the real controller's transition errors are untyped.** The contract
  distinguishes `NotControllable`; `CaptureController.control` raises bare
  `RuntimeError` for an unknown job/invalid transition
  (`application/capture.py:154-170`), which crosses as
  `org.freedesktop.DBus.Error.Failed` → `HubError`, not `NotControllable`.
  The typed path is only exercised by tests. Correct-but-coarse; follow-up.
- **N3 — `_pending` is unguarded on the channel.** Only the single pump thread
  touches it; `close()` clears it from the release thread. Benign today;
  document if the pump ever becomes multi-threaded.
- **N4 — `Control` after lease expiry can still reach a live endpoint.** The
  domain drops a job at TTL but the hub only unbinds on `EndJob` /
  `NameOwnerChanged`; a live process whose lease expired can still be called.
  Low impact (the job is alive); the endpoint is dropped at process exit.

## Panel notes

- **Blind Hunter (correctness):** no lock-order inversion; `HubService._lock`
  is released before every outbound call and re-acquired safely on the
  callback path. Verified the job-side `_pending` matching is serial-exact.
  B1/B2 found by execution, not intuition.
- **Edge Hunter (edges):** nested `Control`, recorder-exits-during-grace,
  `EndJob` failure during cleanup, unknown-job `Control`, dead/timed-out
  endpoint drop, name-owner loss — each has a test or a repro.
- **Acceptance Auditor:** N1 (production host) and N2 (fail-loud `Control`)
  are MET end-to-end on a real bus. `Control` request/response semantics are
  MET. The only unmet sub-claim is the launcher's success signal (N1 above).
  No scope creep; no contract change.

## Follow-ups

1. Give the launcher a liveness/error surface for a failed recorder start (N1).
2. Type the controller's control failures as `NotControllable` (N2).
3. Audit the interaction between the reactive prune opt-in and the
   declarative diff-driven trim — surfaced by the E2E, recorded in
   `phase5-completion-report.md` ("declarative trim" finding).

---
Reviewed files changed by this review (all uncommitted):
`src/runtime/src/runtime/adapters/dbus_event_bus.py`,
`src/runtime/src/runtime/application/capture.py`,
`src/runtime/tests/unit/test_control_channel.py`,
`src/runtime/tests/unit/test_capture_controller.py`,
`src/runtime/tests/integration/test_capture_host_integration.py`,
`src/runtime/tests/integration/test_phase5_reactive_runtime_e2e.py` (new).
