# Gate 2 Review — P5‑1‑2b‑ii‑a (Hub Event Surface: Emit / Validation / Topic Store + GetTopicState)

Verdict: **CHANGES-REQUIRED** — one blocking finding (wire-reachable
heterogeneous-array payload escapes validation and then crashes the
signal drain). Everything else is sound.

Reviewed at commit `b1674aa` (working tree clean). Story artifact:
`p5-1-2b-ii-a-hub-event-surface-emit.md` (committed in `b1674aa`, still
marked "draft (Gate‑1 ballot pending)"; lines 163‑196 tasks unchecked).

## Verification (executed by reviewer, not taken on faith)

| Check | Result |
| --- | --- |
| `uv run --directory src/runtime pytest -q` | **1372 passed, 2 skipped** (matches commit claim) |
| `uv run --directory src/runtime pytest tests/architecture/test_layering.py -q` | **100 passed** |
| `make contracts-check` | **22 passed** (now includes the drift gate) |
| `uv run --directory src/runtime ruff check src` | 3 errors, all pre-existing/unrelated: 2× B008 `cli/main.py`, 1× E501 `domain/models.py` (confirmed present at baseline `2681e97`) |
| `uv run --directory src/runtime mypy src` | 6 errors, all pre-existing (the `sections` no-redef in `cli/main.py` is untouched by `b1674aa`) |
| `git diff HEAD -- contracts/` | empty; `contracts/` clean |

Claimed deliverables are present and functionally exercised:
`EventHub.emit`/`topic_state` (`domain/hub.py:314`, `:350`),
`EmitValidator` (`adapters/emit_validation.py`), `METHODS +=
Emit/GetTopicState` (`adapters/dbus_event_bus.py:126‑127`),
`IEventPublisher.publish` binding (`adapters/dbus_event_bus.py:451`),
topics/method conformance (`tests/unit/test_dbus_conformance.py:120‑171`),
rate limiter (`emit_validation.py:167‑197`).

## Findings

### Blocking

**B1 — Heterogeneous arrays pass structural validation and then crash
`signal_for`, losing queued signals and turning a successful `Emit` into a
`Failed` reply.**

- `EmitValidator.validate` calls `_check_sv_compatible`, which for a list
  recurses into each element but **never checks element-type homogeneity**
  (`emit_validation.py:152‑157`). Homogeneity is required by the D-Bus wire
  (`a<elem>` has one element signature).
- `signal_for` → `_wrap_value` → `_variant_sig` **raises**
  `RuntimeError("heterogeneous array has no element type")` on exactly that
  shape (`dbus_event_bus.py:253‑257`).
- `_drain_signals` calls `signal_for(event)` **outside** the emission
  try/except (`dbus_event_bus.py:574`), despite its docstring asserting
  "never raises (sink-must-not-raise)" (`dbus_event_bus.py:563‑565`).
  `dispatch` and `publish` invoke it from a `finally`
  (`dbus_event_bus.py:560‑561`, `:464‑465`), so the `RuntimeError` replaces
  the method's return and propagates to `_answer`, which maps it to
  `org.freedesktop.DBus.Error.Failed`.

Proof by execution (reviewer):

```
service.dispatch("Emit", ("icme.saved", {"path":"/a","future":[1,"two"]}), ":1.5")
# -> dispatch RAISED: RuntimeError heterogeneous array has no element type
# -> topic_state shows the emit WAS stored at seq=1 (mutation happened)
# -> emitted signals: only JobsCleared; no DomainEvent
# -> sink queue left empty (drained then aborted mid-loop: other queued records lost)
```

Wire reachability (reviewer, executed): a variant inside `a{sv}` may carry
signature `av`; jeepney decodes it to `[('i',1),('s','two')]` and
`_decode_in_args` → `_unwrap_value` flattens it to the plain
**heterogeneous** list `[1, 'two']` (`dbus_event_bus.py:218‑233`,
`:272‑280`). That payload then clears `_check_sv_compatible`. So a
same-user client can trigger this; it is not limited to in-process callers.

Impact: violates two stated invariants — "validation before mutation"
(the emit is stored and its `seq` consumed even though the call fails) and
"sink/drain must not raise"; a single crafted payload drops every other
record queued in the same drain window (lifecycle signals included).

Fix direction (either side closes it): reject heterogeneous arrays (and
other non-marshallable shapes) as `PayloadTooLarge` in
`_check_sv_compatible`; and/or wrap the `signal_for` call in
`_drain_signals` so one unmappable record cannot abort the drain. The
existing test corpus does not cover this (`test_emit_validation.py:136‑139`
samples `bytes/None/tuple/nested-bytes/empty-list/int64-overflow` but not a
heterogeneous array; `test_dbus_dispatch.py:244‑259` uses only well-typed
payloads).

### Non-blocking

- **N1 — the ii‑a artifact is now committed but still says "draft
  (Gate‑1 ballot pending)" and all Tasks/Subtasks boxes are unchecked**
  (`p5-1-2b-ii-a-hub-event-surface-emit.md:3`, `:163‑196`). The code is
  present and tested. Bookkeeping only; corrected for the status line in
  this pass (see `phase5-status-summary.md`).
- **N2 — `_check_sv_compatible` accepts `tuple`-typed content only after
  the adapter unwraps it.** In-process callers that pass a literal tuple
  value reach `_variant_sig` and raise there rather than at validation
  (`emit_validation.py:164` only rejects unknown types, not tuples; the
  adapter's `_unwrap_value` never sees in-process tuples). Same class as
  B1; fix together.
- **N3 — `EmitRateLimiter` state is not reset on `HubService.restart()`.**
  The validator lives on the service while the registry is rebuilt
  (`dbus_event_bus.py:500‑515`). Rate quota persists across an epoch bump,
  which is defensible (anti-abuse) but undocumented. Low.
- **N4 — the in-process vs wire sender split relies on the literal
  `"(local)"`** (`hub.py:314`, `dbus_event_bus.py:451‑465`); a caller can
  pass `producer="(local)"` on the wire only via validation (it is a plain
  string) but `producer` is never used for identity, so no impact.

## Panel notes

- Blind Hunter (correctness): B1, N2, N3. No other correctness defects found
  in emit/store/seq/hydration.
- Edge Hunter (edges): B1 is the reproduced edge; also checked `_seq`
  reset-on-epoch, reserved-key rejection (`emit_validation.py:221‑223`),
  int64 boundaries (`:145`), non-finite floats (`:148‑150`), empty arrays
  (rejected), and `GetTopicState` never-emitted sentinel
  (`hub.py:361‑363`) — all correct.
- Acceptance Auditor: AC1/2/4/5/6/7/8/9/10 MET by code + tests; AC3 MET for
  the three contract topics but **the sv-compatibility sub-check is
  incomplete** (B1); AC11 PARTIAL (artifact status/tasks stale, N1).

## Claims I could not verify

- "Live re-smoke green" from the 2b‑i review is not re-run here; no live
  session bus was exercised. The hermetic dispatch/owner tests
  (`test_dbus_dispatch.py:616‑836`) cover the wire codec by round-trip.
