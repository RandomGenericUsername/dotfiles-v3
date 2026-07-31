## 1. Extract build_deps and Remove the Legacy Seam

- [x] 1.1 In `cli/main.py`, add `build_deps() -> CliDependencies` wrapping `create_config_resolver(default_settings_path=<packaged>/settings.toml)` + `create_effect_loader(default_effects_path=<packaged>/effects.yaml)`
- [x] 1.2 Update the `@callback` to call `build_deps()`, then assign `output_adapter` and `ctx.obj["deps"]`; remove the inline path derivation
- [x] 1.3 Delete the `_test_deps` module-global and `set_test_deps()` from `cli/main.py`
- [x] 1.4 Delete the `os.environ.get("WEG_TEST_DEPS")` guard in the `@callback`
- [x] 1.5 Verify `os` import remains used in `cli/main.py` (it reads `XDG_CONFIG_HOME`)

## 2. Migrate Tests to the build_deps Monkeypatch Seam

- [x] 2.1 Update `tests/conftest.py` `cli_deps_with_processor`: `CliDependencies(processor=fake_processor)` + `monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)`; drop the `set_test_deps` import
- [x] 2.2 Update the 3 inline seam sites in `tests/test_cli.py` (`test_batch_all_dry_run_characterization`, `test_process_malformed_param_silent_drop`, `test_explicit_output_without_output_flag`): add `monkeypatch` param, replace `os.environ["WEG_TEST_DEPS"]="1"` + `set_test_deps(deps)` with `monkeypatch.setattr(...build_deps...)`
- [x] 2.3 Remove the now-unused `os` import from `tests/test_cli.py`

## 3. Add Robustness Regression Guards

- [x] 3.1 Add `TestCliDependencies::test_build_deps_returns_proper_cli_dependencies` to `tests/unit/cli/test_process_commands.py`: asserts `CliDependencies` with `AssembledConfigResolver`/`YamlEffectLoader`, `processor is None`, `output_adapter is None`
- [x] 3.2 Add `TestCliDependencies::test_cli_main_has_no_legacy_test_seam`: asserts `build_deps` exists and `set_test_deps`/`_test_deps` are absent from `cli.main`

## 4. Verify Final State

- [x] 4.1 Run `pytest src/cli-tools/wallpaper-effects-generator/tests/ -q` — all non-xfail tests pass, no collection errors (expect 299 passed, 1 xfailed)
- [x] 4.2 Run `pytest src/cli-tools/wallpaper-effects-generator/tests/ -q -rxX` — the 1 xfail reports as expected
- [x] 4.3 Run `pytest src/cli-tools/wallpaper-effects-generator/tests/test_cli.py -q` — passes in isolation (no cross-test leakage from seam tests to `test_info_respects_runtime_override`)
- [x] 4.4 Run `ruff check src/cli-tools/wallpaper-effects-generator/` — no new lint violations vs. baseline (pre-existing B008/E501 tolerated)
- [x] 4.5 Run `ruff format --check src/cli-tools/wallpaper-effects-generator/` — formatting clean
- [x] 4.6 Run `pytest src/cli-tools/color-scheme-generator/tests/ -q` — CSG suite still green (no shared-library cross-talk)
- [x] 4.7 Confirm `rg "WEG_TEST_DEPS|set_test_deps|_test_deps"` finds no matches under `src/cli-tools/wallpaper-effects-generator/`
- [x] 4.8 Verify production path: invoking the real `app` with no patch constructs real deps (resolver/loader resolve packaged defaults, `processor` is `None`)
