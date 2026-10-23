## Why

The shared `cli-output` package (landed in `cli-output-shared`) is additive-only: both WEG and CSG declare it as a dependency but their output adapters still render directly to `sys.stdout`/`sys.stderr`/`rich.Console`, duplicating the three-backend logic and carrying copy-pasted error-detail introspection tables (CSG's `_serialize_error`/`_format_error_details` across three adapters). This change wires the shared renderer into both CLIs, converting each per-domain `OutputPort` adapter into a thin projector that translates domain results into `cli-output` views and delegates rendering to the shared `Renderer` — the payoff the shared package was built for.

## What Changes

1. **WEG adapters become thin projectors.** `JsonOutputAdapter`, `PlainOutputAdapter`, `RichOutputAdapter` collapse to a shared `OutputAdapterBase` (new `adapters/output/base.py`) that holds a `cli_output.Renderer` built by `create_renderer`; a new `adapters/output/projectors.py` maps `ProcessingResult`/`BatchResult`/`EffectsCatalog`/`AppSettings`/exceptions into `ResultView`/`CustomView`/`ErrorView`/`MessageView`. `factory.create_output_adapter` now builds the renderer via `cli_output.create_renderer(...)` and injects it.
2. **CSG adapters become thin projectors.** Mirror-image change: `JsonOutput`, `PlainOutput`, `RichOutput` share `OutputAdapterBase` + `adapters/output/projectors.py` mapping `GenerationResult`/`ColorSchemeError`/`ColorScheme`/config-info/install/version/backends into views. The three duplicated `_format_error_details`/`_serialize_error` introspection tables collapse into one `projectors._error_details`.
3. **Canonical output shapes.** Rendering now flows through the shared renderers' canonical forms: WEG JSON `process_result` emits `success: true` (was `status: "success"`); errors emit `{kind, message, details}` (was `{"error": {type, message}}`) to **stderr** in all three backends (rich/plain errors previously went to stdout). Tests updated to the canonical shapes.
4. **CSG `process_result` uses `CustomView`.** The generated color-scheme output preserves its curated plain/rich forms via the designed escape hatch (`CustomView`), rather than a generic `ResultView` that would dump the nested `color_scheme` dict into plain text.
5. **`dump-*` format override preserved.** `weg dump-config`/`dump-effects` and `csg dump-config` print the raw bundled template regardless of `--output-format` (they bypass the renderer's format); verified end-to-end with `--output-format json`.
6. **`JsonRenderer._CustomEncoder` falls back to `str(o)`** for objects it doesn't specially handle (Path/Enum), matching CSG's historical `default=str` leniency so mocked/serialized results keep working.

## Capabilities

### New Capabilities
- `cli-output-integration`: The pattern by which WEG and CSG consume the shared `cli-output` renderer — per-CLI `OutputAdapterBase` projectors, the `projectors.py` domain→view mappings, the `create_renderer` wiring in each `factory.create_output_adapter`, canonical JSON/plain/rich shapes, error-to-stderr routing, and the `dump-*` format override.

### Modified Capabilities
- `cli-output`: Extends the shared-rendering capability with the consumer contract — the shared `JsonRenderer` SHALL stringify unknown objects (not just Path/Enum), and per-CLI output adapters SHALL route through `create_renderer`.
- `csg-output-port-routing`: CSG's `OutputPort` methods now render through the shared renderer; `error` output changes shape from `{"success": false, "error": {...}}` to the canonical `{kind, message, details}` envelope on stderr.

## Impact

- **WEG (6 files):** `adapters/output/base.py` (new), `adapters/output/projectors.py` (new), `adapters/output/{json,plain,rich}_output.py` (rewritten to subclasses of `OutputAdapterBase`), `factory.py` (`create_output_adapter` builds the shared renderer).
- **CSG (6 files):** `adapters/output/base.py` (new), `adapters/output/projectors.py` (new), `adapters/output/{json,plain,rich}_output.py` (rewritten), `factory.py` (`create_output_adapter`).
- **Shared package (1 file):** `cli-output/src/cli_output/adapters/output/json_renderer.py` (`_CustomEncoder` `str(o)` fallback).
- **Tests updated:** WEG `test_{json,plain,rich}_output.py`, `test_process_commands.py`; CSG `test_{json,plain,rich}_output.py`, `test_error_mapping.py`, `test_container_processor.py`, `test_first_run.py`, `test_generate.py`, `test_generate_full.py`, `test_show.py`.
- **Behavior changes:** WEG JSON `process_result` `status`→`success`; error envelope `{kind, message, details}` on stderr for all backends (rich/plain errors move stdout→stderr).
- **No new commands or flags.** Command names, flags, and command surfaces are unchanged.
