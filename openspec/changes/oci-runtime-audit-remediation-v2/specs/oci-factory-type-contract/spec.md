## ADDED Requirements

### Requirement: RuntimeFactoryConfig callable annotations match call-site signatures

`RuntimeFactoryConfig` field type annotations SHALL match the actual call-site contract. `transport_factory` and `streaming_transport_factory` SHALL be annotated as `Callable[[str, BinaryResolver], Transport]` and `Callable[[str, BinaryResolver], StreamingTransport]` respectively, matching the call sites (`factory.create()` passes `binary_resolver=` kwarg), the default factory implementations, and the `ARCHITECTURE.md` documentation.

#### Scenario: Default transport factory accepts BinaryResolver
- **WHEN** `RuntimeFactoryConfig()` is used with defaults and `factory.create(preference)` is called
- **THEN** the default transport factory receives both `binary` (str) and `binary_resolver` (BinaryResolver) arguments

#### Scenario: Custom factory matching the annotation works
- **WHEN** `RuntimeFactoryConfig(transport_factory=lambda binary, binary_resolver: CustomTransport(binary, binary_resolver))` is used
- **THEN** `factory.create(preference)` succeeds and the custom transport is wired with the resolver

#### Scenario: Single-arg factory fails at runtime
- **WHEN** `RuntimeFactoryConfig(transport_factory=lambda binary: CustomTransport(binary))` is used and `factory.create(preference)` is called
- **THEN** `TypeError` is raised (missing `binary_resolver` keyword argument), because the factory calls it with `binary_resolver=`

### Requirement: timeout type is unified to float across all transports and managers

All `timeout` parameters in `Transport.execute()`, `StreamingTransport.stream()`, `PtyTransport.execute_pty()`, `ImageManager.build/pull/push()`, `ContainerManager.stop/restart/exec_container()`, and `RunConfig.timeout` SHALL be typed as `float | None` (or `float` with a default for methods that always have a timeout). This matches `DeadlineCancellationToken.__init__(timeout: float)`.

#### Scenario: RunConfig.timeout (float) passes to stream (float)
- **WHEN** `RunConfig(timeout=1.5)` is used and `run()` calls `streaming.stream(cmd, timeout=config.timeout)`
- **THEN** no type mismatch occurs (both are `float | None`)
