## Why

The WEG (`wallpaper-effects-generator`) test seam introduced by `weg-test-characterization` (commit `e1264ea`, 2026-07-30) uses an env var + module-global pair: `os.environ["WEG_TEST_DEPS"]` set alongside a module-level `_test_deps` global, checked on every production invocation in the `@callback`. This has three problems:

1. **Test-only machinery leaks into production.** `cli/main.py` carries `_test_deps: CliDependencies | None = None`, `set_test_deps()`, and an `os.environ.get("WEG_TEST_DEPS")` guard that runs on every real `weg` invocation. Production code exists solely to be a test hook.
2. **Cross-test state leakage.** `set_test_deps` writes the env var with a bare assignment and never resets the module-global `_test_deps`. A test that runs after a seam test (e.g. `test_info_respects_runtime_override`, which runs immediately after the last `set_test_deps` call in `test_cli.py`) inherits the stale fake — the seam is order-dependent.
3. **Divergence from the validated CSG pattern.** CSG (`csg-test-characterization`, commit `b38c207`) proved the clean approach: extract a `build_deps()` factory the callback calls, and let tests inject via `monkeypatch.setattr("...main.build_deps", ...)`. No env var, no global, `monkeypatch` auto-reverts per test. WEG already has the honest half — the `deps.processor` short-circuit in `cli/process.py`/`cli/batch.py` — but the injection path still routes through the legacy seam.

The plan targets adoption of the CSG pattern on WEG and **enforces** it with committed regression guards, so the env-var/global seam cannot resurface.

## What Changes

- **Extract `build_deps()`** in `cli/main.py` as the single dependency-construction factory (wrapping `create_config_resolver(default_settings_path=defaults_dir / "settings.toml")` + `create_effect_loader(default_effects_path=defaults_dir / "effects.yaml")`). The `@callback` calls it, then assigns `output_adapter`. Production behavior is byte-for-byte identical.
- **Remove the legacy seam** from production: the `_test_deps` module-global, `set_test_deps()`, and the `WEG_TEST_DEPS` env guard in the callback. The `deps.processor` short-circuit (`cli/process.py:95-96`, `cli/batch.py`) is already the honest seam and stays unchanged.
- **Update tests to monkeypatch `build_deps`**: `tests/conftest.py` `cli_deps_with_processor` becomes `CliDependencies(processor=fake_processor)` + `monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)`; the 3 inline `set_test_deps` call sites in `tests/test_cli.py` switch to the same idiom; the now-unused `os` import in `test_cli.py` is dropped.
- **Enforce robustness with committed regression guards**: a `test_build_deps_returns_proper_cli_dependencies` test (mirroring CSG's `test_generate.py:132`) that locks the prod path — real resolver/loader, `processor is None`, `output_adapter is None` — and a `test_cli_main_has_no_legacy_test_seam` test asserting `set_test_deps`/`_test_deps` are absent from `cli.main`, so the legacy API fails the suite the moment it is reintroduced.

## Capabilities

### New Capabilities
- `weg-deps-test-seam`: The WEG dependency-injection seam is a pure `build_deps()` factory the callback calls; tests inject test doubles via `monkeypatch` of `build_deps`. No env-var or module-global test machinery exists in production, and committed regression guards pin both the prod path and the absence of the legacy API.

### Modified Capabilities
- `weg-cli-integration-tests` (from `weg-test-characterization`): its requirement "test dependencies injected via the `WEG_TEST_DEPS` env-var seam" is superseded — injection is now via `monkeypatch.setattr` on `build_deps`.

## Impact

All changes are in the WEG module at `src/cli-tools/wallpaper-effects-generator/`. No changes to WEG domain, ports, the shared `config-assembler-engine`/`oci-runtime` libraries, or processor resolution logic beyond the callback refactor. No new external dependencies.

### Test files
- **Modify**: `tests/conftest.py` (`cli_deps_with_processor` fixture), `tests/test_cli.py` (3 inline seam sites, remove `os` import), `tests/unit/cli/test_process_commands.py` (add `TestCliDependencies` regression guards)
- **No change**: `tests/unit/cli/test_process_commands.py` / `test_batch_commands.py` usage of `cli_deps_with_processor` (fixture signature is the only surface they consume)

### Source files
- **Modify**: `cli/main.py` (extract `build_deps()`; delete `_test_deps`, `set_test_deps`, env guard)
- **No change**: `factory.py`, `cli/process.py`, `cli/batch.py` (the `deps.processor` short-circuit is already in place), domain, ports, other adapters

### Behavior
Identical production behavior when no test patch is active: `build_deps()` resolves the same packaged defaults, the callback wires the same `output_adapter`, and the `deps.processor` short-circuit path is unchanged. The only production diff is the removal of the dead env-var guard and the two test-only helpers.
