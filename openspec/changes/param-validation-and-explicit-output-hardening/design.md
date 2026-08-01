## Context

`weg` (wallpaper-effects-generator) has two `--param` parsing implementations — one in `cli/process.py:51` and one in `cli/batch.py:51` — that disagree on malformed input: `process` silently drops entries without `=`, `batch` rejects them. Neither validates keys against the effect catalog, so typos like `--param bliur=0x15` are silently ignored. `batch._run_batch` also silently downgrades `--explicit-output` to `False` when `-o` is absent (`cli/batch.py:75-76`). The catalog (`defaults/effects.yaml`) declares typed parameters per effect (`ParameterDefinition.key`); composites and presets reference existing effects, so all valid parameter names originate from `EffectDefinition.parameters`. The test suite currently locks in the buggy behavior with one `@pytest.mark.xfail` and characterization tests in `tests/test_cli.py` section 8.

## Goals / Non-Goals

**Goals:**
- One shared, strict `--param` parser used by all `process` and `batch` commands.
- Pre-execution rejection of `--param` keys not declared by any in-scope unit, with a distinct `UnknownParamError` surfaced as `typer.BadParameter`.
- Scope-aware validation: single-target commands check against that unit's underlying effects; batch commands check per kind (`effects` / `composites` / `presets` / `all`) so errors and accepted keys match what the command actually runs.
- Preserve mixed-param `batch all` viability: a key declared by *some* unit in scope is accepted globally and applied only where declared (per-target leniency).
- Reject `--explicit-output` without `-o/--output`.
- Replace the `xfail` and section 8 characterization tests with contract tests locking the intended behavior.

**Non-Goals:**
- No change to catalog-load-time validation (`CatalogValidationService`) — catalog may declare params unused by templates; only user-supplied `--param` input is validated.
- No per-target strictness at processing time — `ParameterResolutionService.resolve_all` stays lenient by design.
- No CLI flag renaming or new commands.

## Decisions

### D1. Single shared parser: `cli/_params.py::parse_params`
Both `process` and `batch` import a single `parse_params(raw: list[str]) -> dict[str, str]` that raises `typer.BadParameter` on any entry lacking `=` or with an empty key after `strip()`. Rationale: removes the duplicated code that caused the `process`/`batch` divergence. The `process` behavior change (silently skip → reject) is the intended fix, not a `batch` change. Alternative considered: keeping two parsers and only patching `process` — rejected; it leaves the divergence latent.

### D2. Scope-aware unknown-key validation: `cli/_params.py::assert_params_known`
A single validator:
```python
def assert_params_known(user_params, scope_units, scope_label) -> None:
    union = set()
    for unit in scope_units:
        union |= {p.key for p in unit.parameters}
    unknown = set(user_params) - union
    if unknown:
        raise UnknownParamError(sorted(unknown), scope_label, sorted(union))
```
`scope_units` is always a flat list of `EffectDefinition` (the only unit kind that declares params). Composites and presets are dereferenced to their underlying effects. Rationale: strictness lives at one pre-execution boundary instead of in the resolver, avoiding false positives deep in processing. The zero-param single-target reject (e.g. `process effect blackwhite --param x=1`) falls out automatically: scope = `{blackwhite}`, union = `{}`, any key raises — no special case.

### D3. Per-kind batch scope assembly
`build_scope_units(catalog, item_types)` expands the catalog per batch kind:
- `batch effects`: all catalog effects.
- `batch composites`: step-effects of all composites (dedup by name).
- `batch presets`: effects referenced by all presets (dedup by name).
- `batch all`: all catalog effects (composite/preset effects are a subset).
Rationale: correct per-kind unions. `batch composites --param contrast=40` must reject because no composite references the `contrast` effect, even though `contrast` is declared by the `contrast` effect. This was the user's explicit requirement ("one validator but proper separation of the error per kind"). Error messages read `Unknown parameter(s) [...] for batch composites. Valid: [...]`.

### D4. Union-set batch semantics: globally strict, per-target lenient
For multi-target batch commands, validation is against the *union* of declared keys across in-scope units, applied **before** any item is processed (decision: raise before). A user key valid for any unit in scope passes; units apply only the keys they declare (`resolve_all` unchanged). Rationale: makes `batch all --param blur=5x3 --param brightness=10` viable while still catching keys valid nowhere (`--param typo=1`). Alternative considered: per-target strict at execution — rejected; it reintroduces the false-positive failure mode on zero-param effects that the user explicitly rejected.

### D5. Distinct `UnknownParamError` in `domain/exceptions.py`
New exception carrying `unknown_keys`, `scope_label`, `valid_keys`, message `Unknown parameter(s) [...] for <scope>. Valid: [...] or (none declared).` Added to `__all__`. Rationale: user decision — distinct type over reusing `ConfigResolutionError`, giving clean type-based handling and precise messages.

### D6. `--explicit-output` requires `-o/--output`
`cli/batch.py:_run_batch` raises `typer.BadParameter("--explicit-output requires -o/--output")` in place of `explicit_output = False`, before catalog resolution. Rationale: a flag requesting direct-write behavior must not silently degrade; the user explicitly chose hard reject.

### D7. New public lookup: `EffectsCatalog.find_effect(name)`
Scope assembly needs catalog→effect dereferencing. Processors keep private `_lookup_effect` raising `EffectNotFoundError`; a small public `find_effect` on the catalog (or reuse of an existing lookup) provides the same semantics for `_params.py`. Verify during implementation whether such a helper already exists; if not, add it to `domain/models.py`.

### D8. CLI error surfacing
Each `process` command and `_run_batch` wraps only `assert_params_known` in `try/except UnknownParamError → raise typer.BadParameter(str(e))`. Processing calls are not wrapped because the resolver stays lenient and cannot raise `UnknownParamError`.

## Risks / Trade-offs

- **Breaking behavior change (malformed/unknown params now error)** → Mitigation: clear `BadParameter` messages name the offending key(s) and valid keys; documented in proposal as breaking. Mixed-param `batch all` remains viable so legitimate workflows are unaffected.
- **Per-kind unions are narrower than the all-effects union** → Mitigation: intended — `batch composites --param contrast=40` correctly errors; error message includes the per-kind valid list so users see why.
- **Long error messages for `batch all`** (7 keys in default catalog) → Accepted: completeness over terseness; bounded by catalog size.
- **New public API `find_effect`** → Mitigation: minimal addition; mirrors existing private lookups; no behavior change.
- **Upfront batch validation needs catalog resolution before processing** → Already satisfied: `_run_batch` resolves `settings, catalog = _resolve_context(...)` before building `BatchRequest`.

## Migration Plan

Single-step code change; no data migration. Rollback: revert commit; prior behavior returns (silent drops restored) with the characterization tests intact. No deployment surface beyond the CLI tool.
