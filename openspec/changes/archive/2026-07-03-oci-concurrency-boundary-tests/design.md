## Context

No concurrency tests exist. Transport primitives are exercised only via integration tests.

## Goals / Non-Goals

**Goals:** Thread-safety tests for SubprocessRunner, CancelContext, AsyncStreamReader.
**Non-Goals:** Stress/race-condition detection (limited by pytest).

## Decisions

Use `threading.Thread` + `queue.Queue` for concurrent access patterns. Mock subprocess.Popen for SubprocessRunner.

## Risks / Trade-offs

- Tests may be flaky under CI load. Acceptable for now.