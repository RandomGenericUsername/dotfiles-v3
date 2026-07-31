# WEG Config Resolution Chain

## Why

The CLI help text documents a 4-level discovery chain for both `settings.toml` and `effects.yaml`:
1. CLI path (`--config` / `--effects`)
2. ENV path (`WALLPAPER_CONFIG_FILE_PATH` / `WALLPAPER_EFFECTS_CONFIG_FILE_PATH`)
3. CWD traversal (up to 2 parent levels)
4. XDG default (`~/.config/weg/settings.toml`)
5. Package-bundled defaults

Additionally, `WALLPAPER__SECTION__KEY` double-underscore naming provides ENV-based field overrides. This entire chain has zero test coverage.

## ADDED Requirements

### Requirement: CLI explicit path takes highest priority
When an explicit `--config` or `--effects` path is provided, the resolver SHALL use that file regardless of any other discovery strategy.

#### Scenario: CLI path overrides ENV path
- **WHEN** `WALLPAPER_CONFIG_FILE_PATH` is set to an existing file at `/env/path/settings.toml`
- **AND** `--config /cli/path/settings.toml` is provided pointing to a different existing file
- **THEN** the resolver returns the file from `/cli/path/settings.toml`
- **AND** `get_resolved_path()` returns `/cli/path/settings.toml`

### Requirement: ENV path takes second priority
When no explicit CLI path is given, the resolver SHALL check `WALLPAPER_CONFIG_FILE_PATH` (settings) or `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` (effects) env vars.

#### Scenario: ENV path resolves when CLI path is absent
- **WHEN** `WALLPAPER_CONFIG_FILE_PATH` is set to an existing file
- **AND** no `--config` CLI option is provided
- **THEN** the resolver returns the file from the ENV path
- **AND** `get_resolved_path()` matches the ENV path

### Requirement: CWD traversal resolves files up to 2 parent levels deep
When no CLI or ENV path is provided, the resolver SHALL search the current working directory and up to 2 parent directories.

#### Scenario: File found in CWD
- **WHEN** a `settings.toml` file exists in the current working directory
- **AND** no `--config` or `WALLPAPER_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file in CWD

#### Scenario: File found 1 parent level up
- **WHEN** a `settings.toml` file exists in the immediate parent of CWD
- **AND** none exists in CWD itself
- **AND** no `--config` or `WALLPAPER_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file in the parent directory

#### Scenario: File found 2 parent levels up
- **WHEN** a `settings.toml` file exists 2 parent levels above CWD
- **AND** none exists in CWD or 1 level up
- **AND** no `--config` or `WALLPAPER_CONFIG_FILE_PATH` is set
- **THEN** the resolver finds the file 2 levels above

#### Scenario: File not found at depth 3, falls through to XDG
- **WHEN** a `settings.toml` file exists 3 parent levels above CWD
- **AND** none exists in CWD or 1-2 levels up
- **AND** no `--config` or `WALLPAPER_CONFIG_FILE_PATH` is set
- **THEN** the resolver does NOT find the file at depth 3 (falls through to XDG)

### Requirement: XDG config directory is used as fallback
When no file is found via CLI, ENV, or CWD traversal, the resolver SHALL check `~/.config/weg/settings.toml` (or `$XDG_CONFIG_HOME/weg/settings.toml`).

#### Scenario: XDG file is used when no other strategy matches
- **WHEN** no `settings.toml` exists at any CLI/ENV/CWD path
- **AND** a file exists at `~/.config/weg/settings.toml` (via `XDG_CONFIG_HOME`)
- **THEN** the resolver finds the file at the XDG path

#### Scenario: XDG honors XDG_CONFIG_HOME env var
- **WHEN** `XDG_CONFIG_HOME` is set to `/custom/xdg`
- **AND** a file exists at `/custom/xdg/weg/settings.toml`
- **AND** no CLI/ENV/CWD file is found
- **THEN** the resolver finds the file at `/custom/xdg/weg/settings.toml`

### Requirement: Package-bundled defaults are the final fallback
When no file is found by any other strategy, the resolver SHALL return the package-bundled default file.

#### Scenario: Package default is used when nothing else matches
- **WHEN** no `settings.toml` exists at any CLI/ENV/CWD/XDG path
- **THEN** the resolver returns the package-bundled defaults
- **AND** `get_resolved_path()` returns `None` (no real file path)

### Requirement: Effects resolution follows the same priority chain
The effects file (`effects.yaml`) resolver SHALL use the identical priority chain with prefix `WALLPAPER_EFFECTS`.

#### Scenario: Effects ENV path takes priority over CWD
- **WHEN** `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` is set to an existing file
- **AND** no `--effects` CLI option is provided
- **AND** a different `effects.yaml` exists in CWD
- **THEN** the effects loader returns the file from the ENV path

### Requirement: WALLPAPER__SECTION__KEY ENV overrides apply after resolution
After the config file is resolved, the resolver SHALL apply ENV-based field overrides using the double-underscore nesting convention.

#### Scenario: ENV override changes runtime mode
- **WHEN** `WALLPAPER__RUNTIME__MODE=container` is set
- **AND** the resolved settings.toml has `runtime.mode = "local"`
- **THEN** `settings.runtime.mode` is `"container"` after resolution

#### Scenario: ENV override changes container engine
- **WHEN** `WALLPAPER__CONTAINER__ENGINE=podman` is set
- **AND** the resolved settings.toml has `container.engine = "docker"`
- **THEN** `settings.container.engine` is `"podman"` after resolution

#### Scenario: ENV override changes output directory
- **WHEN** `WALLPAPER__OUTPUT__DIRECTORY=/custom/out` is set
- **AND** the resolved settings.toml has `output.directory = "/tmp/wallpaper-effects"`
- **THEN** `settings.output.directory` is `"/custom/out"` after resolution

#### Scenario: cli_overrides take precedence over ENV overrides
- **WHEN** `WALLPAPER__RUNTIME__MODE=container` is set
- **AND** `cli_overrides={"runtime.mode": "local"}` is passed to `resolve()`
- **THEN** `settings.runtime.mode` is `"local"` (CLI override wins)
