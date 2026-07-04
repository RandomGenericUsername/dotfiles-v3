## Why

Magic numbers embedded in code make behavior opaque at the call site and make global changes require editing every site: 5s stdin join (`cli.py:129`, `streaming.py:84,94`), 10s default stop/restart timeout (`container.py:213,226`), 4096 read chunk size (`ports/pipe_reader.py:56`). No constants module exists.

## What Changes

- Introduce per-module named constants replacing each magic number. No central constants module (would create cross-layer coupling).

## Capabilities

### New Capabilities

- `oci-named-constants`: per-module named constants SHALL replace inlined magic numbers in transport, manager, and pipe-reader code.

## Impact

- **Code**: `_STDIN_JOIN_TIMEOUT = 5.0` in `cli.py`/`streaming.py`, `_DEFAULT_STOP_TIMEOUT_SECONDS = 10` in `container.py`, `_READ_CHUNK = 4096` in `pipe_reader.py`, `_KILL_GRACE_SECONDS = 5.0` (used by transport extraction, but applicable here as a named constant).
- **Tests**: verify constants exist and are used at call sites.
- **Risk**: none — values unchanged, only names added.