## 1. Shared package: encoder leniency

- [x] 1.1 Update `src/shared/cli-output/src/cli_output/adapters/output/json_renderer.py` `_CustomEncoder.default` to fall back to `str(o)` for non-Path/Enum objects
- [x] 1.2 Run `src/shared/cli-output` test suite — all pass (62)

## 2. WEG: renderer-backed output adapters

- [x] 2.1 Create `src/wallpaper_effects_generator/adapters/output/base.py` with `OutputAdapterBase` holding a `cli_output.Renderer` (default via `_default_format` + `create_renderer`)
- [x] 2.2 Create `src/wallpaper_effects_generator/adapters/output/projectors.py` with `project_result` (ResultView), `project_batch` (CustomView), `project_catalog` (CustomView), `project_config_info` (CustomView), `project_error` (ErrorView), `project_message` (MessageView)
- [x] 2.3 Rewrite `json_output.py`/`plain_output.py`/`rich_output.py` as subclasses of `OutputAdapterBase` with `_default_format` set
- [x] 2.4 Update `factory.create_output_adapter` to build the shared renderer via `cli_output.create_renderer` and inject it; keep `console` forwarding for rich
- [x] 2.5 Preserve `dump_config_template`/`dump_effects_template` as verbatim raw writes (format override)

## 3. CSG: renderer-backed output adapters

- [x] 3.1 Create `src/color_scheme_generator/adapters/output/base.py` with `OutputAdapterBase` holding a `cli_output.Renderer`; preserve `_verbosity` attribute and QUIET short-circuit on `process_result`
- [x] 3.2 Create `src/color_scheme_generator/adapters/output/projectors.py` with `project_result` (CustomView), `project_error` (ErrorView + `_error_details`), `project_palette` (CustomView), `project_message`, `project_config_info`, `project_install`/`project_uninstall`, `project_version`, `project_backends`
- [x] 3.3 Rewrite `json_output.py`/`plain_output.py`/`rich_output.py` as subclasses of `OutputAdapterBase`
- [x] 3.4 Update `factory.create_output_adapter` to build the shared renderer and inject it; keep `verbosity` forwarding

## 4. Tests: canonical shapes

- [x] 4.1 WEG `tests/unit/adapters/output/test_json_output.py`: `status` → `success`; error envelope `kind`/`message`
- [x] 4.2 WEG `tests/unit/adapters/output/test_plain_output.py`: `success: true`; error to stderr
- [x] 4.3 WEG `tests/unit/adapters/output/test_rich_output.py`: `Failure` text; error to stderr
- [x] 4.4 WEG `tests/unit/cli/test_process_commands.py`: `data["success"] is True`
- [x] 4.5 CSG `tests/unit/adapters/output/test_json_output.py`: error envelope `kind`/`message`/`details`
- [x] 4.6 CSG `tests/unit/adapters/output/test_plain_output.py`: error to stderr, `error: {kind}: {message}` format
- [x] 4.7 CSG `tests/unit/adapters/output/test_rich_output.py`: error to stderr
- [x] 4.8 CSG `tests/unit/adapters/test_error_mapping.py`: `kind`/`message`
- [x] 4.9 CSG `tests/unit/adapters/test_container_processor.py`: use realistic `GenerationResult` for mocked processor results
- [x] 4.10 CSG `tests/unit/cli/test_first_run.py`: mocked processor returns a real `GenerationResult`
- [x] 4.11 CSG `tests/unit/cli/test_generate.py`, `test_generate_full.py`, `test_show.py`: error envelope `kind`/`message`

## 5. Verification

- [x] 5.1 `src/shared/cli-output` pytest — 62 passed
- [x] 5.2 `src/cli-tools/wallpaper-effects-generator` pytest — 322 passed
- [x] 5.3 `src/cli-tools/color-scheme-generator` pytest — 550 passed
- [x] 5.4 `ruff check` + `ruff format --check` clean on all new/changed files (remaining findings are pre-existing typer `B008` etc.)
- [x] 5.5 `weg --output-format json dump-config` and `csg --output-format json dump-config` print raw TOML (format override verified)
