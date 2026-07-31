# csg-cli-integration-tests Specification

## Purpose
TBD - created by archiving change csg-test-characterization. Update Purpose after archive.
## Requirements
### Requirement: Command integration tests drive the real Typer app
Command tests SHALL invoke the real `app` via `typer.testing.CliRunner` with a `FakeProcessor` injected through `CliDependencies(processor=...)`. The fake SHALL record each call with its arguments and write a dummy file at the requested output paths. Assertions SHALL target observable output — exit codes, files under `tmp_path`, JSON stdout structure — not mock call counts.

#### Scenario: Fake processor records generate invocation
- **WHEN** `csg generate <input.png> --backend custom -o <tmp_path>/out` is invoked via `CliRunner` with a fake processor
- **THEN** the fake records a `process_generate` call with the resolved `GeneratorConfig`
- **AND** the exit code is 0

#### Scenario: Fake processor records show invocation
- **WHEN** `csg show <input.png> --backend custom` is invoked via `CliRunner` with a fake processor
- **THEN** the fake records a `process_show` call
- **AND** the exit code is 0

### Requirement: All commands have basic smoke tests
Each command — `generate`, `show`, `info`, `dump-config`, `dump-templates`, `install`, `uninstall`, `list-backends`, `version` — SHALL have at least one test that drives the real `app` via `CliRunner` and asserts exit code 0 plus command-specific observable output.

#### Scenario: generate smoke test
- **WHEN** `csg generate <input> --backend custom --param saturation=0.5 --format json -o <tmp_path>/out` is invoked
- **THEN** the exit code is 0
- **AND** dummy output files exist under `<tmp_path>/out`

#### Scenario: show smoke test
- **WHEN** `csg show <input> --backend custom` is invoked
- **THEN** the exit code is 0
- **AND** stdout is valid JSON containing the fake's color scheme data

#### Scenario: info smoke test
- **WHEN** `csg info` is invoked
- **THEN** the exit code is 0
- **AND** stdout is valid JSON with `settings` and `backends` keys

#### Scenario: dump-config smoke test
- **WHEN** `csg dump-config` is invoked
- **THEN** the exit code is 0
- **AND** stdout is valid TOML containing `[output]`, `[generation]`, `[runtime]`, `[container]` sections

#### Scenario: dump-templates smoke test
- **WHEN** `csg dump-templates` is invoked
- **THEN** the exit code is 0
- **AND** the bundled template files are copied to the destination

#### Scenario: list-backends smoke test
- **WHEN** `csg list-backends` is invoked
- **THEN** the exit code is 0
- **AND** the output lists the custom, pywal, and wallust backends

#### Scenario: version smoke test
- **WHEN** `csg version` is invoked
- **THEN** the exit code is 0
- **AND** stdout is valid JSON containing a `version` key

### Requirement: install and uninstall commands are characterized
`install` and `uninstall` SHALL be tested through the real `app` with `shutil.which`/`subprocess.run` patched at the process boundary, asserting exit codes and observable messages rather than internal mock calls.

#### Scenario: install with dry-run
- **WHEN** `csg install --dry-run --backend pywal` is invoked
- **THEN** the exit code is 0
- **AND** no container image is actually built

#### Scenario: uninstall with --yes
- **WHEN** `csg uninstall --yes --backend pywal` is invoked
- **THEN** the exit code is 0
- **AND** the output reports the backend image removed

### Requirement: Global flags work through the real CLI
`--output-format json|rich|plain`, `-q`/`--quiet`, and `-v`/`--verbose` SHALL behave observably through the real `app`.

#### Scenario: JSON output format
- **WHEN** `csg --output-format json info` is invoked
- **THEN** stdout parses as valid JSON

#### Scenario: Rich output format
- **WHEN** `csg --output-format rich info` is invoked
- **THEN** stdout contains ANSI escape sequences

#### Scenario: Plain output format
- **WHEN** `csg --output-format plain info` is invoked
- **THEN** stdout contains no ANSI escape sequences

#### Scenario: Quiet flag suppresses non-error output
- **WHEN** `csg --quiet info` is invoked
- **THEN** non-error output is suppressed

#### Scenario: Verbose flag increases output detail
- **WHEN** `csg -v info` is invoked
- **THEN** output is more detailed than baseline

### Requirement: Error paths are characterized
Missing input files, missing config files, invalid backends, and container-runtime-unavailable conditions SHALL be tested through the real `app` and SHALL produce non-zero exit codes with observable error output.

#### Scenario: Missing input file
- **WHEN** `csg generate <nonexistent.png>` is invoked
- **THEN** the exit code is non-zero
- **AND** error output is rendered through the output adapter

#### Scenario: Missing config file
- **WHEN** `csg info --config <nonexistent.toml>` is invoked
- **THEN** the exit code is non-zero

#### Scenario: Invalid backend
- **WHEN** `csg generate <input> --backend not-a-backend` is invoked
- **THEN** the exit code is non-zero
- **AND** the error identifies the invalid backend

#### Scenario: Container runtime unavailable
- **WHEN** `csg generate <input> --runtime container` is invoked with an unavailable container runtime
- **THEN** the exit code is non-zero
- **AND** the error is mapped through `map_oci_error` to a `ColorSchemeError`

### Requirement: Lazy processor construction and runtime mode resolution are characterized
Tests SHALL flag (assert) that processor construction is lazy — the processor is built at command execution, not at dependency build time — and that `--runtime`/`--container-engine` resolve the effective runtime mode correctly.

#### Scenario: Local runtime uses local processor path
- **WHEN** `csg generate <input>` runs with `runtime.mode = "local"` and no `--runtime` override
- **THEN** the effective runtime is local and the local processor path is exercised

#### Scenario: Container runtime flag selects container processor
- **WHEN** `csg generate <input> --runtime container` is invoked
- **THEN** the container processor path is exercised

