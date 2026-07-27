## 1. Fix dump-config path detection

- [x] 1.1 Add `.suffix` check in `dump_config_cmd.py` — when `output` has no file extension, append `/settings.toml`
- [x] 1.2 Add `mkdir(parents=True, exist_ok=True)` before writing to ensure parent directory exists
- [x] 1.3 Update `--output` option help text to reflect directory support

## 2. Fix dump-config config forwarding

- [x] 2.1 Forward `config_path` from `ctx.obj.get("config_path")` to `config_resolver.resolve()`
- [x] 2.2 Forward `cli_overrides` from `ctx.obj.get("cli_overrides", {})` to `config_resolver.resolve()`

## 3. Fix dump-templates path and XDG consistency

- [x] 3.1 Add `.suffix` check in `dump_templates_cmd.py` — when `output` has no file extension, append `/templates` (directory of templates)
- [x] 3.2 Fix fallback XDG path from `~/.config/color-scheme-generator/templates` to `~/.config/color-scheme/templates`
- [x] 3.3 Add `parent.mkdir(parents=True, exist_ok=True)` call where missing

## 4. Verify and test

- [x] 4.1 Run existing unit tests for dump commands to check for regressions
- [x] 4.2 Manually verify: `csg dump-config --output ./` creates `./settings.toml`
- [x] 4.3 Manually verify: `csg --config ./custom.toml dump-config --output ./out.toml` uses custom config
- [x] 4.4 Manually verify: `csg dump-templates --output ./` creates `./templates/` with `.j2` files
