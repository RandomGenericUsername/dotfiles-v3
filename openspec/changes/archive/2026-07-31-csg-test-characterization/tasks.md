## 1. Remove Inert min/max Catalog Range Fields

- [x] 1.1 Delete `min`/`max` field declarations from `adapters/schemas/backends_catalog_schema.py` (`BackendParameterSchema`)
- [x] 1.2 Delete the `min:`/`max:` lines from `defaults/backends.yaml` (saturation ×3, n_clusters ×1)
- [x] 1.3 Update `tests/unit/adapters/schemas/test_backends_catalog_schema.py`: pin the new contract — schema no longer accepts `min`/`max`; valid catalog loads and round-trips `name`/`type_`/`choices`/`default`/`required` only
- [x] 1.4 Verify `--param saturation=0.6` still applies correctly end-to-end (working behavior stays pinned) and `--param saturation=99.0` is accepted by the CLI (no range check) and clamped by the backend to `1.0`

## 2. Add Test Seam via CliDependencies.processor

- [x] 2.1 In `cli/main.py` `generate`: add `if deps.processor is not None: processor = deps.processor` short-circuit before the existing `RuntimeMode.CONTAINER` branch
- [x] 2.2 In `cli/_helpers.py` `resolve_processor`: add `if deps.processor is not None: return deps.processor` at function top
- [x] 2.3 Verify production path unchanged: `csg version` and `csg info` work normally with `deps.processor` unset

## 3. Add FakeProcessor + Fixtures in conftest

- [x] 3.1 Create `tests/conftest.py` with `FakeProcessor` (duck-typed to `ColorSchemeProcessorPort`): records `process_generate`/`process_show` calls with arguments, writes dummy files at requested output paths, returns a `GenerationResult` with a valid 16-color `ColorScheme`
- [x] 3.2 Add a fixture `cli_deps_with_processor` that returns `CliDependencies(processor=fake_processor, ...)` with the other deps stubbed
- [x] 3.3 Verify the fake is protocol-conformant against `ColorSchemeProcessorPort`

## 4. Rewrite CLI Command Tests with Fakes

- [x] 4.1 Rewrite `tests/unit/cli/test_generate.py` + `test_generate_full.py`: drive real `app` via `CliRunner`, inject `FakeProcessor` through `CliDependencies(processor=...)`, assert exit code 0 and dummy files under `tmp_path`; `--backend`/`--param`/`--format`/`--output-dir` flag resolution and error paths
- [x] 4.2 Rewrite `tests/unit/cli/test_show.py`: drive real `app`, assert `process_result` output (not `palette_display`), invalid-image exit 1, flags absent (format/output-dir/dry-run)
- [x] 4.3 Rewrite `tests/unit/cli/test_info_command.py`: drive real `app`, assert JSON stdout keys (`settings`/`backends`), `--config` explicit path, rich/plain output support, `ConfigResolutionError` handling
- [x] 4.4 Rewrite `tests/unit/cli/test_dump_config_command.py` and `test_dump_templates_command.py`: real `app`, valid TOML stdout, `--output` file-write, overwrite behavior, `--config` rejection on dump-config
- [x] 4.5 Rewrite `tests/unit/cli/test_list_backends_command.py`: real `app`, JSON lists custom/pywal/wallust with availability + parameters, rich/plain support, missing-catalog graceful handling
- [x] 4.6 Rewrite `tests/unit/cli/test_install_command.py` + `test_uninstall_command.py`: real `app`, patch `shutil.which`/`subprocess.run` at the process boundary, `--dry-run` skips build, `--yes` skips prompt, error exit paths
- [x] 4.7 Add/verify `version`, `--help`, completion option (`--install-completion`/`--show-completion`) tests
- [x] 4.8 Add global flag tests: `--output-format json|rich|plain`, `-q`/`--quiet`, `-v`/`--verbose`
- [x] 4.9 Add error-path tests: missing input file, missing `--config`, invalid backend, container-runtime-unavailable via `map_oci_error`
- [x] 4.10 Add lazy-construction + runtime-mode resolution tests: processor built at command execution (not dep build), `--runtime`/`--container-engine` resolve effective mode
- [x] 4.11 Delete `tests/test_user_journey.sh`

