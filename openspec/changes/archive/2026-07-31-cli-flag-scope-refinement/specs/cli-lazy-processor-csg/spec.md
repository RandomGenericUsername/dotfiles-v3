## ADDED Requirements

### Requirement: CSG builds processor lazily in generate command

CSG SHALL NOT build the processor in the root `@app.callback()`. Instead, the `generate` command SHALL build the processor on demand in its own body, based on resolved `--runtime` and `--container-engine` values.

#### Scenario: generate builds processor from --runtime flag

- **WHEN** `csg generate img.png --runtime container --container-engine podman` is run
- **THEN** a `ContainerProcessor` is built wrapping a Podman container engine
- **THEN** `generate` uses that processor to produce the palette

#### Scenario: generate falls back to TOML config when --runtime is omitted

- **WHEN** user config has `runtime.mode = "container"` and `csg generate img.png` is run (no `--runtime` flag)
- **THEN** the runtime mode is read from resolved `settings.runtime.mode`
- **THEN** a `ContainerProcessor` is built using the container engine from config

#### Scenario: show builds its own processor from config

- **WHEN** `csg show img.png` is run
- **THEN** `show` resolves config and builds the processor from `settings.runtime.mode`
- **THEN** `show` uses that processor to display the palette

#### Scenario: version runs without building any processor

- **WHEN** `csg version` is run
- **THEN** no processor is built — only version metadata is read
- **THEN** version output is returned immediately

#### Scenario: Processor construction is deferred for all read-only commands

- **WHEN** `csg info`, `csg dump-config`, `csg dump-templates`, or `csg list-backends` is run
- **THEN** no processor is built
- **THEN** the command completes using only config resolution and catalog loading

### Requirement: Processor dispatch logic lives in the command body

The decision of whether to build a `LocalProcessor` vs `ContainerProcessor` SHALL be made inside each command that needs a processor, not in the root callback or factory.

#### Scenario: generate evaluates runtime in its body

- **WHEN** the `generate` command body runs
- **THEN** it evaluates the effective runtime mode (CLI override > TOML/ENV > default)
- **THEN** it calls `create_local_processor()` or `create_container_processor()` accordingly
