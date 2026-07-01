## ADDED Requirements

### Requirement: Factory composition root has non-lying types after resolution

`RuntimeFactoryConfig` SHALL expose a resolved configuration whose factory/callable/type fields are non-`Optional` after `_resolve_config()` runs. The implementation SHALL either (a) introduce a `ResolvedRuntimeFactoryConfig` with non-`Optional` fields produced by `_resolve_config()`, or (b) assign resolved fields via `object.__setattr__` on the frozen instance with a type-narrowed accessor. `RuntimeFactory.create()` SHALL consume the resolved config so that `self._cfg.binary_resolver_factory()` etc. are statically known to be non-`None`. This eliminates the 57 mypy "None not callable" / `replace(**dict)` errors where the runtime is correct but the types lie.

#### Scenario: mypy reports zero "None not callable" errors in factory.py
- **WHEN** `mypy src/oci_runtime/factory.py` is run
- **THEN** zero `"None" not callable` and zero `Argument ... has incompatible type "**dict..."` errors are reported for the factory module

#### Scenario: Resolved config fields are non-Optional
- **WHEN** the type of the resolved config consumed by `RuntimeFactory.create()` is inspected
- **THEN** `transport_factory`, `binary_resolver_factory`, `pty_transport_factory`, etc. are annotated non-`Optional`

### Requirement: RuntimeProvider.capabilities is a property

`RuntimeProvider.capabilities` SHALL be a `@property` (read-only accessor), matching `ContainerEngine.capabilities` and `RuntimeProvider.kind`. Callers write `provider.capabilities` (no parentheses). The factory, the only internal caller, is updated to drop the call parentheses. This removes the footgun where `engine.capabilities` is a property but `provider.capabilities()` is a method for the same concept.

#### Scenario: capabilities accessed without parentheses
- **WHEN** a `RuntimeProvider` instance is accessed as `provider.capabilities`
- **THEN** it returns a `RuntimeCapabilities` (not a bound method)

#### Scenario: kind and capabilities use the same accessor style
- **WHEN** `RuntimeProvider.kind` and `RuntimeProvider.capabilities` are inspected
- **THEN** both are `@property`

### Requirement: Public API re-exports Parsers and cancellation constructors

`oci_runtime/__init__.py` SHALL re-export `Parsers`, `ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken`, and `compose_tokens` in `__all__`. A consumer implementing a custom `RuntimeProvider` (constructing `Parsers`) or composing a user-cancellation token (passing it to `Transport.execute/stream/execute_pty`) SHALL NOT need to import from `oci_runtime.ports` — the top-level package is sufficient. This honors the "consumers never need to import from submodules" promise in `ARCHITECTURE.md`.

#### Scenario: Parsers importable from the top-level package
- **WHEN** `from oci_runtime import Parsers` is executed
- **THEN** `Parsers` is a class (the frozen aggregate dataclass)

#### Scenario: Cancellation constructors importable from the top-level package
- **WHEN** `from oci_runtime import ThreadCancellationToken, DeadlineCancellationToken, compose_tokens` is executed
- **THEN** all three names are available and `ThreadCancellationToken()` constructs a usable token

#### Scenario: __all__ includes the new re-exports
- **WHEN** `oci_runtime.__all__` is inspected
- **THEN** it contains `"Parsers"`, `"ThreadCancellationToken"`, `"DeadlineCancellationToken"`, `"CompositeCancellationToken"`, `"compose_tokens"`, and `"ProviderNotRegisteredError"`
