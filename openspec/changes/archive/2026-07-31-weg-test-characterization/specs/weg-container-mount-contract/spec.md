# WEG Container Mount Contract

## Why

The `ContainerProcessor` builds a mount plan with 4 volumes (input parent dir, output dir, pre-resolved settings TOML, resolved effects YAML) and passes them via `RunConfig.volumes`. The existing test only checks that a file appears at `/output/img.png` — it never verifies mount sources/targets, read_only flags, temp artifact content, or edge cases like the input path's parent being `/` (mounting root filesystem) or symlink escapes.

This spec defines what the container mount contract SHALL guarantee.

## ADDED Requirements

### Requirement: ContainerProcessor passes 4 volume mounts with correct sources and targets
When `container_processor.py` builds a `RunConfig` for a `process` or `batch` command, it SHALL include exactly 4 `VolumeMount` objects covering input, output, settings config, and effects config.

#### Scenario: All 4 volume mounts are present
- **WHEN** `ContainerProcessor` is invoked with a valid `ProcessingRequest`
- **THEN** `RunConfig.volumes` contains exactly 4 `VolumeMount` entries

#### Scenario: Input volume has correct source and target
- **WHEN** `request.input_path` is `/home/user/wallpapers/photo.jpg`
- **THEN** one `VolumeMount` has `source = request.input_path.parent.resolve()` (i.e., `/home/user/wallpapers/`)
- **AND** `target = "/input"`
- **AND** `read_only = True`

#### Scenario: Output volume has correct source and target
- **WHEN** `request.output_path` is `/tmp/weg-output/blur.jpg`
- **THEN** one `VolumeMount` has `source = Path(request.output_path).parent.resolve()` (i.e., `/tmp/weg-output/`)
- **AND** `target = "/output"`
- **AND** `read_only = False`

#### Scenario: Settings TOML volume has correct source and target
- **WHEN** a pre-resolved settings TOML is serialized to a temp file
- **THEN** one `VolumeMount` has `source = <temp_toml_path>`
- **AND** `target = "/weg-config/settings.toml"`
- **AND** `read_only = True`

#### Scenario: Effects YAML volume has correct source and target
- **WHEN** the resolved effects YAML path is `/home/user/.config/weg/effects.yaml`
- **THEN** one `VolumeMount` has `source = Path("/home/user/.config/weg/effects.yaml").resolve()`
- **AND** `target = "/weg-effects/effects.yaml"`
- **AND** `read_only = True`

### Requirement: Input parent directory SHALL NOT be `/` (root)
If `request.input_path.parent.resolve()` returns `/`, the processor SHALL raise an error and refuse to construct the mount plan.

#### Scenario: Input at root filesystem is rejected
- **WHEN** `request.input_path` is `/photo.jpg` (so `resolve()` parent is `/`)
- **THEN** the processor raises `CommandExecutionError` or a descriptive error
- **AND** no `RunConfig` is submitted

### Requirement: Symlink escape attempts SHALL be neutralized
The processor SHALL resolve symlinks in input and output paths via `Path.resolve()` before using them as volume sources.

#### Scenario: Symlinked input is resolved before mounting
- **WHEN** `request.input_path` is a symlink `/home/user/link.jpg` pointing to `/other/location/real.jpg`
- **THEN** the input volume source is `Path("/other/location/real.jpg").parent.resolve()` (the resolved target, not the link location)

### Requirement: Temp settings TOML is valid TOML with correct content
The serialized settings TOML written to the temp file SHALL be valid TOML and contain the `AppSettings` fields with `runtime.mode` forced to `"local"`.

#### Scenario: Serialized TOML has runtime.mode local
- **WHEN** the original `AppSettings.runtime.mode` is `"container"`
- **THEN** the serialized TOML contains `runtime.mode = "local"` (overridden for in-container safety)

#### Scenario: Serialized TOML is valid and includes execution/output settings
- **WHEN** the original `AppSettings` has non-default `execution.parallel = false`
- **THEN** the serialized TOML contains `execution.parallel = false`

### Requirement: Temp artifacts are cleaned up on success and on exception
The temp TOML file and any temp per-effect directories SHALL be removed after processing completes, whether it succeeds or raises.

#### Scenario: Cleanup on success
- **WHEN** container processing succeeds
- **THEN** the temp TOML file is removed
- **AND** no temp directories remain

#### Scenario: Cleanup on exception
- **WHEN** container processing raises an exception (e.g., `RuntimeError`)
- **THEN** the temp TOML file is removed (via `finally` block or context manager)
- **AND** no temp directories remain

### Requirement: Container engine must have the image before running
The processor SHALL check `engine.images.exists(image_name)` before submitting a `RunConfig` and raise a descriptive error if the image is not found.

#### Scenario: Missing image raises ContainerImageNotFoundError
- **WHEN** `engine.images.exists("wallpaper-effects:latest")` returns `False`
- **THEN** the processor raises `ContainerImageNotFoundError`
- **AND** no `RunConfig` is submitted