## 5. Add Resolution Chain and ENV Override Coverage

- [x] 5.1 Create `tests/unit/adapters/settings/test_config_resolution_chain.py` with CLI-path-prevails test
- [x] 5.2 Add ENV-path-takes-second-priority test (`COLORSCHEME_CONFIG_FILE_PATH`)
- [x] 5.3 Add CWD traversal tests (depth 0/1/2/3 found, depth 4 falls through to XDG)
- [x] 5.4 Add XDG resolution tests (standard `~/.config/color-scheme-generator/`, custom `XDG_CONFIG_HOME`)
- [x] 5.5 Add package-default fallback test (no file found anywhere → bundled defaults used)
- [x] 5.6 Add `COLORSCHEME__SECTION__KEY` ENV override tests (`runtime.mode`, `container.engine`, `output.directory`)
- [x] 5.7 Add `cli_overrides` precedence test (CLI overrides beat ENV overrides)

## 6. Harden Container Mount Plan Tests

- [x] 6.1 Create `_FakeContainerRuntime` in `tests/unit/adapters/test_container_processor.py`: records `last_run_config`, configurable `image_exists()`, writes dummy output at mapped `/output` source path
- [x] 6.2 Replace mock-runtime usage with the recording fake
- [x] 6.3 Assert all 4 mounts (generate) with correct `source`/`target`/`read_only`
- [x] 6.4 Assert `process_show` mounts 3 (no `/output`)
- [x] 6.5 Assert run config `environment == _CONTAINER_ENV`
- [x] 6.6 Assert serialized temp settings.toml is valid TOML with `runtime.mode = "local"`
- [x] 6.7 Assert cleanup on success and exception
- [x] 6.8 Assert `ContainerImageNotFoundError` when `image_exists()` returns `False`
- [x] 6.9 Assert input-parent-is-`/` rejection (no run submitted)
- [x] 6.10 Add interface-contract test: adapter's inner argv for generate and show round-trips through the live Typer `app` (exit code 0)

## 7. Add Remaining Module Coverage

- [x] 7.1 Add direct schema validator tests in `tests/unit/adapters/settings/test_schema.py`: engine whitelist (docker/podman/invalid), `auto` backend rejection, `memory_limit` shape, timeout `<0` rejection, nested composite propagation
- [x] 7.2 Fill output-adapter `config_info`/catalog-display gaps in `test_rich_output.py`/`test_plain_output.py`/`test_json_output.py` (verify `config_info` signatures match `OutputPort`)
- [x] 7.3 Verify `error_mapping.py` is fully covered (one test per `oci_runtime` exception type → `ColorSchemeError`)

## 8. Flag Known Bugs as XFail Tests

- [x] 8.1 Add xfail test: schema accepts arbitrary `default_formats` strings (e.g. `["weird"]`); asserts schema rejects invalid `ColorFormat` values
- [x] 8.2 Add xfail test: `--help` text omits the CLI `--config` priority step (lists 4 strategies, code has 5); asserts help text reflects all 5
- [x] 8.3 Add xfail test: `BackendDefinition.min_version` hardcoded to `"0.0.0"` regardless of YAML; asserts it round-trips if declared
- [x] 8.4 Add xfail test: `install`/`uninstall`/`version`/`list-backends` use `isinstance` dispatch bypassing `OutputPort`; asserts they route through the port abstraction

## 9. Verify Final State

- [x] 9.1 Run `pytest src/cli-tools/color-scheme-generator/tests/ -q` — all non-xfail tests pass, no collection errors
- [x] 9.2 Run `pytest src/cli-tools/color-scheme-generator/tests/ -q -rxX` — all xfails report as expected
- [x] 9.3 Run `ruff check src/cli-tools/color-scheme-generator/` — no new lint violations
- [x] 9.4 Run `ruff format --check src/cli-tools/color-scheme-generator/` — formatting clean
- [x] 9.5 Run `pytest src/cli-tools/wallpaper-effects-generator/tests/ -q` — WEG suite still green (no shared `config-assembler-engine`/`oci-runtime` regression)
- [x] 9.6 Verify `tests/test_user_journey.sh` is deleted and its assertions are preserved by per-command CliRunner tests
