## 1. Option Factories

- [x] 1.1 Create `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/options.py` with `RUNTIME_OPT` and `ENGINE_OPT` (both default `None`)
- [x] 1.2 Create `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/options.py` with `RUNTIME_OPT` and `ENGINE_OPT` (both default `None`)

## 2. Add Flags to Leaves (CSG)

- [x] 2.1 Add `--runtime` (from `options.RUNTIME_OPT`) and `--container-engine` (from `options.ENGINE_OPT`) to `csg generate` in `cli/main.py`
- [x] 2.2 Add `--container-engine` (from `options.ENGINE_OPT`) to `csg install` in `cli/install_cmd.py`
- [x] 2.3 Add `--container-engine` (from `options.ENGINE_OPT`) to `csg uninstall` in `cli/uninstall_cmd.py`

## 3. Add Flags to Sub-Typers and Leaves (WEG)

- [x] 3.1 Add `--runtime` and `--container-engine` to WEG `process_app` sub-typer callback in `cli/process.py`
- [x] 3.2 Add `--runtime` and `--container-engine` to WEG `batch_app` sub-typer callback in `cli/batch.py`
- [x] 3.3 Add `--container-engine` to `weg install` in `cli/install.py` (or main.py inline)
- [x] 3.4 Add `--container-engine` to `weg uninstall` in `cli/uninstall.py` (or main.py inline)

## 4. Remove Redundant WEG Process Flags

- [x] 4.1 Remove `effect_name`/`-e`/`--effect` override option from `process effect` in `cli/process.py`
- [x] 4.2 Remove `composite_name`/`-c`/`--composite` override option from `process composite` in `cli/process.py`
- [x] 4.3 Remove `preset_name`/`-p`/`--preset` override option from `process preset` in `cli/process.py`
- [x] 4.4 Remove the `name = X_name or name` override logic line from all three `process` command bodies

## 5. Wire CLI Overrides Through Config-Assembler (WEG)

- [x] 5.1 Update `assembled_config_resolver.py` `resolve()` method signature to accept `cli_overrides: dict[str, str] | None = None` parameter
- [x] 5.2 Update the `_assembler.execute()` call in `resolve()` to pass `cli_overrides` through
- [x] 5.3 Update WEG `_resolve_context()` in `cli/process.py` to build `cli_overrides` dict from parsed flags and pass it to `config_resolver.resolve()` instead of post-resolution object mutation
- [x] 5.4 Update `weg info` in `cli/info.py` (or main.py) to pass `cli_overrides` to config resolver if it wasn't already

## 6. Remove Flags from Root Callbacks

- [x] 6.1 Remove `--runtime` parameter from CSG `@app.callback()` in `cli/main.py`
- [x] 6.2 Remove `container_engine` parameter and `cli_overrides["container.engine"]` wiring from CSG `@app.callback()` — `--container-engine` no longer declared at root
- [x] 6.3 Remove `runtime` and `container_engine` parameters and their `ctx.obj` stores from WEG `@app.callback()` in `cli/main.py`
- [x] 6.4 Remove the processor-building block from CSG `@app.callback()` (lines 162-169 in main.py) — handled by build_deps refactor in 7.3

## 7. Lazy Processor Construction (CSG)

- [x] 7.1 Add processor resolution logic to `csg generate` body: read effective runtime (CLI override > TOML/ENV > default), build local or container processor on demand
- [x] 7.2 Add processor resolution logic to `csg show` body: read runtime from resolved config, build processor on demand
- [x] 7.3 Update CSG factory `build_deps()` to remove default `LocalProcessor` from `CliDependencies` — processor is no longer a deps-level concern
- [x] 7.4 Ensure `csg version`, `csg info`, `csg dump-*`, `csg list-backends` work without any processor being built

## 8. Update Tests

- [x] 8.1 `csg/tests/unit/cli/test_runtime_mode.py`: update flag position assertions — flags move from global to `generate` command
- [x] 8.2 `csg/tests/unit/cli/test_install_command.py`: update `--container-engine` position test for `install` leaf
- [x] 8.3 `csg/tests/test_user_journey.sh`: remove `--runtime` from info/help checks; update flag position expectations
- [x] 8.4 `weg/tests/test_cli.py`: update `test_info_command` — remove `--runtime container` from `info` invoke args
- [x] 8.5 `weg/tests/unit/cli/test_process_commands.py`: move `--container-engine` from root-level before `process` to sub-typer position after `process`
- [x] 8.6 Run all existing unit and integration tests to confirm no regressions

## 9. Update Spec Documentation

- [x] 9.1 Update `openspec/specs/cli-runtime-engine-scope/spec.md` Decision section with refined scoping table and shared factory/None-default decisions
- [x] 9.2 Update `openspec/specs/cli-runtime-engine-scope/spec.md` Final Shape section to show corrected CSG show row (remove flags) and add explicit rationale for every exclusion
- [x] 9.3 Verify the spec delta at `openspec/changes/cli-flag-scope-refinement/specs/cli-runtime-engine-scope/spec.md` correctly captures all MODIFIED/REMOVED requirements for archival
