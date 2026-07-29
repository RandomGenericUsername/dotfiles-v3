## 1. Extend option factories (both tools)

- [x] 1.1 Add `CONFIG_OPT`, `TEMPLATES_DIR_OPT` to CSG `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/options.py`
- [x] 1.2 Add `CONFIG_OPT`, `EFFECTS_OPT` to WEG `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/options.py`

## 2. CSG — Add flags to leaves

- [x] 2.1 Add `--config` (from `CONFIG_OPT`) and `--templates-dir` (from `TEMPLATES_DIR_OPT`) to `csg generate` in `cli/main.py`. Replace the current `ctx.obj["config_path"]` and `ctx.obj["templates_dir"]` reads with direct leaf parameter reads. Pass to `config_resolver.resolve(explicit_path=config_path)` and `renderer.update_templates_dir(templates_dir)` respectively.
- [x] 2.2 Add `--config` and `--templates-dir` to `csg show` in `cli/show.py`. Same pattern: pass `config_path` to `config_resolver.resolve(explicit_path=...)` and `templates_dir` to `renderer.update_templates_dir(templates_dir)`.
- [x] 2.3 Add `--config` and `--templates-dir` to `csg info` in `cli/info_cmd.py`. Pass `config_path` to `config_resolver.resolve(explicit_path=...)`. Pass `templates_dir` to `template_dir_resolver.resolve(settings_dir=templates_dir)`.
- [x] 2.4 Add `--config` (from `CONFIG_OPT`) to `csg install` in `cli/install_cmd.py`. **Bug fix:** change `deps.config_resolver.resolve()` to `deps.config_resolver.resolve(explicit_path=config_path)`. Note: `config_path` is now a leaf parameter, not from `ctx.obj`.
- [x] 2.5 Add `--config` (from `CONFIG_OPT`) to `csg uninstall` in `cli/uninstall_cmd.py`. Same bug fix: pass `config_path` to `resolve(explicit_path=...)`.

## 3. CSG — Align dump-config with WEG

- [x] 3.1 Rewrite `cli/dump_config_cmd.py`: change body to read `from importlib.resources import files as resource_files`; read `resource_files("color_scheme_generator.defaults").joinpath("settings.toml").read_text()`; write to `output` path if given, else print to stdout.
- [x] 3.2 Remove `config_resolver`, `cli_overrides`, `config_path`, `SettingsSerializer` logic from dump_config_cmd.py
- [x] 3.3 Update `cli/main.py` dump-config registration: no change needed (command name stays the same, just the implementation changes)

## 4. CSG — Remove flags from root callback

- [x] 4.1 Remove `config_path` Typer option from `@app.callback()` in `cli/main.py`
- [x] 4.2 Remove `templates_dir` Typer option from `@app.callback()` in `cli/main.py`
- [x] 4.3 Remove `ctx.obj["config_path"]` and `ctx.obj["templates_dir"]` assignment from root callback
- [x] 4.4 Update help text: remove "Explicit --config flag" and "Explicit --templates-dir flag" bullets from app description
- [x] 4.5 Remove `_xdg_settings_path` and `_xdg_templates_path` constants if no longer referenced

## 5. WEG — Add flags to process and batch sub-typer callbacks

- [x] 5.1 In `cli/process.py`: add `config: Path | None = CONFIG_OPT` and `effects: Path | None = EFFECTS_OPT` parameters to `process_callback`. Store in `ctx.obj["config"]` and `ctx.obj["effects"]`.
- [x] 5.2 In `cli/batch.py`: add `config` and `effects` parameters to `batch_callback`. Same store pattern.
- [x] 5.3 Confirm `_resolve_context` in `cli/process.py` reads `ctx.obj["config"]` and `ctx.obj["effects"]` transparently (lines 73, 77) — no logic change needed.

## 6. WEG — Add show sub-typer callback

- [x] 6.1 In `cli/show.py`: add `@show_app.callback()` function with `effects: Path | None = EFFECTS_OPT` parameter. Store in `ctx.obj["effects"]`.
- [x] 6.2 Confirm `_load_catalog` in show.py reads `ctx.obj.get("effects")` transparently (line 27) — no logic change needed.

## 7. WEG — Add flags to standalone leaves

- [x] 7.1 Add `--config` (from `CONFIG_OPT`) and `--effects` (from `EFFECTS_OPT`) to `weg info` in `cli/main.py`. Wire to `info_command()` parameters.
- [x] 7.2 Add `--config` (from `CONFIG_OPT`) to `weg install` in `cli/main.py`. Wire to `install_command(config_path=config)`.
- [x] 7.3 Add `--config` (from `CONFIG_OPT`) to `weg uninstall` in `cli/main.py`. Wire to `uninstall_command(config_path=config)`.

## 8. WEG — Remove flags from root callback

- [x] 8.1 Remove `config`/`-c` Typer option from `@app.callback()` in `cli/main.py`
- [x] 8.2 Remove `effects`/`-e` Typer option from `@app.callback()` in `cli/main.py`
- [x] 8.3 Remove `ctx.obj["config"]` and `ctx.obj["effects"]` assignment from root callback
- [x] 8.4 Update help text: remove "Explicit --config flag" and "Explicit --effects flag" bullets; keep config/effects discovery chain bullets for env/traversal/XDG/defaults

## 9. Tests

- [x] 9.1 Run CSG test suite; fix flag-position assertions where tests pass flags globally
- [x] 9.2 Run WEG test suite; fix flag-position assertions (especially `test_process_commands.py`, `test_cli.py`)
- [x] 9.3 Add test: `csg info --config /my/settings.toml` passes config_path to resolver
- [x] 9.4 Add test: `csg install --config /my/settings.toml` passes config_path to resolver (regression)
- [x] 9.5 Add test: `weg show effects --effects /my/effects.yaml` works
- [x] 9.6 Add test: `csg dump-config --config /x` returns parse error (no such option)
- [x] 9.7 Add test: `csg install --templates-dir /x` returns parse error (no such option)
- [x] 9.8 Add test: `weg show effects --config /x` returns parse error (no such option)
- [x] 9.9 Run full test suite for both tools: all pass

## 10. Verify final command shapes

- [x] 10.1 `csg --help` shows only `--output-format`, `-v`, `-q` in global options
- [x] 10.2 `weg --help` shows only `--output-format`, `-v`, `-q` in global options
- [x] 10.3 `csg generate --help` lists `--config`, `--templates-dir`, `--runtime`, `--container-engine`, `--backend`, `--param`, `--format`, `--output-dir`
- [x] 10.4 `csg info --help` lists `--config`, `--templates-dir`
- [x] 10.5 `csg install --help` lists `--config`, `--container-engine`, `--backend`, `--dry-run`
- [x] 10.6 `csg dump-config --help` lists only `--output` (no `--config`)
- [x] 10.7 `weg process --help` lists `--config`, `--effects`, `--runtime`, `--container-engine`
- [x] 10.8 `weg batch --help` lists `--config`, `--effects`, `--runtime`, `--container-engine`
- [x] 10.9 `weg show --help` lists `--effects` (new sub-typer)
- [x] 10.10 `weg info --help` lists `--config`, `--effects`
- [x] 10.11 `weg install --help` lists `--config`, `--container-engine`, `--dump-config`, `--dump-effects`
