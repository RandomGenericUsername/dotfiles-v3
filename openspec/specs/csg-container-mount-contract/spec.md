# csg-container-mount-contract Specification

## Purpose
TBD - created by archiving change csg-test-characterization. Update Purpose after archive.
## Requirements
### Requirement: process_generate mounts four containers
`process_generate` SHALL mount exactly 4 volumes with correct `source`/`target`/`read_only`:
- settings TOML (temp file, `read_only=True`)
- templates directory (resolved via `template_dir_resolver`, `read_only=True`)
- input image parent directory (`request.image_path.resolve().parent`, `read_only=True`)
- output directory (`read_only=False`)

#### Scenario: All four mounts present with correct targets
- **WHEN** `process_generate` runs on a request with input and output directories
- **THEN** the recorded run config has exactly 4 volume mounts
- **AND** the targets are `/csg-config/settings.toml`, `/templates`, `/input`, and `/output`
- **AND** the config, templates, and input mounts are `read_only=True`
- **AND** the output mount is `read_only=False`

#### Scenario: Mount sources are host-resolved
- **WHEN** `process_generate` runs
- **THEN** the input mount source is the resolved parent of the input image
- **AND** the output mount source is the resolved output directory

### Requirement: process_show mounts three containers (no output mount)
`process_show` SHALL mount exactly 3 volumes — config TOML, templates, and input parent — with no `/output` mount.

#### Scenario: Show mode omits the output mount
- **WHEN** `process_show` runs
- **THEN** the recorded run config has exactly 3 volume mounts
- **AND** `/output` is NOT among the targets

### Requirement: Container environment matches _CONTAINER_ENV
The run config environment SHALL equal the module's `_CONTAINER_ENV` dict, including the forced `COLORSCHEME__RUNTIME__MODE=local` so the inner `csg` does not recurse into container mode.

#### Scenario: Environment dict equals _CONTAINER_ENV
- **WHEN** `process_generate` runs
- **THEN** the recorded run config's `environment` equals `_CONTAINER_ENV`

### Requirement: Serialized temp settings.toml is valid and forces local runtime
The settings serialized for the container SHALL be valid TOML and SHALL contain `runtime.mode = "local"`, overwriting the original runtime mode for in-container safety.

#### Scenario: Temp TOML parses and forces local mode
- **WHEN** `process_generate` runs with settings whose `runtime.mode` is not `local`
- **THEN** the recorded temp settings.toml content parses as valid TOML
- **AND** `data["runtime"]["mode"] == "local"`

### Requirement: Temp artifacts are cleaned up on success and exception
Temp settings.toml files SHALL be removed after processing, both on success and when an exception is raised.

#### Scenario: Cleanup on success
- **WHEN** `process_generate` completes successfully
- **THEN** the temp settings.toml file no longer exists

#### Scenario: Cleanup on exception
- **WHEN** `process_generate` raises during processing
- **THEN** the temp settings.toml file is removed before the exception propagates

### Requirement: Missing container image raises ContainerImageNotFoundError
If the configured container image does not exist, `process_generate` and `process_show` SHALL raise `ContainerImageNotFoundError` and SHALL NOT submit a run.

#### Scenario: Image does not exist
- **WHEN** `image_exists()` returns `False`
- **THEN** `ContainerImageNotFoundError` is raised
- **AND** no run config is submitted

### Requirement: Input parent at filesystem root is rejected
If the input image's resolved parent directory is `/`, the processor SHALL reject the request and SHALL NOT mount the filesystem root.

#### Scenario: Input image directly under root
- **WHEN** `request.image_path` resolves to a path whose parent is `/`
- **THEN** an error is raised
- **AND** no run config is submitted

### Requirement: Adapter's inner argv is accepted by the live CLI parser
The command string built by `ContainerProcessor` for the inner `csg` invocation SHALL be accepted by the real Typer `app` — the interface-contract test runs the adapter's argv through `CliRunner`.

#### Scenario: Inner generate argv round-trips through the app
- **WHEN** the adapter builds the inner argv for a generate request
- **THEN** invoking the real `app` with that argv yields exit code 0 (with processor construction stubbed)

#### Scenario: Inner show argv round-trips through the app
- **WHEN** the adapter builds the inner argv for a show request
- **THEN** invoking the real `app` with that argv yields exit code 0 (with processor construction stubbed)

