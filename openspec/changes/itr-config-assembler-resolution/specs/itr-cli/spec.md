## MODIFIED Requirements

### Requirement: `--template-dir`, `--color-scheme`, `--output-dir` are optional
The flags SHALL remain accepted but SHALL be optional. When omitted, the corresponding root is resolved from settings.toml / env / discovery. The CLI flag SHALL take precedence over env, settings, and discovery.

#### Scenario: no flags uses settings
- **WHEN** `itr render icons.yaml` is invoked with settings.toml providing `[templates] dir`, `[color_scheme] path`, `[output] output_dir`
- **THEN** the exit code is 0 and icons render using those roots

#### Scenario: flag overrides settings
- **WHEN** `itr render icons.yaml --template-dir /alt` is invoked
- **AND** settings.toml provides a different `[templates] dir`
- **THEN** templates are read from `/alt`

### Requirement: `--config` selects settings.toml
A new `--config` option SHALL specify the settings.toml path, fed to the config resolver's path chain as the `CliPathStrategy` input.

#### Scenario: --config picks a custom settings file
- **WHEN** `itr render icons.yaml --config /custom/settings.toml` is invoked
- **THEN** settings are read from `/custom/settings.toml`

### Requirement: missing required root fails fast
When a required root (`templates_dir` or `color_scheme`) is unresolved after settings + discovery, render/validate SHALL exit non-zero with a clear `Error: ...` naming the missing root and the levers to set it.

#### Scenario: missing templates root errors
- **WHEN** `itr render icons.yaml` is invoked with no settings, env, or flag for `templates_dir`
- **THEN** the exit code is non-zero
- **AND** stderr names `templates_dir` and lists `--template-dir`, `ICON_RENDERER__TEMPLATES__DIR`, `[templates] dir`, discovery

### Requirement: list works without path roots
`itr list` SHALL read group and variant names from the icons YAML without requiring a resolved templates root or color scheme.

#### Scenario: list succeeds with no roots configured
- **WHEN** `itr list icons.yaml` is invoked with no settings/env/flag for any root
- **THEN** the exit code is 0
- **AND** the group and variant names are listed
