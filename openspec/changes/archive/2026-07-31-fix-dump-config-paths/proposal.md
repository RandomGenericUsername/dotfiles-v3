## Why

The `dump-config` command requires the user to pass the full file path (e.g. `--output ./settings.toml`) instead of accepting a directory (e.g. `--output ./`) and automatically writing the default filename. The sibling project `wallpaper-effects-generator` handles this correctly. Additionally, `dump-config` fails to forward `--config` and CLI override arguments to the config resolver, making it ignore user-specified config paths.

## What Changes

- `dump-config` file output: detect when `--output` points to a directory and append `settings.toml`
- `dump-templates` file output: detect when `--output` points to a directory and append default filename
- `dump-config` config resolution: forward `config_path` and `cli_overrides` to the config resolver
- `dump-templates` template directory resolution: forward settings context and fix XDG path inconsistency

## Capabilities

### New Capabilities
- `path-default-filename`: Auto-append default filename when user provides a directory path as `--output`

### Modified Capabilities
*(none — no existing spec files are changing)*

## Impact

- **Files**: `dump_config_cmd.py`, `dump_templates_cmd.py` in `color-scheme-generator`
- **Behavior**: `--output ./` now writes `./settings.toml` instead of erroring
- **Config**: `csg --config /path/to/settings.toml dump-config` now respects the explicit `--config` flag
