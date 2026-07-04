## Context

Edge cases uncovered during code review. All test-only, no code changes.

## Goals / Non-Goals

**Goals:** Cover empty PATH component, trailing separator, multi-candidate resolution, Windows PATHEXT (skip on non-Windows).
**Non-Goals:** Refactoring BinaryResolver.

## Decisions

Test each edge case with `monkeypatch` on `os.environ["PATH"]` and `os.environ.get("PATHEXT", "")`.

## Risks / Trade-offs

- None.