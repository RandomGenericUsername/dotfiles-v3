## ADDED Requirements

### Requirement: Centralized option definitions

Each tool SHALL provide a `cli/options.py` module that exports `typer.Option` instances for `--runtime` and `--container-engine` as reusable constants.

- `RUNTIME_OPT`: `typer.Option(None, "--runtime", "-r", help="Execution runtime mode", case_sensitive=False)`
- `ENGINE_OPT`: `typer.Option(None, "--container-engine", help="Container engine to use (only for container runtime)", case_sensitive=False)`

Both MUST default to `None` (optional — TOML/ENV is the baseline when the flag is omitted).

#### Scenario: Shared option is imported by leaf command

- **WHEN** a leaf command module imports `from .options import RUNTIME_OPT`
- **THEN** `RUNTIME_OPT` is a `typer.Option` instance that typer's signature introspection recognizes as a CLI option

#### Scenario: Same option instance can be used by multiple commands

- **WHEN** both `csg generate` and `weg process` sub-typer callback declare `runtime: RuntimeMode = RUNTIME_OPT`
- **THEN** each command independently parses its own `--runtime` value — no shared mutable state

#### Scenario: Options use None as default

- **WHEN** a user does not pass `--runtime` on the CLI
- **THEN** the parameter value is `None`, and the command falls back to TOML/ENV config value
- **WHEN** a user passes `--runtime container`
- **THEN** the parameter value is `RuntimeMode.CONTAINER`, overriding TOML/ENV

### Requirement: Single source of truth for option metadata

The `cli/options.py` module SHALL be the only place where `--runtime` and `--container-engine` option definitions (help text, type, default, validation) are declared.

#### Scenario: Help text is consistent across all consumers

- **WHEN** a user runs any command that exposes `--runtime`
- **THEN** the help text for `--runtime` is identical across all such commands

#### Scenario: Default change propagates to all consumers

- **WHEN** the default value of `RUNTIME_OPT` is changed in `cli/options.py`
- **THEN** every command that imports `RUNTIME_OPT` automatically picks up the new default
