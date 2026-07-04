## Context

Detach mode raises RuntimeError. User wants streaming startup output + parsed container id. The v3 async complexity is unnecessary — synchronous `subprocess.run` with stdout capture suffices.

## Goals / Non-Goals

**Goals:** `detach` streams stdout, returns `ContainerId`.
**Non-Goals:** Async implementation.

## Decisions

Rewrite `detach` as: `result = subprocess.run(cmd, capture_output=True, text=True, timeout=...); stdout = result.stdout; cid = parse_container_id(stdout); return cid`. Parse container id from first line matching `[0-9a-f]{64}` or similar.

## Risks / Trade-offs

- API break: existing callers catching `RuntimeError("already running")` will break. Acceptable per B5 decision.