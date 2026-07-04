## Context

`container.py` renders Docker CLI `-t` (timeout) values as `str(int(timeout))`, truncating fractional seconds toward zero. This under-applies the user's requested shutdown grace period.

## Goals / Non-Goals

**Goals:** `ceil()`-based rendering so fractional timeouts round up to the next whole second. Integer values pass through unchanged.
**Non-Goals:** changing `RunConfig.timeout` semantics (that's the overall operation timeout, not the CLI `-t` flag).

## Decisions

Use `math.ceil` in a dedicated `adapters/managers/_timeouts.py` helper. Per-module constant, not a central constants module (avoids cross-layer coupling per B14 resolution). `math.ceil(1.0) == 1`, `math.ceil(1.9) == 2` — no off-by-one for integer values.

## Risks / Trade-offs

- Existing tests monkeypatching `str(int(timeout))` will break — update them in the same commit.