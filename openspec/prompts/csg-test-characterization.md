# CSG Test Characterization & Hardening — Agent Task

You are working in the repo `dotfiles-repo-v3`, a Python monorepo of
hexagonal-architecture Typer CLIs. Two tools matter here:

- WEG: `src/cli-tools/wallpaper-effects-generator/`
- CSG: `src/cli-tools/color-scheme-generator/`

## Mission

Perform the SAME characterization + test-hardening work for **CSG** that
was already done for **WEG**. Study the WEG precedent FIRST, then mirror
its methodology and rigor for CSG. Do not invent new abstractions; reuse
the exact patterns WEG established.

## Step 1 — Study the WEG precedent (mandatory reading)

Read these files before writing any code:

1. `openspec/changes/weg-test-characterization/proposal.md`
2. `openspec/changes/weg-test-characterization/design.md`
3. `openspec/changes/weg-test-characterization/tasks.md`
4. `openspec/changes/weg-test-characterization/specs/*/spec.md`
5. WEG test files it produced:
   - `src/cli-tools/wallpaper-effects-generator/tests/conftest.py` (the
     `_FakeProcessor` + `WEG_TEST_DEPS` seam usage pattern)
   - `.../tests/unit/adapters/test_config_resolution_chain.py`
   - `.../tests/unit/adapters/test_container_processor.py` (the
     `_FakeEngine` mount-plan assertions)
   - `.../tests/test_cli.py` (CliRunner-based command characterization)
   - `.../tests/unit/adapters/schemas/test_settings_schema_validators.py`

## Step 2 — Audit CSG's current suite

Run and analyze `pytest src/cli-tools/color-scheme-generator/tests/ -q`.
Determine what is genuinely tested vs. mock-plumbing. Specifically check
for WEG-equivalent gaps:

1. **Mock-heavy CLI tests**: do CSG CLI tests monkeypatch
   `create_local_processor`/`create_container_processor`/`build_deps`
   and assert on mocks, or do they drive the real `app` via
   `typer.testing.CliRunner` with fakes at port boundaries and assert
   observable output?
2. **Resolution chain coverage**: does anything test the full
   `AssembledConfigResolver` priority chain — CLI path >
   `COLORSCHEME_CONFIG_FILE_PATH` env > CWD traversal (max_levels=3) >
   XDG (`~/.config/color-scheme-generator/`) > package default — plus
   `COLORSCHEME__SECTION__KEY` double-underscore ENV overrides and
   `cli_overrides` precedence? (Source:
   `.../adapters/settings/config_resolver.py`.)
3. **Container mount-plan assertions**: does `test_container_processor.py`
   assert the full mount plan (all 4 `ContainerMount` sources/targets,
   `_CONTAINER_ENV` dict, serialized temp settings.toml validity,
   cleanup on success/exception, `ContainerImageNotFoundError`,
   input-parent-is-`/` guard, `template_dir_resolver` wiring)?
