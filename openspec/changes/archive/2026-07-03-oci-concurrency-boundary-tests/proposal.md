## Why

No tests for concurrency safety: `_SubprocessRunner` (thread-safety), `_CancelContext` (cancellation propagation), `_AsyncStreamReader` (concurrent read/write). These are the core of the B8/B9 transport layer.

## What Changes

- Add `tests/unit/adapters/test_transport_concurrency.py` with thread-safety tests for subprocess runner, cancellation context, and async stream reader.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: transport concurrency primitives SHALL have thread-safety tests.

## Impact

- **Code**: none.
- **Tests**: new test file, ~80 LOC.