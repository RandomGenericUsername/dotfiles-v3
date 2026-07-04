## Context

Opaque factory, untyped runtime config dict, no validation before construction. Builder pattern is the standard Python solution.

## Goals / Non-Goals

**Goals:** Builder with typed chainable methods, resolved config as public dataclass, OciRuntime accepts resolved config.
**Non-Goals:** Overriding local config file loading (builder wraps it).

## Decisions

`OciRuntimeBuilder` stores overrides as `dict[str, Any]`. `build()` validates, resolves defaults, returns `(OciRuntime, ResolvedRuntimeFactoryConfig)`. `ResolvedRuntimeFactoryConfig` is a `@dataclass(frozen=True)` with all runtime params as typed fields.

## Risks / Trade-offs

- Public API break for direct `OciRuntime(config=...)` callers. Acceptable per A5 decision.