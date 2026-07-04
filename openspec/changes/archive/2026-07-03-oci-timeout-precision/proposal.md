## Why

`container.py:213,226` uses `str(int(timeout))` which truncates fractional timeouts toward zero. `stop(timeout=1.9)` produces `"1"`, so Docker waits 1s instead of 2s — under-kills the container relative to the user's intent. Same for `restart`.

## What Changes

- Add `adapters/managers/_timeouts.py` with `cli_seconds(timeout: float | None, default: int) -> str` using `math.ceil`.
- Replace both `str(int(timeout))` call sites in `container.py:213,226` with `cli_seconds(timeout, default=10)`.

## Capabilities

### New Capabilities

- `oci-timeout-precision`: CLI `-t` values SHALL be rendered via `ceil()` so fractional timeouts are never under-applied.

## Impact

- **Code**: new `adapters/managers/_timeouts.py` (~10 LOC), two call-site edits in `container.py`.
- **Tests**: unit tests for `cli_seconds`: `1.9→"2"`, `1.0→"1"`, `1.01→"2"`, `None→"10"`, `0.5→"1"`.
- **Risk**: none — integer values pass through unchanged; fractional values round up.