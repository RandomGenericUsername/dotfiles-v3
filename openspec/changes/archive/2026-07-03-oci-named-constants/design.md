## Context

Magic numbers scattered across transport, managers, and pipe-reader. Per-module constants are the right granularity (B14 resolution: no central constants module — would create cross-layer coupling).

## Goals / Non-Goals

**Goals:** Replace inlined numbers with named module-level constants.
**Non-Goals:** A central `constants.py` module (cross-layer coupling anti-pattern).

## Decisions

- `cli.py`: `_STDIN_JOIN_TIMEOUT = 5.0` (replaces `timeout=5` at `:129`).
- `streaming.py`: `_STDIN_JOIN_TIMEOUT = 5.0` (replaces `timeout=5` at `:84,94`).
- `container.py`: `_DEFAULT_STOP_TIMEOUT_SECONDS = 10` (replaces `"10"` at `:213,226`). Note: the actual `"-t"` value rendering is handled by `oci-timeout-precision` via `cli_seconds(timeout, default=_DEFAULT_STOP_TIMEOUT_SECONDS)`. This change just names the default.
- `pipe_reader.py`: `_READ_CHUNK = 4096` (replaces `4096` at `:56`).

## Risks / Trade-offs

- Naming collision if other modules also define `_STDIN_JOIN_TIMEOUT` — mitigated by per-module prefix (modules are different files; no conflict).