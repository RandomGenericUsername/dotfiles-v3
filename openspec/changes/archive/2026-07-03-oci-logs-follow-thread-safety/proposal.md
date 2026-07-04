## Why

`logs --follow` spawns a background thread for streaming. The thread reads from `proc.stdout` with no timeout and no coordination with the main thread on teardown. Under high log volume, the thread can outlive the request context, causing resource leaks or use-after-free on `proc`.

B6 converts the background thread to use `_AsyncStreamReader` (extracted in B8/B9) with timeout support and coordinated teardown via `_CancelContext`.

## What Changes

- Replace raw-thread `logs --follow` implementation with `_AsyncStreamReader` + `_CancelContext`.
- Add `timeout` parameter to `logs` — stream reader yields partial data on timeout.
- Thread teardown coordinated via cancel context broadcast.

## Capabilities

### New Capabilities

- `oci-logs-follow-thread-safety`: `logs --follow` SHALL use `_AsyncStreamReader` with timeout and `_CancelContext` for coordinated teardown.

## Impact

- **Code**: `adapters/managers/container.py` (rewrite `logs` follow path).
- **Tests**: add thread-safety tests for logs follow.
- **Risk**: medium — threaded code is hard to test; timeout changes observable behavior.