4. **Serializer round-trips**: settings serializer, backend catalog
   loader, template catalog loader — any lossy field drops on
   deserialize (compare against WEG's `EffectsSerializer` fix)?
5. **Output adapter coverage**: rich/plain/json output adapters — full
   coverage of every public method (`process_result`,
   `batch_result`/equivalent, catalog/info display)?
6. **Schema validators**: `backends_catalog_schema.py`,
   `settings/schema.py` — are validators (engine whitelist, registry
   constraints) directly tested?
7. **Global flags**: `--output-format json|rich|plain`, `-q`/`--quiet`,
   `-v`/`--verbose` behavior through the real CLI?
8. **Error paths**: missing input file, missing config, invalid backend,
   container-runtime-unavailable, error-mapping through `map_oci_error`?

## Step 3 — Deliverables

Produce an OpenSpec change directory
`openspec/changes/csg-test-characterization/` (mirroring the WEG change's
file layout: `proposal.md`, `design.md`, `tasks.md`, `README.md`,
`specs/<capability>/spec.md` for each capability) and the test suite
changes it describes.

Follow WEG conventions exactly:

### 3a. Test seam
CSG's `cli/main.py` callback builds deps via `build_deps()`. Choose the
least-invasive seam that lets tests inject fake `CliDependencies` into
the real Typer app (WEG used an env-var + module-global seam; CSG may
simply need to monkeypatch `build_deps` or `create_local_processor` /
`create_container_processor` since the callbacks call them — document
your choice in `design.md` with a decision record like WEG's D1). Keep
the production path unchanged.

### 3b. CLI characterization tests
Rewrite/extend CSG CLI tests to drive the real `app` via `CliRunner`,
faking only at the processor/engine/backend-generator port boundary.
Cover ALL commands: `generate`, `show`, `install`, `uninstall`, `info`,
`dump-config`, `dump-templates`, `list-backends`, `version`, plus the
completion option and global flags. Assert observable output — `exit_code`,
files under `tmp_path`, stdout JSON structure — NOT mock call counts.
Flag any real behavior (lazy processor construction, runtime mode
resolution) with concrete tests.

### 3c. Resolution chain + ENV override tests
New `tests/unit/adapters/settings/test_config_resolution_chain.py`
(parallel to WEG's `test_config_resolution_chain.py`): CLI-path-prevails,
`COLORSCHEME_CONFIG_FILE_PATH` priority, CWD traversal at depth 0/1/2
found and depth-3 falls through, XDG standard + custom `XDG_CONFIG_HOME`,
package-default fallback, `COLORSCHEME__SECTION__KEY` nesting
(`runtime.mode`, `container.engine`, `output.directory`), and
`cli_overrides` precedence over ENV.

### 3d. Container mount-plan tests
Harden `tests/unit/adapters/test_container_processor.py` with a
recording fake runtime (mirror WEG's `_FakeEngine`): assert all 4
`ContainerMount`s (config, templates, input, output) with correct
`source`/`target`/`read_only`, `environment == _CONTAINER_ENV`, serialized
temp settings.toml validity, cleanup on success and exception,
`ContainerImageNotFoundError` when `image_exists()` is False,
input-parent-at-`/` rejection, `process_show` mount differences, and the
interface-contract test that runs the adapter's inner argv through the
live CLI parser (see `openspec/changes/container-adapter-decoupling/`).

### 3e. Lossy deserialization fixes
If any serializer/catalog loader drops fields on round-trip (mirror WEG's
`EffectsSerializer` fix), fix it additively and pin it with round-trip
equality tests. If none are lossy, say so explicitly in `proposal.md`.

### 3f. XFail flags for known bugs
Flag, do not fix, any behavioral inconsistencies you discover — each as
an `@pytest.mark.xfail(reason="...")` test that asserts the CORRECT
behavior (so the test goes green when the bug is fixed). Also fix stale
xfails the same way the WEG suite was cleaned up. Document every xfail
with a numbered comment like WEG's `# 8.x` style.

## Step 4 — Verification

- `python -m pytest src/cli-tools/color-scheme-generator/tests/ -q` —
  all non-xfail tests pass; xfail tests report as expected (use
  `-rxX` to see reasons). Goal: 0 unexpected failures, no collection
  errors.
- `ruff check src/cli-tools/color-scheme-generator/`
- `ruff format --check src/cli-tools/color-scheme-generator/`
- Run the WEG suite too to confirm you did not regress the shared
  `config-assembler-engine` or `oci-runtime` behavior:
  `python -m pytest src/cli-tools/wallpaper-effects-generator/tests/ -q`

## Constraints

- Do NOT change CSG domain, ports, or the `oci-runtime`/`config-assembler-engine`
  shared libraries, unless a lossless round-trip fix is strictly required.
- Do NOT build/modify container images; container-mode tests must fake the
  engine.
- Do NOT delete `test_user_journey.sh` unless you replace its assertions
  with CliRunner tests exactly as WEG replaced `test.sh`.
- No new external dependencies.
- Update `openspec/changes/csg-test-characterization/tasks.md` with
  checkboxes as you complete work; mark all done only when the final
  verification passes.

Report back: the gap analysis (Step 2 findings), the decision records,
the final test counts, and any xfail tests you added with their reasons.
