# Gate 2 Review — P5‑1‑2b‑ii‑b (Bus Signal Emission + JobsCleared/Restart)

Verdict: **CHANGES-REQUIRED** — one blocking finding, shared with the
ii‑a review (the drain can raise on a wire-reachable payload). The signal /
restart slice itself is otherwise correct and well-tested.

No standalone story artifact exists for ii‑b; its scope is defined in
`p5-1-2b-ii-a-hub-event-surface-emit.md:50‑56` and Gate‑1 Q7/Q8
(`:301‑320`). Implemented in `b1674aa` (working tree clean at HEAD).

## Verification (executed by reviewer)

| Check | Result |
| --- | --- |
| Full runtime suite | **1372 passed, 2 skipped** |
| `tests/unit/test_dbus_dispatch.py` `TestSignalEmission` + `TestOwnerServeLoop` + `TestWireCodecRoundTrip` | green (incl. real jeepney `Message.serialise`/`from_buffer` round-trips) |
| `tests/unit/test_dbus_conformance.py::test_adapter_signals_*` / `test_signals_are_bound` | green |
| Layering / `make contracts-check` | 100 passed / 22 passed |

Verified behaviours (code + tests):

- All five contract signals are emitted from sink records and pinned to
  `contracts/event-contract.xml|json`: `SIGNALS` (`dbus_event_bus.py:134‑146`),
  `signal_for` (`:376‑401`), conformance
  (`test_dbus_conformance.py:154‑178`).
- Ordering/queue-then-emit: `SignalSink` append-only (`:333‑373`); drains
  occur **after** the registry call and **outside** the dispatcher lock
  (`:557‑561`, `:563‑584`).
- `JobsCleared` first on start (`acquire` flush, `:746‑747`) and on restart
  (`restart`, `:500‑515`); tested at `test_dbus_dispatch.py:355‑358`,
  `:433‑439`, `:739‑772`.
- Synthetic lease expiry → `JobFinished(exit_code=-1)`
  (`hub.py:390‑410` → `signal_for`), tested at `test_dbus_dispatch.py:389‑396`.
- `job_adopted` / `pid` dropped on the wire (`:398‑407`), tested at `:398‑407`.
- `NameOwnerChanged` → restart only for our well-known name and only on
  gain (loss left to the supervisor) (`:517‑532`, `:800‑814`), tested at
  `:441‑449`.
- Emitter failure contained; `OSError` (bus death) stops the loop
  (`:576‑584`, `:816‑829`), tested at `:419‑431`.
- Restart path is live in production: `cli/main.py:1223‑1233` passes a
  `registry_factory` that rebuilds the hub on the same `SignalSink`.

## Findings

### Blocking

**B1 (shared with ii‑a) — `_drain_signals` is not non-raising;
`signal_for` can raise for a validator-accepted payload and abort the
drain.** `_drain_signals` calls `signal_for(event)` outside the
emission try/except (`dbus_event_bus.py:574`), while its docstring asserts
"never raises (sink-must-not-raise)" (`:563‑565`). A wire client can send an
`av` variant inside `a{sv}`; `_decode_in_args`/`_unwrap_value` flatten it to
a heterogeneous Python list (`:218‑233`, `:272‑280`), the validator accepts
it (`emit_validation.py:152‑157`), and `_variant_sig` then raises
(`dbus_event_bus.py:253‑257`). Since `drain()` clears the queue first
(`:359‑364`), every record in the same window is lost (not only the bad
one), and the exception escapes the `finally` in `dispatch`/`publish`,
becoming a `Failed` reply. Reproduced by execution (see ii‑a review B1).
Fix belongs either in `_check_sv_compatible` (reject non-marshallable
arrays) or in `_drain_signals` (guard the mapping and keep draining) — the
review recommends both, with a regression test.

### Non-blocking

- **N1 — `HubService.restart()` requires a `registry_factory`; tests that
  inject a bare `registry` get `registry_factory=None` and `restart()`
  raises** (`dbus_event_bus.py:508‑510`). Contained by the serve loop
  (`:788‑791`), and the daemon always supplies one
  (`cli/main.py:1229`), but the fallback is a silent
  no-restart-plus-log rather than an explicit failure. Low.
- **N2 — rate-limiter state survives a restart** (`HubService._validator`
  is not rebuilt with the registry, `:500‑515`). Defensible as anti-abuse;
  undocumented. Low.
- **N3 — `release()` frees the name by closing the connection rather than
  an explicit `ReleaseName`** (`:751‑760`). Closing is sufficient for the
  bus to drop ownership, and the 2b‑i review already blessed the
  close-on-release path. Informational.
- **N4 — emission ordering for a burst relies on the single serve thread
  plus the per-call drain**; a future in-process `publish` from another
  thread is explicitly unsupported (`:688‑691`). Documented; no action.
- **N5 — no live session-bus smoke test is committed** (the 2b‑i live
  smoke was manual and deleted). Coverage rests on scripted fakes +
  jeepney serialise/parse round-trips (`test_dbus_dispatch.py:463‑491`,
  `:792‑836`). Reasonable for hermetic CI; a gated live test would be
  stronger.

## Panel notes

- Blind Hunter: B1, N1–N3. The signal-body construction and the
  `a{sv}` codec were re-derived against jeepney and round-tripped.
- Edge Hunter: checked empty/None emitter, dead-bus `OSError`, re-acquire
  after release (`:640‑664`), double acquire (`:774‑785`), foreign
  interface on our path (`:666‑696`), arity/shape mismatches — all handled.
- Acceptance Auditor: all ii‑b scope items are MET; the only gap is B1's
  non-raising-drain invariant (AC8/drain precondition from 2b‑i Gate‑2).

## Verdict rationale

The signal/restart machinery is complete, correctly ordered, and
conformance-pinned. It is blocked only by B1, which is a
robustness/correctness violation of an explicitly documented invariant and
is reachable from the wire. Both ii‑a and ii‑b own half of the fix.
