## Context

Review found uncovered branches. Test-only.

## Goals / Non-Goals

**Goals:** Cover filter branches, builder map fallthrough, empty response, error propagation.
**Non-Goals:** Refactoring UnixListExecutor.

## Decisions

Use `mock.patch` to inject controlled responses for each filter variant and error path.

## Risks / Trade-offs

- None.