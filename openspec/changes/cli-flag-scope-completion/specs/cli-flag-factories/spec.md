## ADDED Requirements

### Requirement: Shared option definitions for CONFIG, TEMPLATES_DIR, EFFECTS

Each tool SHALL extend its `cli/options.py` module with additional shared `typer.Option` constants.

CSG SHALL add:
- `CONFIG_OPT`: `typer.Option(None, "--config", help="Path to settings.toml config file", exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)`
- `TEMPLATES_DIR_OPT`: `typer.Option(None, "--templates-dir", help="Path to directory containing .j2 template files", exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True)`

WEG SHALL add:
- `CONFIG_OPT`: `typer.Option(None, "--config", "-c", help="Path to settings.toml config file", exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)`
- `EFFECTS_OPT`: `typer.Option(None, "--effects", "-e", help="Path to effects.yaml file", exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)`

Both SHALL default to `None` (optional — the tool discovers the resource from the resolution chain when omitted).

#### Scenario: CONFIG_OPT is imported by leaf command

- **WHEN** `csg info` imports `from .options import CONFIG_OPT`
- **THEN** `CONFIG_OPT` is a `typer.Option` that typer recognizes as a `--config` CLI option with `exists=True` validation
- **WHEN** a user passes `--config /nonexistent/path`
- **THEN** typer returns a file-not-found error (before the command runs)

#### Scenario: EFFECTS_OPT is used by sub-typer callback

- **WHEN** `weg process` sub-typer callback declares `effects: Path | None = EFFECTS_OPT`
- **THEN** every leaf under `process` inherits `--effects`/`-e` at the sub-typer level
