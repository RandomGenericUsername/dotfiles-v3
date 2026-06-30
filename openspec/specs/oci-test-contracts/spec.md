## MODIFIED Requirements

### Requirement: Wiring tests assert against ports, not concrete adapters

`tests/unit/wiring/test_factory_wiring.py` and `tests/unit/contract/test_interface_compliance.py` must assert `isinstance(runtime.images, ImageManager)` (the port), not `isinstance(runtime.images, CliImageManager)` (the adapter). This allows a future swapped `ImageManager` implementation to pass wiring tests without test changes.

#### Scenario: Factory wiring test passes with ImageManager spec
- **WHEN** `test_create_docker_wires_docker_managers` runs
- **THEN** `assert isinstance(runtime.images, ImageManager)` passes; no assertion on `CliImageManager`

#### Scenario: Contract test verifies adapter implements port
- **WHEN** `test_cli_image_manager_implements_all` runs
- **THEN** it constructs `CliImageManager` and asserts `isinstance(mgr, ImageManager)` (port), not identity check on class name

### Requirement: Factory config defaults test covers all 15 fields

`test_factory_config_defaults_are_none` asserts that **all 15** `RuntimeFactoryConfig` fields default to `None` (was 4). Any future field added must be included.

#### Scenario: All 15 config fields default to None
- **WHEN** `RuntimeFactoryConfig()` is constructed
- **THEN** `transport_factory`, `streaming_transport_factory`, `runtime_cls`, `discovery_factory`, `tty_detector_factory`, `output_stream_factory`, `cancellation_factory`, `binary_resolver_factory`, `pty_transport_factory`, `result_checker_factory`, `list_executor_factory`, `container_manager_cls`, `image_manager_cls`, `volume_manager_cls`, `network_manager_cls` are all `None`

### Requirement: CliResultChecker constructor contract test

A new test verifies that `CliResultChecker` requires `generic_error` and `not_found_error` at construction, and that optional `auth_error`/`is_auth` can be omitted.

#### Scenario: CliResultChecker requires both error types
- **WHEN** `CliResultChecker(generic_error=ContainerRuntimeError, not_found_error=ContainerNotFoundError, is_not_found=lambda s: False)` is constructed
- **THEN** no error; the instance is valid

#### Scenario: CliResultChecker without not_found_error raises TypeError
- **WHEN** `CliResultChecker(generic_error=ContainerRuntimeError)` is attempted
- **THEN** `TypeError` is raised (missing required arguments)

### Requirement: CliListExecutor constructor contract test

A new test verifies that `CliListExecutor[T]` requires `transport`, `caps`, `result_checker`, and `parse_list` at construction.

#### Scenario: CliListExecutor requires all four arguments
- **WHEN** `CliListExecutor(transport, caps, checker, parse_fn)` is constructed with all correct types
- **THEN** no error; the instance is valid

#### Scenario: CliListExecutor without result_checker raises TypeError
- **WHEN** `CliListExecutor(transport, caps, None, parse_fn)` is attempted
- **THEN** `TypeError` is raised (missing required argument)

### Requirement: Factory creates managers with injected ResultChecker and ListExecutor

A new wiring test (or updated `test_factory_wiring.py`) verifies that each manager has `_result_checker` and `_list_executor` attributes set to the correct types, and that the checker is shared between manager and executor.

#### Scenario: Container manager has ResultChecker
- **WHEN** `runtime.containers` is inspected
- **THEN** `runtime.containers._result_checker` is an instance of `ResultChecker` (port ABC)
- **AND** `runtime.containers._result_checker` is the same object as `runtime.containers._list_executor._result_checker`

#### Scenario: Each manager has distinct ListExecutor instances
- **WHEN** all four managers are inspected
- **THEN** `container._list_executor`, `image._list_executor`, `volume._list_executor`, `network._list_executor` are all distinct objects
- **AND** each has the correct `T` bound (ContainerInfo, ImageInfo, VolumeInfo, NetworkInfo)

### Requirement: Conformance fixture absence is noisy

When `make capture-fixtures` has not been run, the conformance test suite must emit a clear pytest warning or skip message listing which fixtures are missing, rather than silently skipping all tests. Implementation: add a `pytest_runtest_setup` hook or a `conftest.py` fixture that scans `tests/conformance/fixtures/` and emits a warning if empty.

#### Scenario: Missing fixtures produce pytest warning
- **WHEN** `pytest -m conformance` runs and `tests/conformance/fixtures/` is empty
- **THEN** a warning "Conformance fixtures not captured; run `make capture-fixtures`" appears in pytest output

### Requirement: Parsers frozen dataclass test uses correct parser types

`test_parsers_is_frozen_dataclass` in `test_interface_compliance.py` is fixed to use `DockerContainerParser()`, `DockerImageParser()`, `DockerVolumeParser()`, `DockerNetworkParser()` in their respective slots, not `DockerContainerParser()` for all four.

#### Scenario: Parsers aggregate constructed with correct types
- **WHEN** `Parsers(container_parser=DockerContainerParser(), image_parser=DockerImageParser(), ...)` is created
- **THEN** `assert parsers.container_parser is not parsers.image_parser` (distinct instances)

### Requirement: Factory wiring broken-key test fixed

`test_factory_wiring.py:test_custom_transport_factory_is_used` uses `{"docker --version": ...}` as response key. Fixed to `{("docker", "--version"): ...}` so the `RecordingTransport` lookup actually matches. An assertion is added that `execute` was called.

#### Scenario: Response key matches transport.execute tuple signature
- **WHEN** the custom transport's `execute(["docker", "--version"])` is called
- **THEN** the response dict with key `("docker", "--version")` is matched and returned

## REMOVED Requirements

### Requirement: _not_found_error required-class-attribute regression test

**Reason**: `CliBaseManager` is deleted; managers no longer define `_not_found_error` as a class attribute. Each `CliResultChecker` instance receives `not_found_error` via constructor injection. The contract is enforced by `ResultChecker` ABC and `CliResultChecker.__init__`.

### Requirement: Dead subprocess.run patches in factory wiring tests

**Reason**: `CliTransport` uses `subprocess.Popen`, never `subprocess.run`. The `@patch("subprocess.run")` decorators in `test_factory_wiring.py` are dead code.

**Migration**: Delete the decorators and the unused `mock_run` parameters.
