## ADDED Requirements

### Requirement: Wiring tests assert parsed CLI output, not mock constants

The `tests/unit/wiring/` `docker_engine` fixture SHALL wire real `Docker*Parser` instances (not `Mock*Parser` instances that discard their `raw` argument). Lifecycle and inspect/list assertions SHALL assert values present in the injected JSON (e.g. `info.id == "ctr1"` where the JSON contains `"Id":"ctr1"`), not hardcoded mock constants (`id == "abc"`). A broken `DockerContainerParser.parse_inspect` SHALL cause these tests to fail.

#### Scenario: Wiring inspect asserts the injected Id
- **WHEN** `test_container_lifecycle` injects inspect JSON with `"Id":"ctr1"` and asserts `info.id`
- **THEN** the assertion compares against `"ctr1"` (from the JSON), and would fail if the parser returned a different value

#### Scenario: Mock parsers that discard raw are not used in wiring
- **WHEN** the `docker_engine` fixture is inspected
- **THEN** it constructs `DockerContainerParser`, `DockerImageParser`, `DockerVolumeParser`, `DockerNetworkParser` (real), not `Mock*Parser`

### Requirement: Every wiring test has at least one assertion on emitted command or returned value

No test in `tests/unit/wiring/` SHALL pass without exercising the system under test. `test_container_exec_with_options` SHALL assert the emitted command (e.g. `t.calls[0].command == ["docker","exec","-d","-u","root","ctr1","ls"]`), not merely call the manager and return.

#### Scenario: exec with options asserts the command shape
- **WHEN** `test_container_exec_with_options` runs
- **THEN** it asserts the recorded command contains `-d` and `-u root` in the correct positions

### Requirement: Smoke lifecycle tests are parametrized over docker and podman

`tests/integration/smoke/` lifecycle tests (pull, run, stop, logs, tag, volume, network) SHALL be parametrized over `live_docker_engine` and `live_podman_engine`, both skip-if-unavailable. The podman engine SHALL NOT be constructed and then left unexercised. Podman-specific manager breakages SHALL be caught end-to-end.

#### Scenario: Podman lifecycle is exercised end-to-end
- **WHEN** the smoke suite runs with podman installed
- **THEN** the run/stop/logs/volume/network lifecycle tests run against `live_podman_engine` (not just `live_docker_engine`)

#### Scenario: Podman absence skips gracefully
- **WHEN** podman is not installed
- **THEN** the podman-parametrized lifecycle tests are skipped (not failed)

### Requirement: Test suite is ruff-clean and shares one manager-construction factory

`tests/audit/test_known_bugs.py`, `tests/unit/adapters/test_cli_container_manager.py`, and `tests/unit/wiring/test_workflows.py` SHALL have zero `F401` (unused import), `F811` (redefinition), or `F841` (unused variable) errors. The manager-construction scaffolding (`_container_mgr`/`_image_mgr`/`_volume_mgr`/`_network_mgr`) SHALL be consolidated into a single shared helper in `tests/helpers/` and imported by all test modules that need it.

#### Scenario: ruff reports zero errors on the test suite
- **WHEN** `ruff check tests/` is run
- **THEN** the exit code is 0 and zero errors are reported

#### Scenario: Single shared manager factory
- **WHEN** the test modules are inspected
- **THEN** there is exactly one definition of the `build_container_mgr`/`build_image_mgr`/etc. helpers (in `tests/helpers/`), and the three previously-duplicated noop container parser classes are replaced by the shared `MockContainerParser`
