## Why

The `weg` CLI validates `--param` overrides inconsistently: `process` subcommands silently drop malformed values (missing `=`) and unknown keys, while `batch` subcommands reject missing `=` but silently ignore unknown keys against zero-param effects. Additionally, `--explicit-output` without `-o` is silently downgraded to `False`, hiding user intent. The test suite encodes this questionable behavior (one `xfail` plus characterization tests) instead of locking the intended capability: strict, consistent validation of `--param` input against the actual effect/composite/preset definitions.

## What Changes

- **Shared param parser** — Hoist `_parse_params` into a single `cli/_params.py::parse_params` used by both `process` and `batch` command groups. Rejects any entry without `=`, and rejects entries with an empty key after stripping whitespace (e.g. `--param =5`).
- **`process` rejects malformed params** — `process effect/composite/preset --param badparam` now exits non-zero with a `BadParameter` error (previously silently dropped; was the `xfail`). **BREAKING**: behavior change for previously-silent invalid input.
- **`--explicit-output` requires `-o/--output`** — `batch` raises `BadParameter("--explicit-output requires -o/--output")` instead of silently treating the flag as `False`. **BREAKING**: previously-silent downgrade is now a hard error.
- **Unknown-key validation (typo detection)** — New distinct `UnknownParamError`. Before any processing, validate every user-supplied `--param` key against the union of declared param names across the command's in-scope target units:
  - Single-target `process` commands scope to that one unit's underlying effects.
  - Batch commands scope per kind (`effects` / `composites` / `presets` / `all`) so error messages and accepted key sets correctly reflect the targets that kind actually runs.
  - A key valid for *some* unit in scope is accepted globally and applied only to the units that declare it (per-target leniency preserved); a key valid for *no* unit in scope is rejected before anything executes.
  - Zero-param single-target units (e.g. `blackwhite`) reject any param — the degenerate case of the union rule, not a special case.
- **Resolver stays lenient** — `ParameterResolutionService.resolve_all` is unchanged; per-target silent application of applicable keys is the intended contract, now locked by an explicit test.
- **Test suite rewritten** — Remove the `xfail`; replace the section 8.1–8.3 characterization tests with contract tests that lock the intended behavior, including the mixed-param `batch all` union-set semantics, per-kind batch scoping, and a happy-path regression guard.

## Capabilities

### New Capabilities
- `weg-param-validation`: CLI-level validation of `--param` input — shared strict parsing (rejects missing `=` and empty keys), pre-execution unknown-key rejection against a scope-aware union of declared param names, distinct `UnknownParamError`, and `--explicit-output` requiring `-o`.

### Modified Capabilities
- (none — no existing spec covers `--param` validation semantics)

## Impact

- **Source files**:
  - `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/_params.py` (new) — `parse_params`, `assert_params_known`, scope-assembly helpers.
  - `cli/process.py`, `cli/batch.py` — import shared parser, call scope validator, surface `UnknownParamError` as `typer.BadParameter`.
  - `domain/exceptions.py` — add `UnknownParamError`.
  - `domain/models.py` — add `EffectsCatalog.find_effect` (public lookup needed for scope assembly).
  - `domain/services.py` — no change to `resolve_all` (intentionally lenient).
- **Tests**:
  - `tests/test_cli.py` — remove xfail + rewrite section 8.1/8.3.
  - `tests/unit/cli/test_param_validation.py` (new) — param-validation contract suite.
  - `tests/test_services.py` — add lenient-resolver contract test.
- **Behavior**: `process` no longer silently accepts malformed `--param`; `batch` no longer silently downgrades `--explicit-output`; typos in `--param` keys raise a clear error naming unknown and valid keys.
