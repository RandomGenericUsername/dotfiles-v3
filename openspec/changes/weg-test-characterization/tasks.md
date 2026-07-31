## 1. Fix Suite Collection (dead modules)

- [x] 1.1 Delete `tests/test_factory.py`, `tests/test_ports.py`, `tests/unit/adapters/test_docker_image_manager.py`, `tests/unit/adapters/test_oci_command_runner.py`
- [x] 1.2 Rewrite `tests/test_factory.py` against current factory API: `create_command_runner()` returns `SubprocessCommandRunner`, `create_container_engine()` uses `oci_runtime.RuntimeFactory`, `create_output_adapter()` switches json/rich/plain, `create_config_resolver()`/`create_effect_loader()` wire strategy chains — no `ImageManagerPort` or `OCICommandRunner` references
- [x] 1.3 Rewrite `tests/test_ports.py` against current port set: `CommandRunnerPort`, `ConfigResolverPort`, `EffectLoaderPort`, `EffectProcessorPort`, `ContextValidatorPort`, `OutputPort`, `SettingsSerializerPort`, `EffectsSerializerPort`, `VersionProviderPort` — structural protocol checks only

## 2. Fix Lossy EffectsSerializer

- [x] 2.1 Extend `adapters/serializer/effects_serializer.py:_dict_to_parameter_definition` to read and pass `min`, `max`, `required`, `type` to `ParameterDefinition` constructor
- [x] 2.2 Add round-trip equality test in `tests/unit/adapters/serializer/test_effects_serializer.py`: assert `min`, `max`, `required`, `type` survive serialize → deserialize; include effects with zero-parameter, bounded parameters, required parameters, and all `type` variants

## 3. Add Test Seam in CLI

- [x] 3.1 In `cli/main.py` `@callback`: after building real `CliDependencies`, check `os.environ.get("WEG_TEST_DEPS")`; if truthy, replace `deps` with deps from module-level `_test_deps` variable (or reconstruct from env var content)
- [x] 3.2 Expose `_test_deps: CliDependencies | None = None` module-level variable; setter function `set_test_deps(deps)` that both sets `_test_deps` and the env var
- [x] 3.3 Verify production path unchanged: `weg version` works normally without env var set

## 4. Rewrite CLI Command Tests with Fakes

- [x] 4.1 Create `_FakeProcessor` helper class in test module (or conftest): duck-typed to `EffectProcessorPort`, records calls, writes dummy file at `request.output_path`
- [x] 4.2 Add conftest fixture that injects `_FakeProcessor` via the `WEG_TEST_DEPS` seam and provides record access for assertions
- [x] 4.3 Add smoke tests for all 9 commands (`info`, `dump-config`, `dump-effects`, `version`, `process effect`, `process composite`, `process preset`, `show *`, `batch *`, `install`, `uninstall`) — assert exit_code=0, valid JSON stdout
- [x] 4.4 Add `process effect --param` tests (single, multiple, malformed silent-drop for now as xfail)
- [x] 4.5 Add `dump-config --output` and `dump-effects --output` file-write tests
- [x] 4.6 Add global flag tests (`--output-format json|rich|plain`, `-q`/`--quiet`, `-v`/`--verbose`)
- [x] 4.7 Add error-path tests (missing input file, missing `--config` file, invalid engine name)
- [x] 4.8 Add `show` exception-path test (`_load_catalog` catches any exception → `error` + `Exit(1)`)
- [x] 4.9 Replace `test.sh` characterization assertions with a single `batch all --dry-run` test that asserts 11 total, 11 succeeded, all paths under output dir
- [x] 4.10 Delete `test.sh`

## 5. Add Resolution Chain and ENV Override Coverage

- [x] 5.1 Create `tests/unit/adapters/test_config_resolution_chain.py` with CLI-path-prevails test
- [x] 5.2 Add ENV-path-takes-second-priority test (`WALLPAPER_CONFIG_FILE_PATH`)
- [x] 5.3 Add CWD traversal tests (depth 0 found, depth 1 found, depth 2 found, depth 3 falls through)
- [x] 5.4 Add XDG resolution tests (standard `~/.config/weg/`, custom `XDG_CONFIG_HOME`)
- [x] 5.5 Add package-default fallback test (no file found anywhere → `get_resolved_path()` returns `None`)
- [x] 5.6 Add effects file resolution priority tests (same chain with `WALLPAPER_EFFECTS_CONFIG_FILE_PATH`)
- [x] 5.7 Add `WALLPAPER__SECTION__KEY` ENV override tests (`runtime.mode`, `container.engine`, `output.directory`)
- [x] 5.8 Add `cli_overrides` precedence test (CLI overrides beat ENV overrides)

## 6. Harden Container Mount Plan Tests

- [x] 6.1 Create `_FakeEngine` helper class: recording `last_run_config`, configurable `images.exists()`, `containers.run()` writes dummy output file at mapped `/output` volume path
- [x] 6.2 Replace mock-engine usage in `test_container_processor.py` with `_FakeEngine`
- [x] 6.3 Assert all 4 volume mounts present with correct `source`/`target`/`read_only`
- [x] 6.4 Assert serialized temp TOML is valid and contains `runtime.mode = "local"`
- [x] 6.5 Assert input-parent-is-`/` raises error (no mount plan submitted)
- [x] 6.6 Assert symlink input resolves before mounting
- [x] 6.7 Assert cleanup on success (temp files removed)
- [x] 6.8 Assert cleanup on exception (temp files removed via `finally`)
- [x] 6.9 Assert `ContainerImageNotFoundError` when `engine.images.exists()` returns `False`

## 7. Add Remaining Module Coverage

- [x] 7.1 Add `settings_schema.py` validator tests (engine whitelist rejects bad engine, registry slash-strip works)
- [x] 7.2 Add `rich_output.catalog_list` and `config_info` coverage in `test_rich_output.py`
- [x] 7.3 Verify `error_mapping.py` is already fully covered (5 tests covering all `oci_runtime` exception branches)

## 8. Flag Known Bugs as XFail Tests

- [x] 8.1 Add xfail test for `process.py:_parse_params` silent drop of malformed `--param` (no-equals case silently continues)
- [x] 8.2 Add xfail test pinning `batch.py:_parse_params` raise-on-malformed behavior
- [x] 8.3 Add xfail test for `explicit_output=True` without `-o` — document current behavior (ADR §12 says "treated as False" but CLI doesn't enforce)
- [x] 8.4 Add xfail test for `info` command ignoring `cli_overrides` (never passes runtime/engine overrides from CLI flags)

## 9. Verify Final State

- [x] 9.1 Run `pytest src/cli-tools/wallpaper-effects-generator/tests/` — all non-xfail tests pass, xfail tests report as expected
- [x] 9.2 Run `ruff check src/cli-tools/wallpaper-effects-generator/` — no new lint violations
- [x] 9.3 Run `ruff format --check src/cli-tools/wallpaper-effects-generator/` — formatting clean
- [x] 9.4 Verify `test.sh` is deleted and no `rm -rf` footgun remains in the repo
