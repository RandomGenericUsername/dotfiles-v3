# WEG CLI Integration Tests

## Why

Existing CLI command tests (`test_process_commands.py`, `test_batch_commands.py`, `test_show_commands.py`) patch `_resolve_processor`/`_resolve_context`/`create_batch_processor`, testing mock plumbing instead of real CLI behavior. These tests produce false confidence — they pass even when the real output-dir fallback, `mkdir`, error-rendering, or JSON-structure code is broken.

This spec defines the contract for `CliRunner`-based integration tests that drive the real Typer `app` with fakes at the port boundary, covering all 9 commands, global flags, option propagation, and error paths.

## ADDED Requirements

### Requirement: Command integration tests drive the real Typer app
Command integration tests SHALL invoke commands through `typer.testing.CliRunner` against the real `weg` `app` from `cli.main`, with test dependencies injected via a `monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", ...)` seam. (Supersedes the original `WEG_TEST_DEPS` env-var seam, removed by `weg-test-seam-cleanup`.)

#### Scenario: Real app is used, not a mock
- **WHEN** a test imports `app` from `wallpaper_effects_generator.cli.main` and invokes it via `CliRunner`
- **THEN** the real Typer parser, callback, option definitions, and `ctx.obj` wiring are exercised

#### Scenario: Fake processor is injected for process/batch commands
- **WHEN** a test monkeypatches `build_deps` to return `CliDependencies(processor=<fake>)` before invoking the app
- **THEN** the callback uses the test-supplied `CliDependencies` with the fake `EffectProcessorPort`
- **AND** each `process_effect`/`process_composite`/`process_preset`/`process_batch` call is recorded (arguments captured)
- **AND** a dummy output file is created at `request.output_path` (or batch output paths)
- **AND** the fake is the only processor present — no real `LocalProcessor` or `ContainerProcessor` is created

### Requirement: All 9 commands have basic smoke tests
Each command SHALL have at least one test that asserts non-zero exit code (success), valid JSON stdout structure, and no unexpected errors.

#### Scenario: info command succeeds
- **WHEN** `weg info` is invoked
- **THEN** exit code is 0
- **AND** stdout is valid JSON with `settings` and `catalog` keys

#### Scenario: dump-config command succeeds
- **WHEN** `weg dump-config` is invoked
- **THEN** exit code is 0
- **AND** stdout is valid TOML containing `[execution]` and `[container]` sections

#### Scenario: dump-config --output writes to file
- **WHEN** `weg dump-config --output <tmp_path>/cfg.toml` is invoked
- **THEN** exit code is 0
- **AND** the file at `<tmp_path>/cfg.toml` exists and is valid TOML

#### Scenario: dump-effects command succeeds
- **WHEN** `weg dump-effects` is invoked
- **THEN** exit code is 0
- **AND** stdout is valid YAML containing `effects`, `composites`, and `presets` keys

#### Scenario: dump-effects --output writes to file
- **WHEN** `weg dump-effects --output <tmp_path>/fx.yaml` is invoked
- **THEN** exit code is 0
- **AND** the file at `<tmp_path>/fx.yaml` exists and is valid YAML

#### Scenario: version command succeeds
- **WHEN** `weg version` is invoked
- **THEN** exit code is 0
- **AND** stdout is valid JSON with `"version"` key and semantic-version string value

#### Scenario: process effect succeeds with dry-run flag
- **WHEN** `weg process effect blur input.png -o <tmp_path>/out.png --dry-run` is invoked with a fake processor injected
- **THEN** exit code is 0
- **AND** recorded call shows `command="process_effect"`, `name="blur"`, `request.input_path` ends with `input.png`

#### Scenario: process effect with --param overrides
- **WHEN** `weg process effect blur input.png -o <tmp_path>/out.png --dry-run --param radius=0x8 --param sigma=3.0` is invoked
- **THEN** exit code is 0
- **AND** `request.params` in the recorded call contains `{"radius": "0x8", "sigma": "3.0"}`

#### Scenario: batch all succeeds with dry-run flag
- **WHEN** `weg batch all input.png --dry-run` is invoked
- **THEN** exit code is 0
- **AND** recorded call shows `command="process_batch"` with `BatchRequest`

#### Scenario: show effects/composites/presets/all succeed
- **WHEN** `weg show effects`, `weg show composites`, `weg show presets`, and `weg show all` are invoked
- **THEN** each returns exit code 0
- **AND** stdout is valid JSON with `"type"` and `"items"` keys

#### Scenario: show rejects --config flag
- **WHEN** `weg show effects --config /path/to/config.toml` is invoked
- **THEN** exit code is non-zero
- **AND** stderr mentions `No such option` or `--config`

### Requirement: Global flags (--output-format, -q, -v) affect output correctly
The `--output-format json|rich|plain`, `--quiet`, and `--verbose` flags SHALL control output rendering as documented in the CLI help.

#### Scenario: --output-format json produces JSON
- **WHEN** `weg info --output-format json` is invoked
- **THEN** stdout is valid JSON

#### Scenario: --output-format rich produces styled terminal output
- **WHEN** `weg info --output-format rich` is invoked
- **THEN** stdout contains ANSI escape sequences (`\x1b[`)

#### Scenario: --output-format plain produces plain text
- **WHEN** `weg info --output-format plain` is invoked
- **THEN** stdout contains no ANSI escape sequences

#### Scenario: --quiet suppresses all non-error output
- **WHEN** `weg version --quiet` is invoked
- **THEN** stdout is empty (no version printed)

#### Scenario: -v increases verbosity
- **WHEN** `weg info -v` is invoked
- **THEN** stdout contains more detail than `weg info` without `-v` (e.g., resolved paths, applied overrides)

### Requirement: Error paths return non-zero and structured JSON
Invalid input, missing files, and resolution failures SHALL produce exit code 1 (or >0) and structured JSON error output in `--output-format json` mode.

#### Scenario: Missing input file yields error
- **WHEN** `weg process effect blur /nonexistent/input.png --dry-run` is invoked
- **THEN** exit code is non-zero
- **AND** stdout is valid JSON containing `"error"` key with `"type"` and `"message"` fields

#### Scenario: Missing --config file yields error
- **WHEN** `weg info --config /nonexistent/config.toml` is invoked
- **THEN** exit code is non-zero
- **AND** stderr mentions file not found or resolution failure

### Requirement: install/uninstall commands accept --container-engine override
The `install` and `uninstall` commands SHALL accept `--container-engine docker|podman` and pass it to the config resolution.

#### Scenario: install with --container-engine podman
- **WHEN** `weg install --container-engine podman --dry-run` is invoked
- **THEN** exit code is 0 (the engine type is passed to config; resolution succeeds with default config)

#### Scenario: install with invalid engine name
- **WHEN** `weg install --container-engine invalid` is invoked
- **THEN** exit code is non-zero
- **AND** error message mentions the invalid engine value
