## MODIFIED Requirements

### Requirement: OciRuntime constructed via builder

`OciRuntime` SHALL be constructed via `OciRuntimeBuilder`, not by passing a `dict[str, Any] | None` to `__init__`. The builder SHALL expose chainable methods: `.with_timeout(seconds: float)`, `.with_pty_mode(mode: PtyMode)`, `.with_logs_follow(follow: bool)`, `.with_runtime_kind(kind: RuntimeKind)`, etc. `build()` SHALL return `tuple[OciRuntime, ResolvedRuntimeFactoryConfig]` where `ResolvedRuntimeFactoryConfig` is a frozen dataclass with all resolved values typed. Direct `OciRuntime(config={...})` construction SHALL be removed.

#### Scenario: Builder returns typed resolved config
- **WHEN** `OciRuntimeBuilder().with_timeout(30.0).build()` is called
- **THEN** the returned `ResolvedRuntimeFactoryConfig` has `.timeout == 30.0`

#### Scenario: OciRuntime rejects dict config
- **WHEN** `OciRuntime(config={"timeout": 30})` is called
- **THEN** `TypeError` is raised (config param removed)