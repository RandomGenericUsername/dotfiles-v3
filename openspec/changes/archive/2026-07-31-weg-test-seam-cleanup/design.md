## Context

The WEG module at `src/cli-tools/wallpaper-effects-generator/` is a hexagonal-architecture Typer CLI. Its test seam was introduced by `weg-test-characterization` (commit `e1264ea`, 2026-07-30) as an env-var + module-global pair:

- `cli/main.py` declares `_test_deps: CliDependencies | None = None` and `set_test_deps(deps)` which both sets the global and writes `os.environ["WEG_TEST_DEPS"] = "1"`.
- The `@callback` builds real deps, then `if os.environ.get("WEG_TEST_DEPS") and _test_deps is not None: deps = _test_deps`.
- `tests/conftest.py` `cli_deps_with_processor` calls `set_test_deps(deps)` as a fixture side effect; `tests/test_cli.py` has 3 inline `set_test_deps` call sites.

CSG (`csg-test-characterization`, commit `b38c207`) validated the cleaner pattern: extract `build_deps()` as the single construction factory, have the callback call it, and let tests inject via `monkeypatch.setattr("...cli.main.build_deps", ...)`. CSG's `CliDependencies.processor` slot (the equivalent of WEG's) is the honest port-boundary seam; `build_deps` is the injection point.

Three concrete problems drive this change:

1. **Test-only machinery in production.** The env guard executes on every real `weg` invocation; `_test_deps`/`set_test_deps` exist solely for tests.
2. **Cross-test state leakage.** `set_test_deps` never resets the global or the env var. `test_info_respects_runtime_override` runs immediately after the last seam call in `test_cli.py` and inherits the stale fake — the suite is order-dependent.
3. **Pattern drift.** WEG has the honest `deps.processor` short-circuit (`cli/process.py:95-96`, `cli/batch.py`) but routes injection through the legacy seam instead of the CSG-validated `build_deps` monkeypatch.

An executable prototype on branch `wip/prototype-weg-test-seam-cleanup` (validated before this change was written) confirmed the refactor is mechanically sound: WEG suite 299 passed/1 xfailed (baseline 297/1 + 2 new guards), CSG 536 passed/8 xfailed, 0 net-new ruff errors, and the vulnerable ordering (`test_cli.py` seam tests → `test_info_respects_runtime_override`) passes in isolation.

## Goals / Non-Goals

**Goals:**
- Extract `build_deps()` in `cli/main.py` and have the `@callback` use it, preserving production behavior byte-for-byte.
- Remove `_test_deps`, `set_test_deps`, and the `WEG_TEST_DEPS` env guard from production.
- Migrate `tests/conftest.py` and the 3 inline `test_cli.py` sites to `monkeypatch.setattr` on `build_deps`.
- Enforce robustness with committed regression guards: prod-path lock + legacy-API-absence guard.
- Keep the existing `deps.processor` short-circuit as the runtime seam (already present, unchanged).

**Non-Goals:**
- No changes to processor resolution logic, `factory.py`, domain, ports, or shared libraries.
- No re-architecture of the CLI beyond the callback refactor (no full DI framework, no click/typer test-deps overhaul).
- No changes to `weg-cli-integration-tests` behavior requirements beyond the seam mechanism it names.
- No new external dependencies.

## Decisions

### D1: Extract `build_deps()` as the single construction factory

**Choice**: Add `def build_deps() -> CliDependencies:` to `cli/main.py` wrapping the current inline construction:

```python
def build_deps() -> CliDependencies:
    defaults_dir = package_files("wallpaper_effects_generator") / "defaults"
    return CliDependencies(
        config_resolver=create_config_resolver(
            default_settings_path=defaults_dir / "settings.toml"
        ),
        effect_loader=create_effect_loader(default_effects_path=defaults_dir / "effects.yaml"),
    )
```

The `@callback` becomes `deps = build_deps(); deps.output_adapter = create_output_adapter(output_format); ctx.obj["deps"] = deps`.

**Rationale**: This is exactly CSG's validated shape (`color_scheme_generator/cli/main.py:78`). `build_deps` becomes the single seam: tests patch one function; production has one construction site. The callback no longer carries the path-derivation inline, so the seam is a named, testable unit.

**Alternatives considered**:
- Keep inline construction and monkeypatch `create_config_resolver`/`create_effect_loader`: patches two namespaces (mirroring the old CSG mock-heavy approach) and couples tests to which factory functions the callback happens to call. Rejected.
- Make `CliDependencies` itself a test fixture injection via `ctx.obj` plumbing: works but requires every test to construct the full `ctx.obj`, which the CliRunner already does through the real callback. Rejected as redundant.

### D2: Remove the legacy seam — `_test_deps`, `set_test_deps`, `WEG_TEST_DEPS` env guard

**Choice**: Delete all three from `cli/main.py`. No replacement guard: when `build_deps` is unpatched, the callback constructs real deps; when a test patches it, the fake flows through the same path. The `deps.processor` short-circuit (`cli/process.py:95-96`) remains the port-boundary seam and is untouched.

