# csg-config-resolution-chain Specification

## Purpose
TBD - created by archiving change csg-test-characterization. Update Purpose after archive.
## Requirements
### Requirement: CLI explicit path takes highest priority
When an explicit `--config` path is provided, the resolver SHALL use that file regardless of any other discovery strategy.

#### Scenario: CLI path overrides ENV path
- **WHEN** `COLORSCHEME_CONFIG_FILE_PATH` is set to an existing file at an ENV path
- **AND** `--config` is provided pointing to a different existing CLI path
- **THEN** the resolver returns the file from the CLI path
- **AND** `get_resolved_path()` returns the CLI path

### Requirement: ENV path takes second priority
When no explicit CLI path is given, the resolver SHALL check the `COLORSCHEME_CONFIG_FILE_PATH` env var.

#### Scenario: ENV path resolves when CLI path is absent
- **WHEN** `COLORSCHEME_CONFIG_FILE_PATH` is set to an existing file
- **AND** no `--config` CLI option is provided
- **THEN** the resolver returns the file from the ENV path
- **AND** `get_resolved_path()` matches the ENV path

### Requirement: CWD traversal resolves files up to 3 parent levels deep
When no CLI or ENV path is provided, the resolver SHALL search the current working directory and up to 3 parent directories.

#### Scenario: File found in CWD (depth 0)
- **WHEN** a `settings.toml` file exists in the current working directory
- **AND** no `--config` or `COLORSCHEME_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file in CWD

#### Scenario: File found 1 parent level up (depth 1)
- **WHEN** a `settings.toml` file exists in the immediate parent of CWD
- **AND** none exists in CWD itself
- **AND** no `--config` or `COLORSCHEME_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file in the parent directory

#### Scenario: File found 2 parent levels up (depth 2)
- **WHEN** a `settings.toml` file exists 2 parent levels above CWD
- **AND** none exists in CWD or 1 level up
- **AND** no `--config` or `COLORSCHEME_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file 2 levels above

#### Scenario: File found 3 parent levels up (depth 3)
- **WHEN** a `settings.toml` file exists 3 parent levels above CWD
- **AND** none exists in CWD or 1-2 levels up
- **AND** no `--config` or `COLORSCHEME_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file 3 levels above

#### Scenario: File not found at depth 4, falls through to XDG
- **WHEN** a `settings.toml` file exists 4 parent levels above CWD
- **AND** none exists in CWD or 1-3 levels up
- **AND** no `--config` or `COLORSCHEME_CONFIG_FILE_PATH` is set
- **THEN** the resolver does NOT find the file at depth 4 (falls through to XDG)

### Requirement: XDG config directory is used as fallback
When no file is found via CLI, ENV, or CWD traversal, the resolver SHALL check the XDG config directory for `color-scheme-generator/settings.toml`.

#### Scenario: Standard XDG path is used
- **WHEN** no `settings.toml` exists at any CLI/ENV/CWD path
- **AND** `XDG_CONFIG_HOME` points to a directory containing `color-scheme-generator/settings.toml`
- **THEN** the resolver finds the file at the XDG path

#### Scenario: XDG honors a custom XDG_CONFIG_HOME
- **WHEN** `XDG_CONFIG_HOME` is set to a custom directory
- **AND** a file exists at `<XDG_CONFIG_HOME>/color-scheme-generator/settings.toml`
- **AND** no CLI/ENV/CWD file is found
- **THEN** the resolver finds the file at the custom XDG path

### Requirement: Package-bundled defaults are the final fallback
When no file is found by any other strategy, the resolver SHALL fall back to the package-bundled default file.

#### Scenario: Package default is used when nothing else matches
- **WHEN** no `settings.toml` exists at any CLI/ENV/CWD/XDG path
- **THEN** the resolver uses the package-bundled defaults

### Requirement: COLORSCHEME__SECTION__KEY ENV overrides apply after resolution
After the config file is resolved, the resolver SHALL apply ENV-based field overrides using the double-underscore nesting convention with prefix `COLORSCHEME`.

#### Scenario: ENV override changes runtime mode
- **WHEN** `COLORSCHEME__RUNTIME__MODE=container` is set
- **AND** the resolved settings.toml has `runtime.mode = "local"`
- **THEN** `settings.runtime.mode` is `"container"` after resolution

#### Scenario: ENV override changes container engine
- **WHEN** `COLORSCHEME__CONTAINER__ENGINE=podman` is set
- **AND** the resolved settings.toml has `container.engine = "docker"`
- **THEN** `settings.container.engine` is `"podman"` after resolution

#### Scenario: ENV override changes output directory
- **WHEN** `COLORSCHEME__OUTPUT__DIRECTORY=/custom/out` is set
- **AND** the resolved settings.toml has a different `output.directory`
- **THEN** `settings.output.directory` is `/custom/out` after resolution

### Requirement: cli_overrides take precedence over ENV overrides
When both `cli_overrides` and ENV overrides target the same field, the CLI override SHALL win.

#### Scenario: cli_overrides beat ENV overrides
- **WHEN** `COLORSCHEME__RUNTIME__MODE=container` is set
- **AND** `cli_overrides={"runtime.mode": "local"}` is passed to `resolve()`
- **THEN** `settings.runtime.mode` is `"local"` (CLI override wins)

