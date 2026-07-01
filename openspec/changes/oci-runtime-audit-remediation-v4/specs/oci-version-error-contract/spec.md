## MODIFIED Requirements

### Requirement: RuntimeFactory.create() raises ProviderNotRegisteredError for unknown RuntimeKind

When a user passes a `RuntimePreference` with a `RuntimeKind` not present in the factory's provider registry, `RuntimeFactory.create()` raises `ProviderNotRegisteredError(OciError)` — NOT `NotImplementedError`. The exception message lists the registered kinds. `RuntimeKind` SHALL be extensible: `RuntimeKind("nerdctl")` SHALL NOT raise `ValueError` at construction (a `_missing_` hook returns an ad-hoc member for unknown non-empty values), so the documented "Adding a New Runtime" example works end-to-end and the unregistered kind reaches the factory, which then raises `ProviderNotRegisteredError`.

#### Scenario: Unknown runtime kind raises ProviderNotRegisteredError
- **WHEN** `RuntimeFactory().create(RuntimePreference(kind=RuntimeKind("nerdctl"), binary="nerdctl"))` with no nerdctl provider registered
- **THEN** `ProviderNotRegisteredError` is raised (not `NotImplementedError`), message includes registered kinds `[DOCKER, PODMAN]`

#### Scenario: RuntimeKind construction does not raise for unknown value
- **WHEN** `RuntimeKind("nerdctl")` is called
- **THEN** it returns a member with `.value == "nerdctl"` and does not raise `ValueError`

#### Scenario: Catching ProviderNotRegisteredError via OciError
- **WHEN** `RuntimeFactory().create(unknown_preference)` is called
- **THEN** `except OciError` catches `ProviderNotRegisteredError`

### Requirement: ProviderNotRegisteredError is an OciError subclass

A `ProviderNotRegisteredError` exception EXISTS in `domain/exceptions.py`, inherits from `OciError`, and carries the unknown `RuntimeKind`. It is re-exported via `oci_runtime/__init__.py` (added to `__all__`). (This requirement was previously specced but not implemented; it is now actually present in the codebase.)

#### Scenario: ProviderNotRegisteredError exists and is an OciError
- **WHEN** `from oci_runtime import ProviderNotRegisteredError` is imported
- **THEN** `issubclass(ProviderNotRegisteredError, OciError)` is `True`

#### Scenario: ProviderNotRegisteredError carries the unknown kind
- **WHEN** `ProviderNotRegisteredError(RuntimeKind("nerdctl"))` is constructed
- **THEN** the exception's `.kind` attribute equals `RuntimeKind("nerdctl")`
