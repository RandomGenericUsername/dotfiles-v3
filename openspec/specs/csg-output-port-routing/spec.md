# csg-output-port-routing Specification

## Purpose
`install`, `uninstall`, `version`, and `list-backends` deliver their user-facing results through `OutputPort` methods — never through `isinstance` dispatch on concrete adapter classes.

## Requirements

### Requirement: OutputPort exposes result methods for the four commands
`OutputPort` SHALL declare `install_result(results)`, `uninstall_result(results)`, `version_info(version)`, and `backends_catalog(backends, hint="")` as part of its interface, and every concrete output adapter (`JsonOutput`, `RichOutput`, `PlainOutput`) SHALL implement all four.

#### Scenario: JsonOutput implements all four methods
- **WHEN** the structural port conformance suite runs `assert_interface_method_count(JsonOutput(), OutputPort)`
- **THEN** `JsonOutput` exposes `install_result`, `uninstall_result`, `version_info`, and `backends_catalog`

#### Scenario: PlainOutput implements all four methods
- **WHEN** the structural port conformance suite runs `assert_interface_method_count(PlainOutput(), OutputPort)`
- **THEN** `PlainOutput` exposes `install_result`, `uninstall_result`, `version_info`, and `backends_catalog`

#### Scenario: RichOutput implements all four methods
- **WHEN** the structural port conformance suite runs `assert_interface_method_count(RichOutput(), OutputPort)`
- **THEN** `RichOutput` exposes `install_result`, `uninstall_result`, `version_info`, and `backends_catalog`

### Requirement: Commands route results through the OutputPort
`install` SHALL call `output_adapter.install_result(results)`, `uninstall` SHALL call `output_adapter.uninstall_result(results)`, `version` SHALL call `output_adapter.version_info(version)`, and `list-backends` SHALL call `output_adapter.backends_catalog(backends, hint)`. None of the four commands SHALL dispatch on concrete adapter classes.

#### Scenario: Recording adapter observes install routing
- **WHEN** `csg install --dry-run --backend custom` is invoked with a recording adapter implementing only `OutputPort`
- **THEN** the adapter's `install_result` is called with a list of `{backend, image, status}` dicts
- **AND** the exit code is 0

#### Scenario: Recording adapter observes uninstall routing
- **WHEN** `csg uninstall --dry-run --backend custom --yes` is invoked with a recording adapter implementing only `OutputPort`
- **THEN** the adapter's `uninstall_result` is called with a list of `{backend, image, status}` dicts
- **AND** the exit code is 0

#### Scenario: Recording adapter observes version routing
- **WHEN** `csg version` is invoked with a recording adapter implementing only `OutputPort`
- **THEN** the adapter's `version_info` is called with the installed package version
- **AND** the exit code is 0

#### Scenario: Recording adapter observes list-backends routing
- **WHEN** `csg list-backends` is invoked with a recording adapter implementing only `OutputPort`
- **THEN** the adapter's `backends_catalog` is called with the backend list and an availability hint
- **AND** the exit code is 0