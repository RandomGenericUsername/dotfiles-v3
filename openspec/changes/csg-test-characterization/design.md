## Context

The `csg` module at `src/cli-tools/color-scheme-generator/` is a hexagonal-architecture Typer CLI. Its suite collects and passes but has structural problems:

1. **Mock-heavy CLI tests**: `tests/unit/cli/*.py` patch `build_deps`/`create_local_processor`/`create_container_processor` — often in two namespaces (`cli.main` and `cli._helpers`) because `generate` builds processors inline while `show` routes through `resolve_processor` in `_helpers.py`. Tests assert mock call counts/return values instead of real observable behavior.
2. **Zero resolution-chain or ENV-override coverage**: `tests/unit/adapters/settings/test_config_resolver.py` covers resolver invocation but not the 5-strategy priority chain (CLI > `COLORSCHEME_CONFIG_FILE_PATH` > CWD traversal `max_levels=3` > XDG > package default) or `COLORSCHEME__SECTION__KEY` semantics.
3. **Inert catalog range fields**: `defaults/backends.yaml` declares `min`/`max` bounds (saturation ×3, n_clusters ×1) that are dropped by `_schema_to_domain` (`yaml_backend_catalog_loader.py:40-50`), have no slot on `BackendParameterDefinition` (`domain/models.py:83-90`), are never checked by `ParameterResolutionService.resolve_all`, and are contradicted by the HLS saturation clamp in every backend (`[1.0, 2.0]` is unrepresentable). The catalog lies.
4. **No container mount-plan source assertions**: `tests/unit/adapters/test_container_processor.py` uses a `Mock()` runtime and asserts mount *targets* but not sources or `_CONTAINER_ENV` fidelity.
5. **`test_user_journey.sh` (534 lines)** is the only true end-to-end harness but runs outside pytest, duplicates the CLI surface, and is excluded from CI.
6. **Known inconsistencies unexamined**: schema accepts arbitrary `default_formats` strings; `--help` omits the CLI `--config` priority step; `BackendDefinition.min_version` hardcoded; four commands bypass `OutputPort` via `isinstance` dispatch.

The architecture is well-suited for the fix: inject a fake processor through the existing `CliDependencies.processor` slot, drive the real `app` via `CliRunner`, assert observable output under `tmp_path`.

## Goals / Non-Goals

**Goals:**
- Characterize real CLI behavior through `CliRunner`-based integration tests with a fake processor at the port boundary, not mocks of internal glue.
- Cover the full config resolution chain (CLI > ENV > CWD traversal depth 0/1/2 + depth-3 fall-through > XDG standard + custom > package default) including `COLORSCHEME__SECTION__KEY` and `cli_overrides` precedence.
- Assert the full container mount plan (4 mounts for generate, 3 for show, sources/targets/read_only, `_CONTAINER_ENV`, serialized temp settings.toml validity, cleanup, `ContainerImageNotFoundError`, input-parent-`/`).
- Remove the inert `min`/`max` catalog range fields and pin the resulting contract.
- Preserve `test_user_journey.sh` assertions as per-command CliRunner tests, then delete the bash script.
- Flag discovered behavioral inconsistencies as xfail tests with numbered `# N.x` comments.

**Non-Goals:**
- No CSG domain, port, or shared-library (`oci-runtime`/`config-assembler-engine`) behavior changes.
- No changes to production CLI flag-scope layout or processor resolution logic beyond the test seam.
- No new external dependencies.
- No Docker/container-image build changes; container-mode tests fake the engine.
- Not fixing every discovered inconsistency — only the `min`/`max` removal is a production change. All other findings become xfail tests for later triage.

## Decisions

### D1: Remove the inert `min`/`max` catalog range fields (removal over resurrection)

**Choice**: Delete the `min`/`max` field declarations from `BackendParameterSchema` (`adapters/schemas/backends_catalog_schema.py:14-15`) and the 4 `min:`/`max:` lines from `defaults/backends.yaml`. The catalog parameter contract becomes: `key`/`param_type`/`default`/`choices`/`description`/`required` only.

