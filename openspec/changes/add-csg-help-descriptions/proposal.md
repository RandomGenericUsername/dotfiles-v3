## Why

`csg --help` lists all commands but shows no descriptions next to them:

```
╭─ Commands ───────────────────────────────────────────────────╮
│ generate                                                     │
│ info                                                         │
│ dump-config                                                   │
│ dump-templates                                                │
│ install                                                      │
│ list-backends                                                │
│ show                                                         │
│ uninstall                                                    │
│ version                                                      │
╰──────────────────────────────────────────────────────────────╯
```

Per-command help is equally bare — `csg info --help` shows `Usage:` and `--help` with no explanation of what the command does. Users have to guess or check the README.

In Typer, each command's short description comes from either a function docstring or the `help=` parameter of `@app.command()`. Currently none of the 9 commands provide either.

## What Changes

Add a short `help=` description to each of the 9 commands. No functional changes.

### Commands and descriptions

| Command | Description |
|---------|-------------|
| `generate` | Extract a color palette from an image |
| `show` | Display a color palette preview in the terminal |
| `info` | Show system configuration, backends, and sources |
| `install` | Build container images for extraction backends |
| `uninstall` | Remove container images for extraction backends |
| `list-backends` | List available extraction backends and their status |
| `dump-config` | Print or save current settings to a TOML file |
| `dump-templates` | Copy bundled Jinja2 templates to a local directory |
| `version` | Show the installed package version |

### How

Two approaches are equivalent in Typer — pick one consistently:

**Option A** — docstrings:
```python
def info(ctx: typer.Context) -> None:
    """Show system configuration, backends, and sources."""
    ...

app.command()(info)
```

**Option B** — help parameter:
```python
app.command(help="Show system configuration, backends, and sources")(info)
```

## Capabilities

### New Capabilities

- `help-text-display`: Each csg command has a short description visible in `csg --help` and `csg <command> --help`.

### Modified Capabilities

*(none)*

## Impact

- **Files**: `main.py` (9 registration lines or 8 function files + `generate` inline) — cosmetic only
- **Tests**: none needed
- **Docs**: none needed
