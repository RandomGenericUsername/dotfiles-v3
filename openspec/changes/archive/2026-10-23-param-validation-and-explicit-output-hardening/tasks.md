## 1. Domain primitives

- [x] 1.1 Add `UnknownParamError(WallpaperEffectsError)` to `src/wallpaper_effects_generator/domain/exceptions.py` carrying `unknown_keys`, `scope_label`, `valid_keys`, with message format `Unknown parameter(s) [...] for <scope>. Valid: [...] or (none declared).` and add to `__all__`
- [x] 1.2 Add public `EffectsCatalog.find_effect(name) -> EffectDefinition` to `domain/models.py` raising `EffectNotFoundError` for unknown names (mirror the processors' private lookup)
- [x] 1.3 Export `UnknownParamError` via `domain/exceptions` re-exports if any exist (`domain/__init__.py`)

## 2. Shared param parser and validator (`cli/_params.py`)

- [x] 2.1 Create `src/wallpaper_effects_generator/cli/_params.py` with `parse_params(raw: list[str]) -> dict[str, str]` that raises `typer.BadParameter` on missing `=` or empty (post-strip) key
- [x] 2.2 Add `assert_params_known(user_params, scope_units, scope_label)` to `cli/_params.py` computing the union of declared keys over `scope_units` (list of `EffectDefinition`) and raising `UnknownParamError` for keys absent from the union
- [x] 2.3 Add `build_scope_units(catalog: EffectsCatalog, item_types: tuple[ItemType, ...]) -> list[EffectDefinition]` to `cli/_params.py` with per-kind expansion (effects = all effects; composites = deduped step-effects; presets = deduped referenced effects; all = all effects) using `EffectsCatalog.find_effect`
- [x] 2.4 Add a small label helper mapping `item_types` to the batch scope label (`effects` / `composites` / `presets` / `all`) used in error messages

## 3. CLI integration

- [x] 3.1 Remove `_parse_params` from `cli/process.py` and `cli/batch.py`; replace call sites with `parse_params` from `_params`
- [x] 3.2 In `cli/process.py` `effect` command: assemble single-effect scope, call `assert_params_known` wrapped in `try/except UnknownParamError → typer.BadParameter`, before processor call
- [x] 3.3 In `cli/process.py` `composite` command: assemble step-effects scope for the named composite, validate as in 3.2
- [x] 3.4 In `cli/process.py` `preset` command: assemble referenced-effects scope for the named preset, validate as in 3.2
- [x] 3.5 In `cli/batch.py` `_run_batch`: replace the `explicit_output = False` downgrade with `raise typer.BadParameter("--explicit-output requires -o/--output")`
- [x] 3.6 In `cli/batch.py` `_run_batch`: after `_resolve_context`, validate params via `build_scope_units(catalog, item_types)` + `assert_params_known` (wrapped to surface `BadParameter`) before constructing `BatchRequest`

## 4. Test rewrite — remove characterization lock-in

- [x] 4.1 In `tests/test_cli.py`, remove `test_process_malformed_param_silent_drop` and its `@pytest.mark.xfail` decorator
- [x] 4.2 Replace section 8.1/8.2 with a parametrized malformed-param contract test over `["process", "batch"]` × `["badparam", "=5", "  =5"]` asserting non-zero exit and `Invalid param format`
- [x] 4.3 Rewrite `test_explicit_output_without_output_flag` → assert non-zero exit and `--explicit-output requires`; add `test_explicit_output_with_o_succeeds` (exit 0, flat output under `-o`)
- [x] 4.4 Remove or fold `test_batch_malformed_param_raises` into the parametrized contract test (avoid duplicate coverage)

## 5. New param-validation contract suite

- [x] 5.1 Create `tests/unit/cli/test_param_validation.py` with tests for: single effect unknown key (`bliur`), zero-param effect reject (`blackwhite` + `brightness`), composite scope unknown key, composite accepts per-step keys, `batch effects` accepts declared key
- [x] 5.2 Add batch per-kind scoping tests: `batch composites --param contrast=40` rejected with `for batch composites` and valid list excluding `contrast`; `batch presets` unknown key rejected; `batch all` unknown key rejected
- [x] 5.3 Add union-set lock tests: `batch all` mixed declared keys → exit 0; `batch all` partially-unknown set (`blur` + `typo`) → non-zero naming `typo`
- [x] 5.4 Add strict-mode-before-execution test: `batch effects --strict --param typo=1` → non-zero and `FakeProcessor.calls == []`
- [x] 5.5 Add happy-path regression guard: `process effect blur --param blur=5x3` with `FakeProcessor` → exit 0 and `fp.calls[0]["params"]["blur"] == "5x3"`

## 6. Resolver leniency lock

- [x] 6.1 In `tests/test_services.py` `TestParameterResolutionService`, add `test_resolve_all_ignores_unknown_keys` (no raise, only declared keys resolved) and `test_resolve_all_accepts_empty_overrides`
- [x] 6.2 Confirm no source change to `resolve_all` was needed (leniency is the contract)

## 7. Verification

- [x] 7.1 Run `uv run pytest -rX` from `src/cli-tools/wallpaper-effects-generator` — expect 0 xfailed, all tests green
- [x] 7.2 Run `uv run ruff check .` — no violations
- [x] 7.3 Run `uv run ruff format --check .` — formatting clean
