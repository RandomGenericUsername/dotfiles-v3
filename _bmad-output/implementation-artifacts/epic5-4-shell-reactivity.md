# Epic 5‑4 — Shell Reactivity (first slice)

Status: **complete (coherent first slice)** — all new/owned suites green; full
runtime suite green (1372 passed, 2 skipped). Nothing committed (per the
untouched-tree constraint).

baseline_commit: `2681e97` (dirty tree carried P5‑1‑2b‑ii‑a/ii‑b, Epic 5‑2,
Epic 5‑3; NOT reverted — built on top).

Epic: Phase 5 epic 5‑4 — Shell reactivity (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`; spine
`ARCHITECTURE-SPINE.md` status `final`, AD‑34/AD‑37/AD‑38/AD‑40; contract
`contracts/event-contract.json`).

Related: P5‑1‑2b‑ii‑a/ii‑b (hub methods/signals, uncommitted baseline),
Epic 5‑2 (`adapters/bar_subscriber.py`, unchanged), Epic 5‑3 (watch +
reactive converge, unchanged).

## Story

As the desktop user,
I want the shell to react to tool state through the one shared session‑bus
event contract — a resident capture job reporting through the hub's methods,
a bar recording indicator that renders pushed elapsed seconds, a speed‑test
job, and ICME publishing `icme.saved` on save —

so that no part of the shell polls a state file, and every UI indicator is
driven by that tool's **domain** events (never job lifecycle signals),
exactly as AD‑37/AD‑38/AD‑40 require.

## Context / scope of this slice

Epic 5‑4 as written is several subsystems. This slice lands the reusable,
fully‑tested job runtime and the bar/ICME event wiring, with the
out‑of‑process control‑delivery channel called out as the explicit follow‑up
(the contract has no hub→job control signal; adding one is a contract
change and was out of scope). Everything here is exercisable without a live
bus:

- **Job seam** — `ports/jobs.py` (`IJobClient`, `IRecorderProcess`,
  `ISpeedTestRunner`) + `domain/jobs.py` (`SpeedTestResult`,
  `CAPTURE_STATES`). A job reports through the hub's methods and publishes
  DOMAIN events through the hub; it never constructs a D‑Bus signal.
- **Clients** — `adapters/in_process_job_client.py` (co‑hosted/test seam)
  and `adapters/dbus_job_client.py` (production: `BeginJob`/`RenewJob`/
  `ReportProgress`/`EndJob`/`Emit` over jeepney).
- **Capture controller** (`application/capture.py`, AD‑37) — resident state
  machine owning the recorder child; monotonic elapsed; `capture.state` on
  every transition and ≥ 1/s while recording; lease renew; `Control`
  pause/resume/stop.
- **Recorder** — `adapters/subprocess_recorder.py` (owns the child;
  injectable spawn/signaler/clock).
- **Speed‑test job** (`application/speedtest.py`) + real backend
  (`adapters/command_speedtest_runner.py`; tests use a fake runner — no
  network).
- **Bar indicator** (`application/indicator.py`) — Python harness for the
  AGS widget: consumes `capture.state` via `IEventSubscriber`, interpolates
  from a monotonic clock, reads no file. The GJS widget
  (`dotfiles/config/ags/bar/widgets/recording.tsx`) was rewritten from the
  `capture-tool status` poll to a contract `DomainEvent` subscription via a
  new `dotfiles/config/ags/lib/event-bus.ts`; control actions go through the
  hub's `Control` (never shelling the tool).
- **ICME emit** (`application/icme.py` + GJS `lib/event-bus.ts` wired into
  `EditorWindow.save()`) — emits `icme.saved {path}` on save; per the
  validate‑gate ruling **C1** it is a BAR/UI event, NOT a daemon trigger
  (the daemon observes ICME via the watched icon‑mappings file, Epic 5‑3).
- **Hub control delivery** — `EventHub.control` now records a `control`
  sink entry after the allowlist check; `HubService.register_control` fans
  it to a co‑hosted job. This makes the hub the single control path in the
  in‑process slice.

## Acceptance Criteria (all met)

1. **Capture as a resident lifetime job (AD‑37).** `CaptureController`
   allocates `BeginJob(kind="capture", ttl)`, renews the lease every
   cadence, reports progress, ends with `EndJob`, and owns an
   `IRecorderProcess` child. It starts in `idle`, transitions
   `recording ↔ paused → idle`. ✅
2. **`capture.state` payload + cadence.** Every transition emits
   `capture.state {state, elapsed_seconds}`; while recording it emits at
   least once per second. `elapsed_seconds` is an int derived from a
   monotonic clock plus the recorded segment start — never a file or shared
   wall clock; paused time is excluded. An additive optional `job_id` rides
   the event so the bar can route `Control` without a second read. ✅
3. **Domain events through the hub, never direct signals (AD‑38).** The
   controller/jobs publish only via `IJobClient.publish` (the hub's
   validated `Emit`). Application modules import no jeepney/dbus/gi; a test
   pins that. ✅
4. **Hub is the single control path.** `EventHub.control` validates against
   `CONTROL_ALLOWLIST["capture"] = {pause, resume, stop}` and records the
   validated action; `HubService.register_control` delivers it to the
   co‑hosted job. `Control(job_id, "explode")` is `NotControllable` and
   never reaches the job. ✅
5. **Bar recording indicator (AD‑40).** The Python harness subscribes to
   `capture.state` through `IEventSubscriber`, renders pushed
   `state`/`elapsed_seconds`, and interpolates locally while recording; it
   reads no status file. The GJS AGS widget no longer calls
   `spawn_command_line_sync`/`capture-tool status`; it subscribes to the
   contract `DomainEvent` signal and uses the hub `Control` method. ✅
6. **Speed‑test job.** `SpeedTestJob` runs a fake (tests) or real
   `ISpeedTestRunner`, emits exactly one `speedtest.finished
   {down_mbps, up_mbps, latency_ms}` with contract‑typed doubles, and ends
   `0`; a failing measurement ends `1` and re-raises. ✅
7. **ICME `icme.saved` emit + ruling C1.** `emit_icme_saved` publishes
   `icme.saved {path}` via `IEventPublisher`; the GJS editor publishes on a
   successful save. Tests pin that the daemon/converge never reference
   `icme`, and that `icme.saved` is a known topic but not a bar render
   topic. ✅
8. **UI indicators are domain‑driven only (AD‑37).** The indicator
   subscribes only to `capture.state`; `JobStarted`/`JobFinished` are never
   delivered to it. ✅
9. **Consumer‑side vs hub caps unchanged; no contract change.** Structural
   caps stay 64 KiB / depth 8 (drift test green); `contracts/` untouched. ✅
10. **Surgical scope.** One coherent slice, no new third‑party dependency
    (jeepney/fastjsonschema already declared); ruff/mypy/layering green on
    owned files. ✅
11. **Story artifact.** This file records status, ACs, tasks, dev notes,
    exact results. ✅

## Tasks / Subtasks

- [x] `domain/jobs.py` — `CAPTURE_STATES` (mirrors the contract enum) and
  the frozen `SpeedTestResult` (floats so the `a{sv}` variants are `d`).
- [x] `ports/jobs.py` — `IJobClient`, `IRecorderProcess`, `ISpeedTestRunner`
  (ABCs only, layering rule).
- [x] `adapters/in_process_job_client.py` — registry + publisher binding.
- [x] `adapters/dbus_job_client.py` — jeepney client over the hub's methods
  (`BeginJob`/`RenewJob`/`ReportProgress`/`EndJob`/`Emit`); injectable
  connection; `a{sv}` wrapping reuses the hub codec.
- [x] `adapters/subprocess_recorder.py` — owns the recorder child
  (SIGUSR2 toggle / SIGINT finalize); injectable spawn/signaler/sleep.
- [x] `adapters/command_speedtest_runner.py` — Ookla JSON backend; injectable
  command runner.
- [x] `application/capture.py` — `CaptureController` (monotonic elapsed,
  cadence, renew, transitions, `control`, `serve`).
- [x] `application/speedtest.py` — `SpeedTestJob` (begin → progress →
  publish → end; failure path ends non‑zero).
- [x] `application/indicator.py` — `RecordingIndicator` + `IndicatorView`.
- [x] `application/icme.py` — `emit_icme_saved` (`icme.saved {path}`).
- [x] `domain/hub.py` — `HubEvent.action`; `EventHub.control` records a
  `control` sink entry after validation.
- [x] `adapters/dbus_event_bus.py` — `HubService.register_control` +
  `_notify_control` (contained fan‑out; no wire signal — same as
  `job_adopted`).
- [x] GJS bar: `dotfiles/config/ags/lib/event-bus.ts` (DomainEvent
  subscription + `Control` call) and poll‑free `recording.tsx`.
- [x] GJS ICME: `src/gui-tools/icon-color-mapping-editor/lib/event-bus.ts`
  (`publishIcmeSaved`) wired into `EditorWindow.save()`.
- [x] Tests: `test_capture_controller`, `test_speedtest_job`,
  `test_recording_indicator`, `test_icme_saved`, `test_dbus_job_client`,
  `test_job_hub_wiring` (47 tests; fakes only, no live bus).

## Dev Notes

- **Monotonic elapsed, never a file (AD‑40).** The controller accumulates
  completed segment durations and adds the live segment delta from the
  injected monotonic clock. Paused time is excluded. The bar harness does
  the same on the consumer side (local interpolation), and the GJS widget
  updates a label on a 1 s timer — a rendered continuous value, not a state
  read. The legacy `capture-tool status` poll (500 ms) is gone from the bar.
- **Domain vs lifecycle (AD‑37).** `JobStarted`/`JobProgress`/`JobFinished`
  stay job/lifecycle signals; the recording indicator consumes only
  `capture.state` (a `DomainEvent`). The wiring test asserts lifecycle
  signals exist on the hub while the domain subscriber sees only
  `capture.state`.
- **Control delivery (slice boundary).** The contract has no hub→job control
  signal/method. This slice delivers `Control` to a **co‑hosted** job via the
  hub's control sink (fully tested). Out‑of‑process delivery — a
  `capture-tool` process receiving `Control` from the daemon — requires a
  contract addition and is deferred (see Follow‑ups). The GJS bar already
  calls `Control` per AD‑37, so only the job‑side reception is pending.
- **Rate cap interaction.** `capture.state` at the contract‑required ≥ 1/s
  exactly consumes the hub's 60/min per‑(sender, topic) budget; extra
  transition emits in the same window can hit `RateLimited`. Delivery is
  at‑most‑once and the bar interpolates locally, so a dropped tick is
  invisible; a per‑topic budget is a follow‑up (the rate numbers are code
  constants pinned by `test_emit_validation`/`test_dbus_dispatch`, not
  contract fields).
- **Additive `job_id` on `capture.state`.** Non‑breaking per AD‑34; the JSON
  topic schema has `additionalProperties: true`, so `EmitValidator` accepts
  it (pinned by a test). Consumers must not rely on it for identity
  (AD‑38: producer identity is never trusted).
- **No direct signals (AD‑38).** The job adapters are the only place that
  talks to the bus; the application layer imports no jeepney/dbus/gi (AST
  test). `DbusJobClient.publish` goes through `Emit`, so the hub validates
  and the hub emits `DomainEvent`.
- **Subprocess recorder signals.** gpu-screen-recorder uses `SIGUSR2` as a
  pause/resume toggle and `SIGINT` to finalize; the adapter encodes that.
  wf-recorder has a different toggle (`SIGSTOP`/`SIGCONT`); backend‑specific
  handling is a follow‑up (selection logic still lives in
  `bin/capture-tool`).
- **ICME ruling C1.** `icme.saved` is emitted for consumers but is not a
  daemon trigger; the daemon already observes ICME through the watched
  `icon-mappings` file (Epic 5‑3). A test pins that no daemon/converge
  function references the topic and that `emit_icme_saved` is not called by
  the runtime.
- **GJS validation.** No JS test runner exists (`tsc` absent), but `ags
  bundle` is a real transpile/typecheck gate and was run on both the bar and
  ICME apps (both exit 0). The drift test's shell‑literal scan also covers
  the new `dotfiles/config/ags/lib/event-bus.ts`.
- **Untouched by this slice.** `adapters/bar_subscriber.py` (Epic 5‑2),
  `contracts/` (machine definitions), the Epic 5‑3 watch/converge modules,
  and `cli/main.py` (no daemon wiring changed).

## Exact test results

| Command | Result |
| --- | --- |
| `uv run --directory src/runtime pytest` (full) | **1372 passed, 2 skipped** (baseline 1315/2; +57 = 47 new tests + 10 new layering parametrizations) |
| `uv run --directory src/runtime pytest tests/unit/test_capture_controller.py` | **14 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_speedtest_job.py` | **4 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_recording_indicator.py` | **8 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_icme_saved.py` | **5 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_dbus_job_client.py` | **7 passed** |
| `uv run --directory src/runtime pytest tests/unit/test_job_hub_wiring.py` | **9 passed** |
| `uv run --directory src/runtime pytest tests/architecture/test_layering.py` | **100 passed** (was 90; +10 new source files) |
| `make contracts-check` | **22 passed** |
| `uv run --directory src/runtime ruff check src` | 3 errors, **all pre‑existing/unrelated**: 2× B008 `typer.Option` in `cli/main.py`, 1× E501 in `domain/models.py`; every new/changed file is clean |
| `uv run --directory src/runtime ruff check tests/unit/test_capture_controller.py … test_job_hub_wiring.py` | **All checks passed** |
| `uv run --directory src/runtime mypy <12 new/changed source files>` | **Success: no issues found** |
| `make -C src/gui-tools/icon-color-mapping-editor test` (node) | **pass** (unaffected) |
| `make -C src/gui-tools/icon-color-mapping-editor lint` (`ags bundle`) | **exit 0** |
| `ags bundle dotfiles/config/ags/app.tsx … --gtk 4` | **exit 0** |

## Files changed

**New (runtime source):** `domain/jobs.py`, `ports/jobs.py`,
`adapters/in_process_job_client.py`, `adapters/dbus_job_client.py`,
`adapters/subprocess_recorder.py`, `adapters/command_speedtest_runner.py`,
`application/capture.py`, `application/speedtest.py`,
`application/indicator.py`, `application/icme.py`.

**Edited (runtime source):** `domain/hub.py` (control sink record +
`HubEvent.action`), `adapters/dbus_event_bus.py` (`register_control` +
`_notify_control`).

**New (tests):** `tests/unit/test_capture_controller.py`,
`test_speedtest_job.py`, `test_recording_indicator.py`, `test_icme_saved.py`,
`test_dbus_job_client.py`, `test_job_hub_wiring.py`.

**New (shell):** `dotfiles/config/ags/lib/event-bus.ts`,
`src/gui-tools/icon-color-mapping-editor/lib/event-bus.ts`.

**Edited (shell):** `dotfiles/config/ags/bar/widgets/recording.tsx` (poll
removed), `src/gui-tools/icon-color-mapping-editor/ui/EditorWindow.tsx`
(publish `icme.saved` on save).

**New:** this artifact.

**Untouched (constraints):** `contracts/event-contract.{xml,json,md}`,
`src/runtime/src/runtime/adapters/bar_subscriber.py`, Epic 5‑3 watch/converge
modules, `cli/main.py`; nothing committed.

Note: `adapters/in_process_hub.py` appears modified in `git status` from the
carried P5‑1‑2b‑ii baseline, not from this story.

## Follow‑up items

1. **Out‑of‑process `Control` delivery.** Add a contract‑compatible hub→job
   control channel (e.g. a `Control` signal or a job‑owned callback method)
   so a standalone `capture-tool` process receives pause/resume/stop; then
   wire a `dotfiles-runtime capture` resident host and retire the legacy
   `bin/capture-tool` control surface.
2. **`capture.state` rate budget.** Consider a larger/per‑topic budget (or
   coalescing transitions) so ≥ 1/s cadence plus transitions cannot trip the
   60/min cap; keep the code‑constant/tests in sync.
3. **Daemon‑hosted job runner.** Host the resident capture job inside
   `daemon run` (or a supervised sibling) with signal‑based stop, so the
   in‑process control path is the production path.
4. **Backend‑specific recorder toggles.** Handle `wf-recorder`
   (`SIGSTOP`/`SIGCONT`) vs gpu-screen-recorder (`SIGUSR2` toggle) in
   `SubprocessRecorder`.
5. **Bar hydration on start.** The GJS `DomainEventBus` currently relies on
   the next push; add subscribe‑before‑read (`GetTopicState`) so a bar that
   starts mid‑recording shows the timer immediately.
6. **ICME end‑to‑end.** The GJS `publishIcmeSaved` is bundle‑checked only
   (no JS runner); a VM smoke test should confirm the hub receives
   `icme.saved` and that the bar/daemon behavior is unchanged.
