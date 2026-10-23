## ADDED Requirements

### Requirement: Per-CLI output adapters route through cli-output

Each CLI's concrete output adapters (`JsonOutputAdapter`/`PlainOutputAdapter`/`RichOutputAdapter` for WEG; `JsonOutput`/`PlainOutput`/`RichOutput` for CSG) SHALL be thin projectors: they SHALL hold a `cli_output.Renderer` built by `cli_output.create_renderer(...)` and SHALL delegate all rendering to that renderer's verb methods or context managers. The per-CLI `factory.create_output_adapter(...)` SHALL construct the shared renderer (from the CLI's `OutputFormat`) and inject it into the adapter. Each CLI's `OutputPort` protocol and method signatures SHALL remain unchanged.

#### Scenario: WEG factory builds a renderer-backed JSON adapter

- **WHEN** `wallpaper_effects_generator.factory.create_output_adapter(OutputFormat.JSON)` is invoked
- **THEN** the returned adapter is a `JsonOutputAdapter` whose `_renderer` is a `cli_output` `JsonRenderer`

#### Scenario: CSG factory builds a renderer-backed plain adapter

- **WHEN** `color_scheme_generator.factory.create_output_adapter(OutputFormat.PLAIN)` is invoked
- **THEN** the returned adapter is a `PlainOutput` whose `_renderer` is a `cli_output` `PlainRenderer`

#### Scenario: adapters remain structurally conformant to OutputPort

- **WHEN** `isinstance(JsonOutputAdapter(), OutputPort)` and `isinstance(JsonOutput(), OutputPort)` are evaluated
- **THEN** both evaluate `True`

### Requirement: Domain results project to shared views via a per-CLI projector

Each CLI SHALL provide an `adapters/output/projectors.py` module of pure functions mapping its domain types to `cli_output` views. WEG SHALL project `ProcessingResult` to `ResultView`, `BatchResult` to a `CustomView`, `EffectsCatalog`+query to a `CustomView`, `AppSettings`+catalog+sources to a `CustomView`, and exceptions to `ErrorView`. CSG SHALL project `GenerationResult` to a `CustomView`, `ColorSchemeError` to an `ErrorView` (with `details` from a single shared `_error_details` projector), `ColorScheme` to a `CustomView` (palette), and config/install/uninstall/version/backends to `CustomView`s.

#### Scenario: WEG process_result delegates to renderer.result

- **WHEN** a WEG `JsonOutputAdapter.process_result(ProcessingResult)` is invoked with a captured stdout
- **THEN** stdout contains a JSON object with `"success": true`
- **AND** the object includes `command`, `return_code`, and `duration` keys

#### Scenario: CSG error details come from one projector

- **WHEN** a CSG `JsonOutput.error(InvalidImageError)` is invoked with captured stderr
- **THEN** stderr contains a JSON object with `"kind": "InvalidImageError"` and `"details": {"image_path": ..., "reason": ...}`

### Requirement: Errors render to stderr in all three backends

The per-CLI adapters SHALL render `error(...)` through the shared renderer's `error` method, which SHALL write to `sys.stderr` in the JSON, plain, and rich backends. Rich and plain errors that previously wrote to stdout SHALL now write to stderr.

#### Scenario: WEG plain error goes to stderr

- **WHEN** a WEG `PlainOutputAdapter.error(ValueError("bad"))` is invoked with stdout and stderr captured
- **THEN** stderr contains `error: ValueError: bad`
- **AND** stdout receives nothing

#### Scenario: CSG rich error goes to stderr

- **WHEN** a CSG `RichOutput.error(InvalidImageError(...))` is invoked with stdout and stderr captured
- **THEN** stderr contains the error text
- **AND** stdout receives nothing

### Requirement: dump-* commands override the output format

`weg dump-config` and `weg dump-effects` SHALL write the bundled template content verbatim to stdout regardless of `--output-format`. `csg dump-config` SHALL write the bundled template verbatim to stdout regardless of `--output-format`. Neither SHALL wrap the content in the chosen format (e.g. JSON must NOT wrap it in `{"content": ...}`).

#### Scenario: weg dump-config with JSON format prints raw TOML

- **WHEN** `weg --output-format json dump-config` is invoked
- **THEN** stdout starts with the raw bundled `settings.toml` content (e.g. `version = "1.0"`)
- **AND** stdout is not a JSON object

#### Scenario: csg dump-config with JSON format prints raw TOML

- **WHEN** `csg --output-format json dump-config` is invoked
- **THEN** stdout starts with the raw bundled `settings.toml` content
- **AND** stdout is not a JSON object

### Requirement: CSG process_result preserves curated output via CustomView

CSG SHALL project `GenerationResult` to a `cli_output.CustomView` whose `object` field carries the structured payload (unchanged JSON shape), `plain` field carries the curated plain-text lines, and `rich` field is a callable drawing the styled table and output files. A generic `ResultView` SHALL NOT be used for CSG `process_result` (it would render the nested `color_scheme` dict into plain text).

#### Scenario: CSG JSON process_result shape is unchanged

- **WHEN** a CSG `JsonOutput.process_result(GenerationResult)` is invoked with captured stdout
- **THEN** the parsed JSON has `success`, `color_scheme`, `output_files`, `backend`, `duration`, and `command` keys

#### Scenario: CSG plain process_result stays curated

- **WHEN** a CSG `PlainOutput.process_result(GenerationResult)` is invoked with captured stdout
- **THEN** stdout contains the `Success`, `Backend:` and `Duration:` lines (not a raw `color_scheme` dict repr)

### Requirement: QUIET verbosity gating is preserved in CSG

CSG's `OutputAdapterBase` SHALL keep the `_verbosity` attribute and SHALL short-circuit `process_result` when verbosity is `Verbosity.QUIET`, so `--quiet` continues to suppress result output. The shared renderer SHALL remain verbosity-agnostic.

#### Scenario: CSG quiet suppresses process_result

- **WHEN** a CSG `JsonOutput(verbosity=Verbosity.QUIET).process_result(result)` is invoked with stdout captured
- **THEN** stdout receives nothing
