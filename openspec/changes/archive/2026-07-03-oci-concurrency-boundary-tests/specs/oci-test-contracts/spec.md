## MODIFIED Requirements

### Requirement: Transport concurrency tests

Concurrency tests SHALL cover: `_SubprocessRunner` invoked from multiple threads concurrently, `_CancelContext` broadcasting cancellation to multiple waiters, `_AsyncStreamReader` reading with timeout (data available, timeout expires, stream closes mid-read).

#### Scenario: CancelContext broadcasts to all waiters
- **WHEN** `_CancelContext.cancel()` is called while 3 threads are waiting on `.wait()`
- **THEN** all 3 threads return from `.wait()` within 100ms

#### Scenario: AsyncStreamReader timeout yields partial data
- **WHEN** a 500ms read is requested with 200ms timeout on a 300ms delayed stream
- **THEN** the reader yields data read up to the timeout point