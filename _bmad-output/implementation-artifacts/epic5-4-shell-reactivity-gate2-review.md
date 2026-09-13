# Gate 2 Review — Epic 5‑4 (Shell Reactivity, first slice)

Verdict: **APPROVED-WITH-FOLLOWUPS** — the job seam, capture controller,
speed-test job, indicator, `icme.saved` emit, and the hub control fan-out
are real and green, and both GJS bundles transpile. No blocking findings.
The main risks are that the runtime job layer is not yet wired into any
production host and that the hub answers `Control` successfully even when no
job consumes it.

Artifact: `epic5-4-shell-reactivity.md` (status "complete (coherent first
slice)"; states "nothing committed" — actually committed in `b1674aa`).
Reviewed at `b1674aa`, clean tree.

## Verification (executed by reviewer)

| Check | Result |
| --- | --- |
| `pytest test_capture_controller test_speedtest_job test_recording_indicator test_icme_saved test_dbus_job_client test_job_hub_wiring` | **47 passed** (14+4+8+5+7+9; matches the artifact) |
| Full suite / layering / contracts-check | **1372 passed, 2 skipped** / 100 / 22 |
| `make -C src/gui-tools/icon-color-mapping-editor lint` (`ags bundle … --gtk 4`) | **exit 0** (independently re-run) |
| `make -C src/gui-tools/icon-color-mapping-editor test` (node) | **pass** |
| `ags bundle dotfiles/config/ags/app.tsx … --gtk 4` | **exit 0** (independently re-run) |

Verified claims:

- **Domain events through the hub, never direct signals.** Application
  modules import no jeepney/dbus/gi; the transport lives in
  `adapters/{in_process,dbus}_job_client.py`. `DbusJobClient.publish` calls
  `Emit` (`dbus_job_client.py:78‑80`); layering test green.
- **Resident capture job.** `CaptureController` allocates
  `BeginJob(kind="capture", ttl)`, renews, publishes
  `capture.state {state, elapsed_seconds}` on every transition and cadence,
  monotonic elapsed, paused time excluded, `EndJob(0)`
  (`application/capture.py:90‑179`).
- **Hub is the single control path.** `EventHub.control` validates against
  `CONTROL_ALLOWLIST["capture"]` and records a `control` sink entry
  (`domain/hub.py:281‑303`); `HubService.register_control`/`_notify_control`
  fan it out with contained handler errors
  (`dbus_event_bus.py:481‑494`, `:586‑604`); `Control(job,"explode")` →
  `NotControllable` (`test_dbus_dispatch.py:194‑198`).
- **Speed-test job** emits exactly one `speedtest.finished` with float
  fields and ends `0`/`1` (`application/speedtest.py`, 4 tests).
- **ICME ruling C1.** `emit_icme_saved` publishes `icme.saved {path}`
  (`application/icme.py`); GJS publishes on save
  (`EditorWindow.tsx`, `b1674aa` diff); tests pin that the daemon/converge
  never reference `icme`.
- **Poll-free bar.** `recording.tsx` subscribes to `capture.state` via
  `event-bus.ts`; no `capture-tool status`/`spawn_command_line_sync`
  remains; elapsed interpolated locally on a 1 s timer
  (`recording.tsx:32‑49`).

## Findings (all non-blocking)

- **N1 — no production host for the job layer.** The capture/speed-test
  jobs and the Python `RecordingIndicator` are exercised only with fakes;
  `daemon run` wires watch/converge but not a job runner, and
  `bin/capture-tool` still owns capture out-of-process. The control path
  that is "fully tested" is therefore in-process-only. The artifact states
  this explicitly (follow-ups 1 and 3, `epic5-4-shell-reactivity.md:257‑269`);
  it must not be mistaken for an end-to-end control capability.
- **N2 — the hub answers `Control` successfully with no consumer.** With no
  registered control handler, `_notify_control` iterates zero handlers and
  the bar's `Control` `call_sync` returns success (`event-bus.ts:78‑95`).
  The UI receives a positive reply for an action nothing performed. Consider
  returning `UnknownJob`/`NotControllable` when no job is co-hosted, or
  documenting the no-op; today it is a silent UI/state divergence.
- **N3 — the GJS bar ignores `(epoch, seq)` and does not hydrate** (see the
  5‑2 review N1). It also routes `Control` using the additive `job_id` field
  (`recording.tsx:38`, `:51‑53`), which is non-breaking per AD‑34 but is a
  routing dependency on a field the contract does not guarantee; keep
  AD‑38's "producer identity is never trusted" caveat in view.
- **N4 — rate-cap interaction is acknowledged, not resolved.**
  `capture.state` at the contract-required ≥1/s exactly consumes the hub's
  60/min per-(sender, topic) budget, so extra same-window transitions can
  hit `RateLimited` (`epic5-4-shell-reactivity.md:172‑178`). Dropped ticks
  are invisible because the bar interpolates; a per-topic budget is a
  follow-up. Non-blocking, correctly reasoned.
- **N5 — `CaptureController.start()` can leak a hub job if the recorder
  fails to start.** `BeginJob` runs before `self._recorder.start()`
  (`capture.py:94‑96`); a recorder-start exception leaves a live lease that
  only the synthetic-expiry path ends (`JobFinished(-1)`). Acceptable given
  leases, but a try/except `EndJob` would be tidier.
- **N6 — `SubprocessRecorder` encodes gpu-screen-recorder's
  `SIGUSR2`/`SIGINT` only;** `wf-recorder`'s `SIGSTOP`/`SIGCONT` is a
  documented follow-up (`epic5-4-shell-reactivity.md:187‑191`).
- **N7 — ICME GJS literals are outside the drift scan** (5‑2 review N2).
- **N8 — no JS test runner;** the gate is `ags bundle` (independently
  re-run green here) plus the Python textual scan. The Python
  `RecordingIndicator` is a harness, not the shipped widget.

## Panel notes

- Blind Hunter: no correctness blockers in the controller state machine,
  the monotonic elapsed math, or the codec. Checked bool-before-int
  ordering in variant encoding (reused from the hub).
- Edge Hunter: pause/resume/stop transition guards, unknown job id for
  `control`, failed speed-test path, publish/renew failures contained —
  all tested.
- Acceptance Auditor: AC1–AC11 MET for the slice; AC4 is MET in-process
  only (N1/N2 are the production-coherence caveats the artifact itself
  records). GJS bundle claims independently reproduced.

## Follow-ups

1. Land a production host for the resident capture job and the
   out-of-process `Control` channel (5‑4 follow-ups 1/3).
2. Make `Control` fail loud when no job is co-hosted (N2) or document the
   no-op semantics.
3. Extend the bar to `(epoch, seq)` hydration/stale-drop (N3) and bring the
   ICME GJS file into the drift scan (N7).
