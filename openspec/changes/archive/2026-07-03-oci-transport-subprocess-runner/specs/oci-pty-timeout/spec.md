## MODIFIED Requirements

### Requirement: CancelContext uses Event broadcast

`_CancelContext.cancel()` SHALL use `threading.Event.set()` for broadcast (not a single-waiter flag). All threads waiting on `.wait()` SHALL be notified on cancel.

### Requirement: AsyncStreamReader supports timeout

`_AsyncStreamReader.read()` SHALL accept a `timeout: float | None` parameter. When timeout expires before the stream produces data, the reader SHALL yield whatever data has been accumulated so far (partial read).

#### Scenario: Cancel notifies all waiters
- **WHEN** 3 threads are blocked on `cancel_ctx.wait()` and `cancel_ctx.cancel()` is called
- **THEN** all 3 threads unblock within 100ms

#### Scenario: Stream read with timeout yields partial data
- **WHEN** `reader.read(timeout=0.1)` is called on a stream that produces data after 500ms
- **THEN** the reader returns whatever data is available at 100ms (possibly empty bytes)