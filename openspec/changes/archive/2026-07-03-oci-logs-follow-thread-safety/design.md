## Context

logs --follow uses raw thread with no coordination. Convert to use extracted transport primitives.

## Goals / Non-Goals

**Goals:** Use _AsyncStreamReader + _CancelContext for logs --follow.
**Non-Goals:** Changing log output format.

## Decisions

Replace `threading.Thread(target=...proc.stdout.readline...)` with `_AsyncStreamReader(proc.stdout, timeout=...)` driven by `_CancelContext`. On timeout, yield partial data. On cancel, close stream.

## Risks / Trade-offs

- Thread safety is inherently hard to test. Acceptable trade-off.