# weg-deps-test-seam Specification

## Purpose
TBD - created by archiving change weg-test-seam-cleanup. Update Purpose after archive.
## Requirements
### Requirement: The CLI builds dependencies through a single build_deps factory
`cli/main.py` SHALL define a `build_deps() -> CliDependencies` function that constructs the production `CliDependencies` — a `ConfigResolverPort` via `create_config_resolver(default_settings_path=<packaged>/settings.toml)` and an `EffectLoaderPort` via `create_effect_loader(default_effects_path=<packaged>/effects.yaml)`. The Typer `@callback` SHALL obtain its dependencies by calling `build_deps()` and then assign the output adapter and `ctx.obj["deps"]`.

#### Scenario: Production callback uses build_deps
- **WHEN** a command is invoked through the real `app` with no test patch active
- **THEN** the callback constructs dependencies via `build_deps()`
- **AND** `ctx.obj["deps"]` is that instance
- **AND** `deps.output_adapter` is set from the effective `--output-format`

#### Scenario: build_deps returns production dependencies
- **WHEN** `build_deps()` is called directly
- **THEN** it returns a `CliDependencies` instance
- **AND** `config_resolver` is an `AssembledConfigResolver`
- **AND** `effect_loader` is a `YamlEffectLoader`
- **AND** `processor` is `None`
- **AND** `output_adapter` is `None`

### Requirement: No env-var or module-global test machinery exists in production
`cli/main.py` SHALL NOT contain the `WEG_TEST_DEPS` env-var guard, the `_test_deps` module-global, or a `set_test_deps` helper. Production behavior SHALL be independent of any environment variable for dependency injection.

#### Scenario: Legacy seam API is absent
- **WHEN** `cli.main` is imported
- **THEN** it has `build_deps`
- **AND** it does not have `set_test_deps`
- **AND** it does not have `_test_deps`

#### Scenario: Real invocation never consults a test env var
- **WHEN** a command is invoked with no test patch active
- **THEN** the resolved processor is determined solely by `deps.processor` (when set) and the runtime-mode resolution path
- **AND** no `WEG_TEST_DEPS`-style environment variable is read

### Requirement: Tests inject fakes via monkeypatching build_deps
Tests that need a fake processor SHALL construct `CliDependencies(processor=<fake>)` and inject it by `monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", ...)`. The `cli_deps_with_processor` fixture SHALL follow this pattern and SHALL NOT use the env var or a module-global setter.

#### Scenario: cli_deps_with_processor injects via monkeypatch
- **WHEN** the `cli_deps_with_processor` fixture is requested in a test
- **THEN** it returns `CliDependencies(processor=<fake>)` with real resolver/loader via `default_factory`
- **AND** it registers `monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", ...)` so the callback receives the fake
- **AND** the patch is reverted automatically when the test completes

#### Scenario: Explicit config/effects paths still resolve with real adapters
- **WHEN** a test invokes `process`/`batch` with explicit `--config` and `--effects` paths and the `cli_deps_with_processor` fixture active
- **THEN** the fake processor handles the `process_*`/`batch_*` calls
- **AND** the real `config_resolver`/`effect_loader` resolve the explicit files

### Requirement: The runtime processor short-circuit is preserved
The `deps.processor` short-circuit in `cli/process.py` (and the equivalent batch path) SHALL remain the port-boundary seam: when `deps.processor` is not `None`, that processor is used; otherwise the existing runtime-mode resolution runs. This change SHALL NOT alter that logic.

#### Scenario: Pre-set processor wins
- **WHEN** `deps.processor` is set (via the `build_deps` monkeypatch)
- **THEN** the processor is used without constructing a real local or container processor

#### Scenario: Unset processor keeps production path
- **WHEN** `deps.processor` is `None` and no patch is active
- **THEN** the dry-run/container/local processor construction follows the unchanged production logic

### Requirement: Cross-test isolation is enforced
The WEG test suite SHALL be order-independent: no test SHALL rely on module-global state or environment variables written by another test. The suite SHALL pass when `test_cli.py` runs in isolation with the seam tests followed by the real-deps `info` test.

#### Scenario: Real-deps test after seam tests is unaffected
- **WHEN** `tests/test_cli.py` runs fully in isolation (including the 3 seam tests and `test_info_respects_runtime_override`)
- **THEN** all tests pass
- **AND** `test_info_respects_runtime_override` observes real dependencies, not a stale fake

