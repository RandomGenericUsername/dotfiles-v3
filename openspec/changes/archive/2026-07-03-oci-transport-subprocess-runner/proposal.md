## Why

B8 found that `_SubprocessRunner` is entangled with `_CancelContext` and `_AsyncStreamReader` inside the Lima adapter (`_transport_lima.py:400-580`). It cannot be unit-tested, reused by Docker, or audited for thread safety. B9 identified that the cancellation context has no broadcast mechanism and the stream reader blocks on `readline()` with no timeout.

B8/B9 extract `_SubprocessRunner`, `_CancelContext`, and `_AsyncStreamReader` into dedicated adapter-level modules under `adapters/transport/`. This is NOT a domain relocation — these are OS-process primitives with subprocess dependencies (adapter concern).

## What Changes

- Create `adapters/transport/__init__.py`, `adapters/transport/runner.py`, `adapters/transport/cancel.py`, `adapters/transport/stream.py`.
- Extract each class into its own module with full type annotations.
- Lima adapter imports from `oci_runtime.adapters.transport.*` instead of defining inline.
- Add thread-safety improvements: `_CancelContext` uses `threading.Event` broadcast; `_AsyncStreamReader` supports timeout.

## Capabilities

### New Capabilities

- `oci-transport-subprocess-runner`: `_SubprocessRunner`, `_CancelContext`, `_AsyncStreamReader` SHALL live in `adapters/transport/` as extracted, importable modules.

### Modified Capabilities

- `oci-pty-timeout`: cancellation SHALL use `threading.Event` broadcast; stream reader SHALL support timeout.

## Impact

- **Code**: 4 new files (~250 LOC extracted), Lima adapter shortened.
- **Tests**: new transport unit tests.
- **Risk**: medium — extraction changes import paths; functional behavior preserved.