## Context

v4 A4 closed the auth-error context gap but left the not-found path dropping context. The `*NotFoundError` family only takes entity id; the `ProviderNotRegisteredError` uses a constructor-time import hack.

## Goals / Non-Goals

**Goals:** All `OciError` subclasses carry the same diagnostic context. `ProviderNotRegisteredError.kind` is typed.
**Non-Goals:** Changing positional call conventions (keyword-only additions preserve existing callers).

## Decisions

Keyword-only `command`/`exit_code`/`stderr` on `*NotFoundError` — mirror `ImagePullAccessDeniedError`. `super().__init__(f"...", command=command, exit_code=exit_code, stderr=stderr)`. Top-level `RuntimeKind` import: verified no cycle (`enums.py` imports nothing from `exceptions`).

## Risks / Trade-offs

- None. Keyword-only means `ContainerNotFoundError("abc")` still works.