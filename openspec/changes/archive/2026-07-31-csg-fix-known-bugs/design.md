# CSG Fix Known Bugs

## Context

The archived `2026-07-31-csg-test-characterization` change hardened the csg test suite and, as task §8, flagged four discovered behavioral inconsistencies as `@pytest.mark.xfail` tests "for later triage". This change is that triage. All four are genuine defects — the codebase claims contracts it silently violates — and all eight xfails share a second problem: `strict=False` with no CI gate means the "demand attention when fixed" promise (design.md D4 of the prior change) is not enforced anywhere.

The four defects:

1. `OutputSettingsSchema.default_formats: list[str]` has no validator; invalid values only fail late at `ColorFormat(f)` in `cli/main.py`.
2. `_schema_to_domain` hardcodes `min_version="0.0.0"`; `BackendDefinitionSchema` lacks the field so YAML-declared `min_version` is silently dropped.
3. The hand-written `--help` string lists 4 config strategies while the resolver chain has 5 (`CliPathStrategy` first).
4. `install`/`uninstall`/`version`/`list-backends` reach the user through `isinstance(adapter, ...)` dispatch and adapter-private methods, bypassing `OutputPort`.

The architecture makes all four fixes local and low-risk: schema validators already exist for sibling fields (`backend`, `mode`, `engine`, `memory_limit`, `timeout_seconds`); `BackendDefinitionSchema` is pydantic so adding an optional field is backward-compatible; the `OutputPort` is a runtime-checkable Protocol whose conformance is structurally tested by `tests/unit/ports/*`; and the 4 command files already funnel through `deps.output_adapter` — only the dispatch block changes.

## Goals / Non-Goals

**Goals:**
- Fix all four defects so the eight xfail tests become real passing characterization tests.
- Lock the now-correct behavior: schema rejects invalid `default_formats`; YAML-declared `min_version` round-trips; `--help` lists all 5 strategies; the 4 commands route through `OutputPort`.
- Enforce xfail discipline going forward: `--strict-markers -rxX` so stale xfails and unknown markers fail CI.

**Non-Goals:**
- No changes to csg domain models, ports other than `output.py`, factory, or shared libraries.
- Not rewriting the mock-heavy `install`/`uninstall`/`list-backends`/`info`/`dump-*` command tests to observable-output assertions (audit finding R1/R5). They mock the container engine, not the output port, so they keep passing unchanged; a separate follow-up change will address them.
- No new external dependencies, no container-image behavior changes.

## Decisions

### D1: Validate `default_formats` against `ColorFormat` enum values, keep field type `list[str]` (validate-not-coerce)

**Choice**: Add a `@field_validator("default_formats")` on `OutputSettingsSchema` that raises `ValueError` if any entry is not in `{m.value for m in ColorFormat}`. The field remains `list[str]`.

**Rationale**: Coercing to `ColorFormat` at the schema boundary would change the observable schema output type and break `test_schema.py`'s `schema.output.default_formats == ["json", "sh"]` equality assertion. Validation-only fixes the defect (rejecting garbage early) while preserving the existing contract where the serializer (`settings_serializer.py`) owns enum coercion downstream in `cli/main.py`. This matches how sibling fields are handled: `backend`/`mode`/`engine` validate against enum *values* while storing the raw string.

**Alternatives considered**:
- Coerce to `list[ColorFormat]`: cleaner type, but breaks the serializer contract and the `["json","sh"]` assertion; deferred enum coercion is an established pattern. Rejected.
- Leave unvalidated: preserves the bug. Rejected.

### D2: Add `min_version` as an optional field on `BackendDefinitionSchema` (additive, backward-compatible)

**Choice**: Add `min_version: str = "0.0.0"` to `BackendDefinitionSchema`; `_schema_to_domain` passes `def_schema.min_version` instead of the literal `"0.0.0"`.

