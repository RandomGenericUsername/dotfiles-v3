## MODIFIED Requirements

### Requirement: Root callback declares only cross-cutting flags

The root callback SHALL declare only the cross-cutting flags `--output-format` (output serialization), `--verbose`/`-v` (logging), and `--quiet`/`-q` (logging). All other flags SHALL be declared at leaf or sub-typer scope.

**Previous (after `cli-flag-scope-refinement`):** Root callback declared `--output-format`, `--config`, `--templates-dir` (CSG) or `--config`, `--effects` (WEG), plus `--verbose`/`--quiet`.

#### Scenario: CSG root --help shows only output-format, verbose, quiet

- **WHEN** `csg --help` is run
- **THEN** global options section shows only `--output-format`, `--verbose`/`-v`, `--quiet`/`-q`
- **THEN** `--config`, `--templates-dir`, `--runtime`, `--container-engine` are NOT in global options

#### Scenario: WEG root --help shows output-format, verbose, quiet

- **WHEN** `weg --help` is run
- **THEN** global options section shows only `--output-format`, `--verbose`/`-v`, `--quiet`/`-q`
- **THEN** `--config`, `--effects`, `--runtime`, `--container-engine` are NOT in global options

### Requirement: Config flag scope

**Updated.** `--config` SHALL be accepted only by commands that resolve settings.

**CSG `--config` consumers:** `generate`, `show`, `info`, `install`, `uninstall`.
**WEG `--config` consumers:** `process` sub-typer, `batch` sub-typer, `info`, `install`, `uninstall`.

#### Scenario: csg generate accepts --config

- **WHEN** `csg generate img.png --config /my/settings.toml` is run
- **THEN** config is resolved from `/my/settings.toml`

#### Scenario: csg dump-config rejects --config

- **WHEN** `csg dump-config --config /my/settings.toml` is run
- **THEN** typer returns a parse error: `Error: no such option: --config`

#### Scenario: weg show effects rejects --config

- **WHEN** `weg show effects --config /my/settings.toml` is run
- **THEN** typer returns a parse error: `Error: no such option: --config`

### Requirement: Templates-dir flag scope (CSG only)

**Updated.** `--templates-dir` SHALL be accepted only by commands that use the template renderer or display templates resolution.

**CSG `--templates-dir` consumers:** `generate`, `show`, `info`.

#### Scenario: csg generate accepts --templates-dir

- **WHEN** `csg generate img.png --templates-dir /custom/templates` is run
- **THEN** the renderer uses templates from `/custom/templates`

#### Scenario: csg info accepts --templates-dir

- **WHEN** `csg info --templates-dir /custom/templates` is run
- **THEN** info displays the templates source as `/custom/templates`

#### Scenario: csg install rejects --templates-dir

- **WHEN** `csg install --templates-dir /custom/templates` is run
- **THEN** typer returns a parse error: `Error: no such option: --templates-dir`

### Requirement: Effects flag scope (WEG only)

**Updated.** `--effects` SHALL be accepted only by commands that load the effects catalog.

**WEG `--effects` consumers:** `process` sub-typer, `batch` sub-typer, `show` sub-typer, `info`.

#### Scenario: weg process accepts --effects at sub-typer level

- **WHEN** `weg process --effects /my/effects.yaml effect blur img.png` is run
- **THEN** effects are loaded from `/my/effects.yaml`

#### Scenario: weg show effects accepts --effects

- **WHEN** `weg show effects --effects /my/effects.yaml` is run
- **THEN** the catalog is loaded from `/my/effects.yaml`

#### Scenario: weg install rejects --effects

- **WHEN** `weg install --effects /my/effects.yaml` is run
- **THEN** typer returns a parse error: `Error: no such option: --effects`

### Requirement: Show sub-typer callback (WEG)

**ADDED.** WEG's `show_app` SHALL have a `@show_app.callback()` that declares `--effects`/`-e` as an option. All `show` leaves (effects, composites, presets, all) SHALL inherit this option.

#### Scenario: show effects loads from explicit --effects path

- **WHEN** `weg show effects --effects /my/effects.yaml` is run
- **THEN** `_load_catalog` receives `/my/effects.yaml` from `ctx.obj["effects"]`
- **THEN** catalog is loaded from `/my/effects.yaml`

### Requirement: CSG dump-config aligns with WEG

**ADDED.** CSG `dump-config` SHALL print the bundled default `settings.toml` from package resources, matching WEG's `dump-config` behavior. It SHALL NOT resolve config, SHALL NOT read `ctx.obj["config_path"]`, and SHALL NOT accept `--config`.

#### Scenario: dump-config prints bundled default

- **WHEN** `csg dump-config` is run
- **THEN** the output contains the exact content of the bundled `defaults/settings.toml`
- **THEN** no config resolution occurs

### Requirement: CSG install/uninstall honor --config

**ADDED.** `csg install` and `csg uninstall` SHALL accept `--config` as a leaf option and SHALL pass the config path to `config_resolver.resolve(explicit_path=...)`.

#### Scenario: install uses --config to resolve settings

- **WHEN** `csg install --config /my/settings.toml --container-engine podman` is run
- **THEN** settings are resolved from `/my/settings.toml`
- **THEN** the container image is built using the resolved `image_prefix` and `image_tag` from that settings file
- **THEN** the previously missing config fallback bug is fixed

## REMOVED Requirements

### Requirement: Config flag on CSG dump-config

**Reason:** CSG `dump-config` no longer resolves config. It prints the bundled default template. `--config` would be meaningless.

**Migration:** `csg dump-config --config /path/to.toml` becomes invalid. Use `csg info --config /path/to.toml` to inspect resolved settings.

### Requirement: Effects flag on WEG dump-config and dump-effects

**Reason:** Both commands print bundled default templates and do not load the effects catalog. `--effects` would be meaningless.

**Migration:** `weg dump-config --effects /path/effects.yaml` becomes invalid.

### Requirement: Config flag on WEG show sub-typer

**Reason:** WEG `show` does not resolve settings — it only loads the effects catalog via `effect_loader.load()`. `--config` would be silently ignored.

**Migration:** `weg show effects --config /path/to.toml` becomes invalid. Show uses `--effects` only.
