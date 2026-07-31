## Context

The `weg` module at `src/cli-tools/wallpaper-effects-generator/` is a hexagonal-architecture Typer CLI. Its test suite has structural problems:

1. **Broken at collection**: 4 test modules import deleted symbols.
2. **Mock-heavy CLI tests**: `test_process_commands.py` and `test_batch_commands.py` patch `_resolve_processor`/`_resolve_context`, testing mock plumbing instead of real behavior.
3. **No resolution-chain or ENV-override coverage**: The advertised `WALLPAPER__SECTION__KEY` semantics and the 4-level discovery chain (CLI > ENV > CWD-traversal > XDG > default) have zero tests.
4. **No container mount-plan assertions**: The existing mock-engine tests only fake `/output/img.png` — never inspect volume sources/targets, read_only flags, input-parent edge cases, temp artifact serialization/cleanup.
5. **Lossy serializer**: `EffectsSerializer.deserialize` silently drops `min`/`max`/`required`/`type` on round-trip.
6. **Data-loss risk from `test.sh`**: The only end-to-end test uses `rm -rf` with absolute `/tmp` paths.

The architecture is well-suited for the fix: inject fakes at port boundaries, drive real CLI via `CliRunner`, assert observable outputs under `tmp_path`.

## Goals / Non-Goals

**Goals:**
- Make the test suite collect and pass (233+ tests).
- Characterize real CLI behavior through `CliRunner`-based integration tests with fakes at port boundaries, not mocks of internal glue.
- Cover the full config resolution chain (CLI > ENV > CWD-traversal > XDG > default) for both settings and effects.
- Cover `WALLPAPER__SECTION__KEY` ENV override semantics and `cli_overrides` precedence.
- Assert the full container mount plan in `ContainerProcessor` tests (volumes, env, temp artifacts, cleanup, edge cases).
- Fix the lossy `EffectsSerializer` round-trip and pin it with equality tests.
- Flag known behavioral inconsistencies as failing/xfail tests.
- Delete `test.sh` and eliminate the `rm -rf` footgun.

**Non-Goals:**
- No domain, port, or shared-library behavior changes.
- No changes to the production CLI flag-scope layout or processor resolution logic.
- No changes to `oci-runtime` library or `RunConfig` API.
- No new external dependencies.
- No Docker/container-image build changes.
- Not fixing every bug discovered — only the `EffectsSerializer` data loss is fixed. Other inconsistencies are flagged as xfail tests for later triage.

## Decisions

### D1: Env-var test seam in `cli/main.py` callback

**Choice**: In the `@callback` of `app`, after building real `CliDependencies`, check `os.environ.get("WEG_TEST_DEPS")`. If set and the env var value is a valid JSON-serialized `CliDependencies` or a sentinel like `"1"` meaning "use test deps from a module-global," swap in test-supplied dependencies.

**Rationale**: Minimal invasiveness (~5 lines). No need to refactor Typer app construction. The callback currently builds deps in 3 lines — a single guard before `ctx.obj["deps"] = deps` suffices. Tests set the env var with `monkeypatch.setenv` (automatically cleaned by pytest).

**Alternatives considered**:
- Module-level `_test_deps` global setter: simpler but not thread-safe; won't reset between tests unless carefully fixture-managed. Env var is automatically cleaned. Chosen.
- Refactoring `CliDependencies` out of the callback: clean but touches many more lines and risks Typer context wiring issues. Deferred.

### D2: Fake processor replaces `LocalProcessor`/`ContainerProcessor` in integration tests

**Choice**: Create a `_FakeProcessor` class (duck-typed to `EffectProcessorPort`) in the test file that:
- Records each call (`process_effect`, `process_composite`, `process_preset`, `process_batch`) with all arguments.
- Writes a dummy file at `request.output_path` (or `BatchResult` output paths) to simulate real output.
- Returns a `ProcessingResult(success=True, command=str(args), ...)` with the mocked file path.

**Rationale**: The hexagonal port boundary is exactly the right seam. A fake here exercises the *entire real CLI glue* (Typer parsing, option propagation, `ctx.obj` wiring, `OutputPort` rendering, error handling) without needing ImageMagick or a container engine. Real end-to-end tests with `--runtime container` still need a real engine; those remain as guarded integration tests (non-default).

**Alternatives considered**:
- Patching `_resolve_processor` at module level: current approach, proven to miss bugs. Discarded.
- Inline lambda as processor: loses call recording. Discarded.

### D3: Resolution chain tests use `tmp_path` + `monkeypatch.chdir` + `monkeypatch.setenv`

**Choice**: For each priority level (CLI path > ENV path > CWD-traversal > XDG > default), set up a `tmp_path` directory tree with a `settings.toml` / `effects.yaml` at the relevant location, set/unset `WALLPAPER_CONFIG_FILE_PATH` / `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` / `XDG_CONFIG_HOME` as appropriate, and invoke the resolver directly. Assert the resolved values match expectations. Then add `WALLPAPER__SECTION__KEY` overrides on top.

**Rationale**: Tests are deterministic, isolated, and fast. No disk sharing, no real XDG state.

**Edge cases**: The CWD path traversal is depth-limited to 2 parent levels. Test at depth 0, 1, 2 (found) and depth 3 (not found, falls to XDG) by creating a nested tmp dir chain with `Path(tmp_path / "a" / "b" / "c")`.

### D4: Container mount-plan tests use a fake engine that captures `RunConfig`

**Choice**: Create a `_FakeEngine` in the test file with:
- `images.exists(image_name) -> bool` (configurable return).
- `capabilities() -> set[str]` (return `{"container"}`).
- `containers.run(run_config) -> str`: store `self.last_run_config = run_config`, write a dummy file at a volume path mapped from `/output` in the mount plan, return `""`.

**Rationale**: The existing mock-engine approach only fakes `/output/img.png` and never inspects volumes. A recording fake addresses all mount-plan assertions in one test class: check `last_run_config.volumes` for all 4 mounts, `last_run_config.environment` for env vars, `last_run_config.image` for image name, and the path-containment assertion that no volume source is `/` or resolves outside the intended tree.

### D5: `EffectsSerializer` fix is additive

**Choice**: Extend `_dict_to_parameter_definition` to read `min`, `max`, `required`, `type` from the dict and pass them to `ParameterDefinition`. The `ParameterDefinition` dataclass already has all four fields. No schema changes needed — the fields are already present in `ParameterTypeSchema` and survive the initial parse; only the domain-model conversion path drops them.

**Rationale**: Pure additive change. Existing behavior for dicts without these keys is preserved (defaults remain `None`/`False`). The round-trip equality test becomes meaningful.

## Risks / Trade-offs

- **[Risk] Env-var test seam leaks into production trace.** The `WEG_TEST_DEPS` env var is checked on every production `weg` invocation. **Mitigation:** The check is a single `os.environ.get("WEG_TEST_DEPS")` — negligible cost. No code path change if unset.
- **[Risk] Fake processor may drift from real processor behavior.** If `EffectProcessorPort` interface changes (new methods, changed signatures), the fake won't reflect the new contract until the test is updated. **Mitigation:** The port interface itself is stable; `test_ports.py` (rewritten) provides structural coverage. The fake is the test — drift manifests immediately as test failures.
- **[Risk] Deleting `test.sh` loses the only test that runs against real ImageMagick.** **Mitigation:** Keep one `skipif not shutil.which("magick")` integration test in `tests/integration/test_local_processing.py` (already exists with `cp`; extend to also run with `magick` if available). Add one more guarded test for `weg process effect blur --dry-run` that validates command rendering without real execution.