**Rationale**: Existing YAML catalogs that omit `min_version` keep the prior `"0.0.0"` value (backward-compatible); catalogs that declare it now round-trip. The domain `BackendDefinition` already has the `min_version` slot, so no domain change is required.

**Alternatives considered**:
- Keep hardcoding and delete the domain slot: would make `min_version` unavailable to consumers of `list-backends`/catalog display. Rejected — the slot exists precisely to carry this.
- Remove `min_version` entirely: out of scope, changes the domain model. Rejected.

### D3: Rewrite the hand-written `--help` string to mirror the resolver chain

**Choice**: Add `1. --config flag` as the first numbered settings-discovery step and renumber 2-5, matching the 5-strategy `AssembledConfigResolver` chain (`CliPathStrategy` → `EnvPathStrategy` → `DirectoryTraversalStrategy` → `XdgStrategy` → `DefaultFileStrategy`).

**Rationale**: `--help` is a user-facing contract; it must reflect the actual resolution priority. The templates-directory block and ENV-overrides line are unaffected.

### D4: Extend `OutputPort` with 4 named methods; move per-adapter rendering into adapters

**Choice**: Add `install_result(results: list[dict])`, `uninstall_result(results: list[dict])`, `version_info(version: str)`, `backends_catalog(backends: list[dict], hint: str = "")` to the `OutputPort` Protocol. Implement each on `JsonOutput`, `RichOutput`, `PlainOutput` by relocating the inline `print(...)`/`Table` code currently in the command files. The command files call `deps.output_adapter.<method>(...)` and drop the `isinstance` dispatch + the now-unused imports.

**Rationale**: Named methods match the existing convention (`process_result`, `palette_display`, `config_info`, `message`). A generic `render(payload, kind)` would lose type safety and diverge from the codebase style. Moving the rendering code into the adapters makes each command file port-boundary-clean: the command computes results, the adapter renders.

**Alternatives considered**:
- One generic `render(payload: dict, kind: str)`: fewer methods but loses per-command signatures and diverges from style. Rejected (user chose 4 named methods).
- Keep `print_table` as a rich-only escape hatch: retained (existing public method) but no longer needed by these commands.

### D5: Remove the 8 xfail markers; harden pytest config

**Choice**: Delete all 8 `@pytest.mark.xfail` decorators (the tests now pass as real characterization tests). Add `addopts = ["--strict-markers", "-rxX"]` to `pyproject.toml`.

**Rationale**: Once the bugs are fixed, the xfail tests encode the correct contract and must run unconditionally. `--strict-markers` fails on unknown markers; `-rxX` makes xpass/xfail reporting explicit in CI output — so any future `strict=False` xfail that silently xpasses is surfaced. With 0 xfails remaining, the strict=True migration question is moot.

## Risks / Trade-offs

- **[Risk] `OutputPort` Protocol extension breaks out-of-tree adapters.** **Mitigation:** No out-of-tree adapters exist in this repo; the conformance fakes (`test_interfaces.MockOutput`) and the recording adapter in `test_known_bugs.py` are updated in the same change. Declared `**BREAKING**` in `proposal.md`.
- **[Risk] `default_formats` validator rejects previously-accepted values.** **Mitigation:** This is the point of the fix. Existing test fixtures use valid values (`()` / `["json","sh"]` / `ColorFormat.JSON`); verified no test constructs invalid formats outside the two former xfails.
- **[Risk] Help-text change breaks tests asserting the old 4-step list.** **Mitigation:** Searched `tests/` — no test asserts the old enumeration; only the former xfail asserts the new 5-step list.
- **[Risk] Command refactor changes observable output.** **Mitigation:** The rendering code was moved verbatim into adapter methods (same print statements, same Table construction). Verified via manual CLI runs across all 3 formats and the full test suite.

## Open Questions

None — all four defects are unambiguous bugs; scope decisions (D1-D5) were resolved with the user before implementation.