## Why

The `csg` (color-scheme-generator) test suite does collect and pass, but it is dominated by mock-heavy CLI command tests that patch `build_deps`/`create_local_processor`/`create_container_processor` (often in two namespaces — `cli.main` and `cli._helpers`) and assert on mock return values rather than real behavior. Critical behavior has zero or weak coverage: the full config resolution priority chain, `COLORSCHEME__SECTION__KEY` ENV override semantics, the container mount plan's sources/targets/read_only, serializer/catalog field fidelity, and error paths through the real Typer `app`. The only true end-to-end harness, `tests/test_user_journey.sh` (534 lines of bash), drives the real binary but is not run by pytest, duplicates the CLI surface it exercises, and cannot be part of the normal suite.

The suite produces false confidence: real inconsistencies — inert `min`/`max` range fields declared in `backends.yaml` yet dropped end-to-end, schema accepting invalid `default_formats` strings, help text omitting the CLI `--config` priority step, `install`/`uninstall`/`version`/`list-backends` bypassing the `OutputPort` abstraction — pass undetected.

## What Changes

- **Remove the inert `min`/`max` range fields** from `defaults/backends.yaml` and `BackendParameterSchema`. The declared ranges are dropped by `_schema_to_domain`, have no slot on `BackendParameterDefinition`, are never checked by `ParameterResolutionService`, and are contradicted by the HLS saturation clamp (`[1.0, 2.0]` is unrepresentable in the color model). The catalog contract becomes: type + choices + default + required. **BREAKING** for any third-party `backends.yaml` that declares `min`/`max` (silently ignored before, now absent).
- **Add a test seam** via the existing `CliDependencies.processor` slot (`factory.py`): short-circuit `create_local_processor`/`create_container_processor` in `cli/main.py` and `cli/_helpers.py` when `deps.processor` is set. No env-var/module-global machinery; production behavior unchanged when the slot is unset.
- **Rewrite CLI command tests** to drive the real Typer `app` via `CliRunner` with a `FakeProcessor` injected through `CliDependencies(processor=...)`, asserting observable output (exit codes, files under `tmp_path`, JSON stdout structure) instead of mock call assertions. Cover all commands: `generate`, `show`, `info`, `dump-config`, `dump-templates`, `install`, `uninstall`, `list-backends`, `version`, the completion options, and the global flags (`--output-format json|rich|plain`, `-q`/`--quiet`, `-v`/`--verbose`).
- **Add resolution-priority and ENV-override coverage** for the full chain: CLI path > `COLORSCHEME_CONFIG_FILE_PATH` > CWD traversal (`max_levels=3`) > XDG (`~/.config/color-scheme-generator/`) > package default; `COLORSCHEME__SECTION__KEY` double-underscore nesting (`runtime.mode`, `container.engine`, `output.directory`); `cli_overrides` precedence over ENV.
- **Harden container processor tests** with a recording fake runtime: assert all 4 `ContainerMount`s (generate) and 3 (show) with correct `source`/`target`/`read_only`, `environment == _CONTAINER_ENV`, serialized temp settings.toml validity, cleanup on success and exception, `ContainerImageNotFoundError`, input-parent-is-`/` rejection, and the interface-contract test (inner argv round-trips through the live Typer `app`).
- **Delete `tests/test_user_journey.sh`**; its assertions are preserved by the per-command CliRunner tests rewritten in this change.
- **Flag (as xfail tests)** known behavioral inconsistencies, each with a numbered `# N.x` comment: schema accepts arbitrary `default_formats` strings; `--help` text omits the CLI `--config` priority step; `BackendDefinition.min_version` hardcoded to `"0.0.0"`; `install`/`uninstall`/`version`/`list-backends` use `isinstance` dispatch that bypasses the `OutputPort` abstraction.
- **Cover remaining gaps**: schema validators (engine whitelist, `auto` rejection, memory-limit shape, timeout `<0`), output adapters (`config_info`, catalog/info display), and error paths (missing input, missing config, invalid backend, container-runtime-unavailable, `map_oci_error`).

## Capabilities

### New Capabilities
- `csg-cli-integration-tests`: Characterize the real CLI end-to-end via `CliRunner` with fakes at the processor port boundary, covering all 9 commands, global flags, config/templates options, and error paths with observable-output assertions.
- `csg-config-resolution-chain`: Cover the full priority chain (CLI path > `COLORSCHEME_CONFIG_FILE_PATH` > CWD traversal at depth 0/1/2, depth-3 fall-through > XDG standard + custom > package default) including `COLORSCHEME__SECTION__KEY` double-underscore nesting and `cli_overrides` precedence over ENV.
- `csg-container-mount-contract`: Assert the container mount plan — 4 mounts (generate) / 3 mounts (show) with correct sources/targets/read_only, `_CONTAINER_ENV`, serialized temp settings.toml validity, cleanup on success and exception, `ContainerImageNotFoundError`, input-parent-is-`/` rejection, and inner-argv acceptance by the live CLI parser.

### Modified Capabilities
None — this change does not modify existing spec behavior requirements; it covers existing requirements with new tests.

## Impact

All changes are in the CSG module at `src/cli-tools/color-scheme-generator/`. No changes to CSG domain, ports, or the shared `oci-runtime`/`config-assembler-engine` libraries. No new external dependencies. No container images are built or modified; container-mode tests fake the engine.

### Test files
- **Delete**: `tests/test_user_journey.sh`
- **Rewrite**: `tests/unit/cli/*.py` (mock-heavy command tests), `tests/unit/adapters/test_container_processor.py` (mocks → recording fake runtime)
- **Add**: `tests/conftest.py`, `tests/unit/adapters/settings/test_config_resolution_chain.py`, schema-validator direct tests, serializer/catalog round-trip fidelity tests, xfail tests for the four flagged inconsistencies
- **Update**: `tests/unit/adapters/schemas/test_backends_catalog_schema.py` (pin the removal of `min`/`max`), existing output-adapter tests (fill `config_info`/catalog-display gaps)

### Source files
- **Modify**: `defaults/backends.yaml` (remove 4 `min:`/`max:` lines), `adapters/schemas/backends_catalog_schema.py` (remove `min`/`max` fields), `cli/main.py` (processor short-circuit in `generate`, ~2 lines), `cli/_helpers.py` (processor short-circuit in `resolve_processor`, ~2 lines)
- **No change**: domain, ports, other adapters, factory, shared libraries
