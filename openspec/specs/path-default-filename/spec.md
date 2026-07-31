# path-default-filename Specification

## Purpose
TBD - created by archiving change fix-dump-config-paths. Update Purpose after archive.
## Requirements
### Requirement: dump-config auto-appends settings.toml when output is a directory

When the user provides a directory path (no file extension) as `--output` to `dump-config`, the tool SHALL automatically append `settings.toml` to the path.

#### Scenario: directory path via --output

- **WHEN** user runs `csg dump-config --output ./`
- **THEN** the file `./settings.toml` is created with the resolved configuration

#### Scenario: explicit file path via --output

- **WHEN** user runs `csg dump-config --output ./custom.toml`
- **THEN** the file `./custom.toml` is created with the resolved configuration

#### Scenario: no --output prints to stdout

- **WHEN** user runs `csg dump-config` (no `--output` flag)
- **THEN** the resolved configuration is printed to stdout

### Requirement: dump-config respects --config flag

When the user passes `--config` to the global callback, `dump-config` SHALL forward it to the config resolver instead of resolving from defaults.

#### Scenario: custom config path

- **WHEN** user runs `csg --config /custom/settings.toml dump-config --output ./out.toml`
- **THEN** the output contains settings from `/custom/settings.toml`, not the defaults

### Requirement: dump-templates auto-appends filename when output is a directory

When the user provides a directory path as `--output` to `dump-templates`, the tool SHALL create the default template directory structure inside that path.

#### Scenario: directory path via --output

- **WHEN** user runs `csg dump-templates --output ./`
- **THEN** template files are written to `./templates/` directory

### Requirement: dump-templates fallback XDG path matches resolver

The `dump-templates` command SHALL use `~/.config/color-scheme/templates` as its fallback target directory, matching the `TemplateDirResolver`'s XDG strategy.

#### Scenario: fallback path consistency

- **WHEN** the template dir resolver fails and no `--output` is given
- **THEN** templates are written to `~/.config/color-scheme/templates/`

