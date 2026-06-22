## ADDED Requirements

### Requirement: Factory is the sole composition root for adapter instantiation

`RuntimeFactory` SHALL be the only place where manager, transport, engine, discovery, and infrastructure adapter classes are instantiated. `RuntimeProvider` SHALL NOT implement `create_managers()`. The provider port SHALL expose only `kind`, `capabilities()`, and `create_parsers()`. Provider subclasses reference only parser adapter classes (the one genuinely runtime-specific piece — different JSON shapes per runtime).

#### Scenario: Factory creates managers directly
- **WHEN** `RuntimeFactory.create(preference)` is called
- **THEN** the factory instantiates `CliContainerManager`, `CliImageManager`, `CliVolumeManager`, and `CliNetworkManager` using the resolved config and the parsers from `provider.create_parsers()`

#### Scenario: RuntimeProvider port has no create_managers
- **WHEN** a custom `RuntimeProvider` subclass is defined
- **THEN** it SHALL implement `kind`, `capabilities()`, and `create_parsers()` only — `create_managers()` is not part of the port

#### Scenario: Factory config allows manager class injection
- **WHEN** `RuntimeFactoryConfig(container_manager_cls=CustomManager)` is passed
- **THEN** the factory uses `CustomManager` instead of the default `CliContainerManager`

#### Scenario: Adding a new runtime requires no manager wiring
- **WHEN** a `NerdctlRuntimeProvider` is registered with parser classes and capabilities
- **THEN** the factory automatically wires managers using the same `Cli*Manager` classes — the provider does not reference any manager class

#### Scenario: Provider port has no CLI-adapter hooks
- **WHEN** the `RuntimeProvider` ABC is inspected
- **THEN** its imports do not include `PtyTransport`, `OutputStream`, `TtyDetector`, `CancellationToken`, `StreamingTransport`, or `Transport`
