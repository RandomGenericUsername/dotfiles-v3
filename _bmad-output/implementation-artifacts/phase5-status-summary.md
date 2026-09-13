# Phase 5 — Status Summary (Gate‑2 + bookkeeping pass)

Date: 2026‑09‑13 · HEAD: `b1674aa` · Reviewer pass — no source/tests/
contracts/Makefile touched by this pass.

> **Concurrency caveat.** The tree was clean at `b1674aa` when this review
> began and when the test runs below were executed. Partway through, a
> concurrent P5‑1‑4 workstream began writing into the tree (see "What
> remains"). All verification here reflects `b1674aa`; the current working
> tree is no longer clean and was not re-verified.

## Committed

| Slice | Commit | Evidence |
| --- | --- | --- |
| P5‑1‑1 daemon run skeleton + supervised unit | `5e06485` | prior Gate‑2 `p5-1-1-...-gate2-review.md` (APPLIED) |
| P5‑1‑2a hub domain core (registry/leases/epoch) | `a82eb73` | prior Gate‑2 `p5-1-2a-...-gate2-review.md` (APPLIED) |
| P5‑1‑2b‑i hub wire dispatch (job surface) | `2681e97` | prior Gate‑2 `p5-1-2b-i-...-gate2-review.md` (APPLIED) |
| P5‑1‑2b‑ii‑a Emit / validation / topic store+seq / GetTopicState | `b1674aa` | 1372 passed / 2 skipped |
| P5‑1‑2b‑ii‑b 5 signals + JobsCleared + restart | `b1674aa` | same commit; `TestSignalEmission` |
| Epic 5‑2 bar consumer binding + per-language drift gate | `b1674aa` | bar 29 + drift 7; `make contracts-check` 22 |
| Epic 5‑3 inotify watch + reactive converge + backstop + desired relocation (lands P5‑1‑3) | `b1674aa` | scoped suites green; live inotify 3 |
| Epic 5‑4 capture/speedtest/indicator/icme + control fan-out (first slice) | `b1674aa` | 47 job/runtime tests; `ags bundle` exit 0 (bar + ICME, re-run) |
| R‑1..R‑5 prerequisite remediation | `eac14b7`, `01a5e94`, `34721ba`, `39aab69`, `6ac38c5` | prior Gate‑2 reviews (APPLIED) |

Independent re-verification at `b1674aa`: full runtime suite **1372 passed,
2 skipped**; layering **100 passed**; `make contracts-check` **22 passed**;
`contracts/` diff empty; ruff 3 pre-existing/unrelated (2× B008 in
`cli/main.py`, 1× E501 in `domain/models.py`); mypy 6 pre-existing;
`ags bundle` (bar and ICME) and ICME node tests green.

## Gate‑2 verdicts

| Artifact | Verdict | Notes |
| --- | --- | --- |
| `p5-1-2b-ii-a-hub-event-surface-emit-gate2-review.md` | **CHANGES-REQUIRED** | 1 blocking finding (B1) |
| `p5-1-2b-ii-b-signal-emission-restart-gate2-review.md` | **CHANGES-REQUIRED** | same B1 (drain invariant) |
| `epic5-2-bar-consumer-binding-gate2-review.md` | **APPROVED-WITH-FOLLOWUPS** | shipped GJS bar lacks hydration/stale-drop; drift-scan scope |
| `epic5-3-watch-reactive-gate2-review.md` | **APPROVED-WITH-FOLLOWUPS** | auto-prune on reactive converge; observe-only shipping; symlink asymmetry |
| `epic5-4-shell-reactivity-gate2-review.md` | **APPROVED-WITH-FOLLOWUPS** | job layer not production-hosted; `Control` succeeds with no consumer |

Sprint-status records `done` for the committed stories (land state); the
two **CHANGES-REQUIRED** verdicts are called out inline in
`sprint-status.yaml` and must be closed before Phase 5 sign-off.

## Blocking finding (B1) — affects P5‑1‑2b‑ii‑a and ii‑b

A heterogeneous array reaches `EmitValidator` and passes `_check_sv_compatible`
(`src/runtime/src/runtime/adapters/emit_validation.py:152-157`, no element-type
homogeneity check). `signal_for` → `_variant_sig` then raises
(`.../adapters/dbus_event_bus.py:253-257`), and `_drain_signals` calls
`signal_for` outside its try/except (`:574`) despite promising "never raises"
(`:563-565`). Because `drain()` clears the queue first (`:359-364`), one bad
payload drops every other record in the window and the exception escapes the
`finally` in `dispatch`/`publish` (`:560`, `:464`), surfacing as a `Failed`
reply.

Wire-reachable, reproduced by the reviewer: an `av` variant inside `a{sv}`
decodes to `[('i',1),('s','two')]`, which `_unwrap_value`
(`dbus_event_bus.py:218-233`, `:272-280`) flattens to the heterogeneous list
`[1,'two']`. Executing the hub path showed the emit stored at `seq=1`, no
`DomainEvent` emitted, the queued records lost, and a raised
`RuntimeError`. Fix in `_check_sv_compatible` and/or guard the mapping in
`_drain_signals`; add a regression test.

## What remains

- **P5‑1‑4 (status surface).** Owned by another agent. During this review a
  concurrent workstream landed an uncommitted artifact
  (`p5-1-4-status-kill-switch-audit.md`, which claims "done") plus
  `src/runtime/src/runtime/adapters/daemon_status.py`,
  `tests/unit/test_cli_inspect_daemon.py`, and edits to `cli/main.py` /
  `converge_backstop.py`. Not reviewed or verified here; recorded
  `in-progress` in sprint-status. `LastConvergedBackstop.read_record`
  anticipates the status surface (`.../adapters/converge_backstop.py:15-17`).
- **B1 fix + regression test** (blocking; owns ii‑a/ii‑b).
- **Epic 5‑4 production coherence:** out-of-process `Control` channel,
  daemon-hosted job runner, `Control` failure when no consumer, GJS bar
  `(epoch,seq)` hydration/stale-drop, ICME file in the drift scan.
- **Epic 5‑3:** unit `--activate` + `WatchdogSec`/`sd_notify`; decide the
  reactive auto-prune policy.
- **Epic 5‑2:** fix stale artifact status; extend drift scan.

## Bookkeeping corrections / discrepancies

- **Fixed:** `p5-1-2b-ii-a-hub-event-surface-emit.md` status changed from
  "draft (Gate‑1 ballot pending)" to "done — implemented and committed in
  `b1674aa`", with the applied Gate‑1 rulings and the Gate‑2 verdict noted.
  (The brief described this file as "uncommitted"; it is in fact committed
  in `b1674aa`.)
- **Noted, not edited:** the Epic 5‑2/5‑3/5‑4 artifacts each say "nothing
  committed" and the 5‑2 artifact reports a red full suite from a concurrent
  workstream. All are committed in `b1674aa` and the full suite is green.
- `p5-remediation` updated `in-progress` → `done` (R‑1..R‑5 commits).
- `sprint-status.yaml` `last_updated` refreshed.