**Rationale**: The env guard and global exist only for tests. Removing them eliminates the "check env on every invocation" overhead, the module-global that leaks across tests, and the divergence from CSG. `monkeypatch` (pytest-managed) reverts automatically per test — the exact property the manual global lacked.

**Alternatives considered**:
- Keep the env-var seam and fix only the reset (set `_test_deps = None` in a fixture): minimal diff but leaves test-only machinery in production and diverges from CSG. Rejected.
- `unittest.mock.patch` the callback: works but every test would re-enter the callback; `monkeypatch.setattr` on `build_deps` is simpler and pytest-idiomatic. Chosen.

### D3: Migrate fixtures and inline sites to `monkeypatch.setattr("...main.build_deps", ...)`

**Choice**: `tests/conftest.py`:

```python
@pytest.fixture
def cli_deps_with_processor(
    fake_processor: FakeProcessor, monkeypatch: pytest.MonkeyPatch
) -> CliDependencies:
    deps = CliDependencies(processor=fake_processor)
    monkeypatch.setattr("wallpaper_effects_generator.cli.main.build_deps", lambda: deps)
    return deps
```

The 10 existing consumers (`test_process_commands.py` ×6, `test_batch_commands.py` ×4) are unchanged — they request the fixture and get the side effect. The 3 inline sites in `tests/test_cli.py` replace `os.environ["WEG_TEST_DEPS"] = "1"` + `set_test_deps(deps)` with `monkeypatch.setattr("...build_deps", lambda: deps)` and add a `monkeypatch` parameter. The `os` import in `test_cli.py` becomes unused and is removed.

**Rationale**: The fixture keeps its contract (returns `CliDependencies(processor=fake)`) while the injection mechanism switches from a leaking global to pytest-managed `monkeypatch`. Because `CliDependencies.config_resolver`/`effect_loader` use `default_factory` (`factory.py:51-52`), `CliDependencies(processor=fake)` still yields real resolver/loader — so explicit `--config`/`--effects` fixtures keep working with zero churn in the 10 consumers.

**Alternatives considered**:
- `autouse` fixture for `test_cli.py`: would patch `build_deps` for the whole module and silently drop the real-deps path that `test_info_respects_runtime_override` exercises. Rejected — per-test explicit patching preserves the real-path coverage.
- Helper `_invoke(...)` like CSG's `test_generate.py:17-24`: clean, but WEG's inline invoke style means converting all 10 consumers is churn without coverage gain. Rejected for this change.

### D4: Enforce robustness with committed regression guards

**Choice**: Add `class TestCliDependencies` to `tests/unit/cli/test_process_commands.py` (mirroring CSG's `test_generate.py:132`):

- `test_build_deps_returns_proper_cli_dependencies` — asserts `build_deps()` returns a `CliDependencies` with real `AssembledConfigResolver`/`YamlEffectLoader`, `processor is None`, `output_adapter is None`.
- `test_cli_main_has_no_legacy_test_seam` — asserts `build_deps` exists and `set_test_deps`/`_test_deps` are absent from `cli.main`.

**Rationale**: These convert the design decisions into red/green signals. The prod-path test locks the contract so a future refactor can't silently break `build_deps()`; the absence guard fails the suite the instant the legacy API is reintroduced, fulfilling the "enforcing robust tests" requirement rather than just updating tests.

**Alternatives considered**:
- Docs-only (record the seam in design.md and trust reviewers): no enforcement; the env guard could return undetected. Rejected.
- A single `rg`-style static check script: brittle and not part of the pytest suite. Rejected — the two pytest guards are both precise and CI-native.

## Risks / Trade-offs

- **[Risk] `build_deps` becomes a new public patch target.** A test that patches it and fails to revert could leak a fake across tests. **Mitigation:** `monkeypatch` auto-reverts per test (the entire point of the change); the callback builds fresh deps per `CliRunner.invoke`, so there is no shared state between invocations.
- **[Risk] `monkeypatch.setattr` by string couples tests to the module path.** If `build_deps` moves modules, the string target breaks at runtime. **Mitigation:** The string is pinned by `test_build_deps_returns_proper_cli_dependencies` (import-time check) and `test_cli_main_has_no_legacy_test_seam`; a move fails loudly, not silently.
- **[Risk] The `cli_deps_with_processor` fixture now depends on `monkeypatch`.** Any test that requests the fixture outside a function-scoped context is unaffected (all current consumers are function-scoped). **Mitigation:** The 10 consumers run unchanged and green in the validated prototype.
- **[Trade-off] The `weg-cli-integration-tests` spec (from `weg-test-characterization`) names the env-var seam.** This change supersedes that mechanism. **Mitigation:** Declared under "Modified Capabilities" in `proposal.md`; the requirement text is updated to the `build_deps` monkeypatch mechanism.

## Open Questions

None — the executable prototype resolved the seam mechanism, leakage, and enforcement questions. This change formalizes the validated outcome.
