## Why

`DefaultRuntimeFactory` (v4) takes optional overrides with default-`None` params; callers don't know what defaults are used. `ResolvedRuntimeFactoryConfig` is internal and never exposed. The `OciRuntime` constructor signature (`config: dict[str, Any] | None = None`) is a type-unsafe blob.

Change A5 replaces the opaque factory with a builder pattern. The builder validates and resolves everything before construction, then exposes the resolved config as a public dataclass (`ResolvedRuntimeFactoryConfig`). `OciRuntime.__init__` takes the resolved config instead of a dict.

## What Changes

- Add `class OciRuntimeBuilder` with chainable `.with_timeout(...)`, `.with_pty_mode(...)`, `.with_logs_follow(...)`, etc.
- `build()` returns a tuple `(OciRuntime, ResolvedRuntimeFactoryConfig)`.
- `ResolvedRuntimeFactoryConfig` is a public dataclass with all resolved values.
- `OciRuntime.__init__` takes `ResolvedRuntimeFactoryConfig`, not `dict[str, Any] | None`.

## Capabilities

### Modified Capabilities

- `oci-strict-hexagonal-layering`: `OciRuntime` SHALL accept `ResolvedRuntimeFactoryConfig`; a builder SHALL provide the construction path.

## Impact

- **Code**: `ports/runtime.py`, `domain/runtime.py`, `domain/factory.py` — rewrite construction.
- **Tests**: update all `OciRuntime` instantiations (in tests) to use builder.
- **Risk**: high — API break for any external caller constructing `OciRuntime` directly.