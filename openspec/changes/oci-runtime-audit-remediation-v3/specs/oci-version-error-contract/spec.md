## MODIFIED Requirements

### Requirement: version() raises OciError on non-zero exit

`ContainerEngine.version()` must raise `OciError` (not `RuntimeNotAvailableError`) when the runtime binary returns a non-zero exit code. The exception carries `command`, `exit_code`, and `stderr` so callers can diagnose the failure.

#### Scenario: docker --version fails with non-zero exit
- **WHEN** `docker --version` returns exit code 1, stderr `"Error: docker daemon not running"`
- **THEN** `engine.version()` raises `OciError` with `command=["docker", "--version"]`, `exit_code=1`, `stderr="Error: docker daemon not running"`

#### Scenario: version() propagates OperationTimeoutError
- **WHEN** `transport.execute(["docker", "--version"], timeout=0.1)` raises `OperationTimeoutError`
- **THEN** `engine.version()` propagates the `OperationTimeoutError` unchanged (it is an `OciError` subclass)

#### Scenario: version() success returns stripped stdout
- **WHEN** `docker --version` returns exit 0, stdout `"Docker version 24.0.0\n"`
- **THEN** `engine.version()` returns `"Docker version 24.0.0"`

### Requirement: RuntimeFactory.create() raises ProviderNotRegisteredError for unknown RuntimeKind

When a user passes a `RuntimePreference` with a `RuntimeKind` not present in the factory's provider registry, `RuntimeFactory.create()` raises `ProviderNotRegisteredError(OciError)` instead of `NotImplementedError`. The exception message lists the registered kinds.

#### Scenario: Unknown runtime kind raises ProviderNotRegisteredError
- **WHEN** `RuntimeFactory().create(RuntimePreference(kind=RuntimeKind("nerdctl"), binary="nerdctl"))` with no nerdctl provider registered
- **THEN** `ProviderNotRegisteredError` is raised, message includes registered kinds `[DOCKER, PODMAN]`

## ADDED Requirements

### Requirement: ProviderNotRegisteredError is an OciError subclass

A new `ProviderNotRegisteredError` exception in `domain/exceptions.py` inherits from `OciError` and carries the unknown `RuntimeKind`. It is re-exported via `oci_runtime/__init__.py`.

#### Scenario: Catching ProviderNotRegisteredError via OciError
- **WHEN** `RuntimeFactory().create(unknown_preference)` is called
- **THEN** `except OciError` catches `ProviderNotRegisteredError`