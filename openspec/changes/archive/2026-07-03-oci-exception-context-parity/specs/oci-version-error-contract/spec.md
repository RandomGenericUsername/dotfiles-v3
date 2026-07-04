## MODIFIED Requirements

### Requirement: ProviderNotRegisteredError is typed

`ProviderNotRegisteredError.kind` SHALL be annotated `RuntimeKind`. The `RuntimeKind` import SHALL be at module top-level (not inside `__init__`). Importing `RuntimeKind` at top-level SHALL NOT create a circular import (`enums.py` imports nothing from `exceptions.py`).

#### Scenario: kind is RuntimeKind-typed
- **WHEN** `ProviderNotRegisteredError(RuntimeKind.DOCKER)` is constructed
- **THEN** `.kind is RuntimeKind.DOCKER` and mypy infers `kind: RuntimeKind`

#### Scenario: no constructor-time import
- **WHEN** `domain/exceptions.py` is parsed
- **THEN** `from oci_runtime.domain.enums import RuntimeKind` appears at module top-level (not inside `__init__`)