**Rationale**: The fields are dead end-to-end and cannot be honestly resurrected within this change's constraints:
- `_schema_to_domain` drops them; `BackendParameterDefinition` has no slots; `ParameterResolutionService` checks only `required`; backends never read them.
- Fixing properly requires a forbidden domain change (add `min`/`max` to `BackendParameterDefinition`) **and** a product decision on the `[1.0, 2.0]` contradiction — HLS saturation is a fraction in `[0,1]`, so `max: 2.0` is mathematically unrepresentable, and all three backends clamp the factor to `1.0` anyway. Implementing enforcement against the declared range would bless values that silently clamp.
- `choices` remains the enforced constraint mechanism for `algorithm`; `saturation`/`n_clusters` remain wired params with the backends' own defensive clamps as the safety net.

**Alternatives considered**:
- Additive fix (mirror WEG's `EffectsSerializer` patch): requires `BackendParameterDefinition.min`/`.max` (domain change) + loader forwarding + resolver checks + catalog range reconciliation. Out of scope; recorded in `proposal.md` as `**BREAKING**` for third-party catalogs declaring `min`/`max`.
- Keep fields, flag as xfail: preserves the lie in `--help` and the dead path; chosen only if we wanted zero production churn. Rejected — removal is the honest contract.

### D2: Test seam = existing `CliDependencies.processor` slot (no env-var/module-global)

**Choice**: `CliDependencies` already declares `processor: ColorSchemeProcessorPort | None = None` (`factory.py:37`). Add a 2-line short-circuit at the top of the two processor-construction sites so a pre-set processor wins:
- `cli/main.py` `generate` (`main.py:227-238`): if `deps.processor is not None`, use it; else the existing `RuntimeMode.CONTAINER` branch.
- `cli/_helpers.py` `resolve_processor` (`_helpers.py:127-141`): if `deps.processor is not None`, return it immediately.

**Rationale**: The slot already exists in production — this is the least-invasive seam and the one place both `generate` and `show` already converge (`deps`). Tests construct `CliDependencies(processor=FakeProcessor())` and inject via the existing `ctx.obj["deps"]` wiring. No env var, no module-global `_test_deps`, no monkeypatching two namespaces.

**Alternatives considered**:
- WEG-style env-var + module-global `set_test_deps`: adds ~5 lines of production test-only machinery and an env check on every invocation. Unnecessary — the `processor` slot is the CSG-native equivalent of `WEG_TEST_DEPS`.
- Monkeypatching `create_local_processor`/`create_container_processor` in both `cli.main` and `cli._helpers`: works (existing tests do it) but couples tests to module internals and requires patching two namespaces whenever the routing changes. Discarded in favor of the slot.

### D3: Delete `test_user_journey.sh`; preserve assertions as per-command CliRunner tests

**Choice**: Delete `tests/test_user_journey.sh`. Its characterization is preserved by the rewritten per-command CliRunner tests in `tests/unit/cli/*` (each command covered individually with observable-output assertions), matching the prompt's "do NOT delete unless you replace its assertions with CliRunner tests" constraint.

**Rationale**: CSG has no single high-level `batch all` command analogous to WEG's journey replacement — its coverage is naturally per-command (`generate`, `show`, `info`, `dump-config`, `dump-templates`, `install`, `uninstall`, `list-backends`, `version`). A single synthetic "run everything" test would duplicate the per-command tests without adding coverage.

**Alternatives considered**:
- One all-commands smoke test: adds no coverage beyond per-command tests. Rejected.
- Keep the bash script alongside: excluded from pytest, duplicates CLI surface, contradictory to the prompt's intent. Rejected.

### D4: XFail policy — every discovered inconsistency gets a pinned failing test

**Choice**: Each behavioral inconsistency discovered during the audit becomes an `@pytest.mark.xfail(reason="...")` test asserting the **correct** behavior, prefixed with a numbered `# N.x` comment (mirroring WEG's task-numbering style). The tests go green when the underlying bug is fixed. Four are planned:
- `# 8.1` — schema accepts arbitrary `default_formats` strings (e.g. `["weird"]`); coercion to `ColorFormat` happens late in `main.py:208-216`. xfail asserts the schema rejects invalid formats.
- `# 8.2` — `--help` text in `main.py:60-74` lists 4 resolution steps but the code has 5 (`CliPathStrategy` first). xfail asserts help text reflects all 5.
- `# 8.3` — `BackendDefinition.min_version` hardcoded to `"0.0.0"` (`yaml_backend_catalog_loader.py:57`) regardless of YAML. xfail asserts it round-trips if declared.
- `# 8.4` — `install`/`uninstall`/`version`/`list-backends` use `isinstance(adapter, ...)` dispatch bypassing `OutputPort`. xfail asserts they route through the port abstraction.

**Rationale**: Mirrors WEG's "flag, don't fix" rule. Keeps the suite self-documenting — each xfail names the bug and the correct behavior in its `reason` and `# N.x` comment.

**Alternatives considered**:
- Document-only (no tests): loses the self-documenting red/green signal. Rejected.
- Fix in this change: four of the five are out-of-scope product/architecture decisions; only the `min`/`max` removal is in-scope (D1).

### D5: Resolution-chain tests use `tmp_path` + `monkeypatch.chdir` + `monkeypatch.setenv`

**Choice**: For each priority level, set up a `tmp_path` directory tree with a `settings.toml` containing a distinct `version` string identifying which level resolved, set/unset `COLORSCHEME_CONFIG_FILE_PATH`/`XDG_CONFIG_HOME` as appropriate, and invoke the resolver directly (no CLI). Add `COLORSCHEME__SECTION__KEY` overrides on top; assert `cli_overrides` beat ENV.

**Edge cases**: CWD traversal is depth-limited to `max_levels=3`. Test at depth 0/1/2 (found) and depth 3 (falls through to XDG/package default) via a nested `tmp_path/a/b/c` chain. Standard XDG (`~/.config/color-scheme-generator/`) is emulated via `XDG_CONFIG_HOME=tmp_path/.config`.

### D6: Container mount-plan tests use a recording fake runtime

**Choice**: Create a `_FakeContainerRuntime` (duck-typed to `ContainerRuntimePort`) that records the last `RunConfig`, makes `image_exists()` configurable, and writes dummy output files at the host path mapped from `/output`. Assert the full mount plan from the recorded run: 4 mounts for `process_generate` (config TOML, templates, `/input`, `/output`) and 3 for `process_show` (no `/output`), correct sources/targets/read_only, `environment == _CONTAINER_ENV`, serialized temp settings.toml validity (`runtime.mode = "local"`), cleanup on success/exception, `ContainerImageNotFoundError` when `image_exists()` is False, input-parent-at-`/` rejection, and the interface-contract test (adapter's inner argv round-trips through the live Typer `app`).

**Rationale**: The existing `Mock()`-based tests assert targets but not sources or env fidelity. A recording fake makes every mount-plan assertion direct.

## Risks / Trade-offs

- **[Risk] The `CliDependencies.processor` slot is a new public surface.** If a test sets it and forgets to reset, later tests could run against a stale fake. **Mitigation:** Each test constructs and injects its own `CliDependencies(processor=...)`; the callback builds fresh deps per invocation, so there is no shared state to leak between `CliRunner.invoke` calls.
- **[Risk] Removing `min`/`max` breaks third-party `backends.yaml` files that declare them.** **Mitigation:** Declared `**BREAKING**` in `proposal.md`; pydantic defaults to ignoring unknown keys, so such files fail only if they relied on the (never-enforced) range. The schema test pins the new contract.
- **[Risk] Fake processor drifts from real processor behavior.** **Mitigation:** The fake is duck-typed to `ColorSchemeProcessorPort`; `tests/unit/ports/*` provide structural coverage. Drift manifests as immediate test failures.
- **[Risk] Deleting `test_user_journey.sh` loses the only real-binary end-to-end run.** **Mitigation:** Per-command CliRunner tests preserve its assertions; the bash script's container-runtime detection is covered by the fake-engine container tests. Documented in D3.
- **[Risk] xfail tests mask regressions if reasons go stale.** **Mitigation:** Each xfail is pinned with a `# N.x` comment and a precise `reason`; `-rxX` reporting in verification surfaces them. When a bug is fixed, the test flips to XPASS and demands attention.

## Open Questions

None — the four decision records resolve the previously open seam, journey-script, and xfail-scope questions.
