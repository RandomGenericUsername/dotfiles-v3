## Why

The `weg` (wallpaper-effects-generator) test suite is broken at collection — 4 test modules import symbols that were deleted during a previous refactor (`docker_image_manager`, `oci_command_runner`, `ImageManagerPort`). The remaining 233 tests that do collect are dominated by mock-heavy CLI command tests that patch `_resolve_processor`/`_resolve_context`, asserting mock return values rather than real behavior. Critical behavior — resolution priority chain, ENV override semantics (`WALLPAPER__SECTION__KEY`), container mount-plan edge cases (input parent at `/`, symlink escapes), flat/explicit_output path matrix, lossy serializer round-trips — has zero coverage. The existing `test.sh` does exercise the real CLI but introduces an `rm -rf` footgun risk that is not worth a bash-based approach.

The result: real-world bugs (wrong mount paths, CLI flag-scope drift, silent `--param` drops, output directory resolution errors) pass the test suite undetected. The suite produces false confidence.

## What Changes

- **Fix the 4 dead modules** that block collection: delete or rewrite `test_factory.py`, `test_ports.py`, `test_docker_image_manager.py`, `test_oci_command_runner.py`. Rewrite factory/ports tests against the current port set and factory API.
- **Add a test seam** in `cli/main.py` so tests can inject fake `CliDependencies` into the real Typer app (env-var-based override).
- **Rewrite CLI command tests** to drive the real Typer `app` via `CliRunner` with fakes at the processor/engine port boundary, asserting observable outputs (files under `tmp_path`, exit codes, JSON structure) instead of mock call assertions.
- **Add resolution-priority and ENV-override coverage** for the full chain: CLI path > `WALLPAPER_CONFIG_FILE_PATH` > CWD traversal > XDG > package default; `WALLPAPER__SECTION__KEY` double-underscore nesting; `cli_overrides` precedence.
- **Harden container processor tests** to assert the full mount plan (all 4 `VolumeMount` sources/targets/read_only), temp TOML/YAML serialization and cleanup, `ContainerImageNotFoundError` path, and input-parent-is-`/` / symlink-escape edge cases.
- **Fix the lossy `EffectsSerializer`** that silently drops `min`/`max`/`required` on deserialize. Add round-trip-equality tests for parameter bounds.
- **Flag (as failing/xfail tests)** known behavioral inconsistencies: `_parse_params` silently drops malformed `--param` in `process.py` but raises in `batch.py`; `explicit_output=True` without `-o` documented as ignored but CLI never enforces it; `cli/info.py` never passes `cli_overrides` so runtime/engine overrides are invisible; `rich_output` missing `catalog_list`/`config_info` coverage.
- **Delete `test.sh`** and replace its characterization assertions with a single `CliRunner`+fake-processor test. The `rm -rf` risk is eliminated entirely.
- **Cover remaining module gaps**: `settings_schema.py` validators (engine whitelist, registry slash-strip), `mixed_texture_loader` (if referenced), `error_mapping` (already well-covered, verify).

## Capabilities

### New Capabilities
- `weg-cli-integration-tests`: Characterize the real CLI behavior end-to-end via `CliRunner` with fakes at port boundaries, covering all 9 commands, global flags (`--output-format`, `-q`, `-v`), config/effects options, error paths (missing file, resolution failure).
- `weg-config-resolution-chain`: Cover the full priority chain (CLI path > ENV path > CWD traversal > XDG > package default) for both settings (`settings.toml`) and effects (`effects.yaml`), including `WALLPAPER__SECTION__KEY` double-underscore nesting and `cli_overrides` precedence over ENV.
- `weg-container-mount-contract`: Assert the container mount plan — all 4 `VolumeMount` sources/targets/read_only, serialized temp TOML/YAML content, `_cleanup_artifacts` on success and exception, `ContainerImageNotFoundError` from `images.exists`, input-parent-is-`/` and symlink-escape pre-flight rejection.
- `weg-effects-serializer-roundtrip`: Cover the full domain-model round-trip including param bounds (`min`/`max`/`required`/`type`) which are currently lost on deserialize.

### Modified Capabilities
None — this change does not modify existing spec behavior requirements; it covers existing requirements with new tests.

## Impact

All changes are in the WEG module at `src/cli-tools/wallpaper-effects-generator/`. No changes to domain, ports, oci-runtime, or other shared libraries. No behavior changes for end users — only tests and test infrastructure are modified, plus one fix to `EffectsSerializer` (behavior-preserving but previously lossy).

### Test files
- **Delete**: `tests/test_factory.py`, `tests/test_ports.py`, `tests/unit/adapters/test_docker_image_manager.py`, `tests/unit/adapters/test_oci_command_runner.py`, `test.sh`
- **Rewrite**: `tests/test_factory.py` (against current factory), `tests/test_ports.py` (against current port set), `tests/unit/cli/test_process_commands.py`, `tests/unit/cli/test_batch_commands.py`, `tests/unit/cli/test_show_commands.py`, `tests/unit/adapters/test_container_processor.py`
- **Add**: `tests/unit/adapters/test_config_resolution_chain.py`, `tests/unit/adapters/test_settings_schema_validators.py`, `tests/unit/adapters/output/test_rich_output_comprehensive.py`, tests for `EffectsSerializer` round-trip equality
- **Update**: `tests/test_assembled_config_resolver.py` (ENV override tests), `tests/test_yaml_effect_loader.py` (ENV path tests), `tests/unit/adapters/serializer/test_effects_serializer.py` (round-trip equality)

### Source files
- **Modify**: `cli/main.py` (add test seam, ~5 lines), `adapters/serializer/effects_serializer.py` (fix `_dict_to_parameter_definition` to preserve `min`/`max`/`required`/`type`)
- **No change**: domain, ports, other adapters, factory, schemas
