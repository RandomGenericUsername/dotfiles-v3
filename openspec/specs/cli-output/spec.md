# cli-output Specification

## Purpose
TBD - created by archiving change cli-output-shared. Update Purpose after archive.
## Requirements
### Requirement: cli-output package structure

The `cli-output` package SHALL live at `src/shared/cli-output/` and SHALL follow hexagonal structure with `domain/`, `ports/`, and `adapters/` directories. It SHALL be a hatchling package named `cli-output` requiring Python `>=3.12`, with `rich>=13` as its only runtime dependency. The package SHALL NOT import any WEG or CSG module, and SHALL NOT introduce Pydantic. The public API SHALL be re-exported from `cli_output/__init__.py`.

#### Scenario: package is importable as cli_output

- **WHEN** the package is installed into an environment
- **THEN** `import cli_output` succeeds
- **AND** `cli_output.OutputFormat`, `cli_output.Renderer`, `cli_output.create_renderer`, and all eight view classes are importable from the top-level package

#### Scenario: no CLI imports leak into the package

- **WHEN** the source tree of `cli_output` is scanned for imports
- **THEN** no `wallpaper_effects_generator` or `color_scheme_generator` import is present

### Requirement: OutputFormat enum

The package SHALL define an `OutputFormat` enum with members `JSON` (value `"json"`), `RICH` (value `"rich"`), and `PLAIN` (value `"plain"`). `str(OutputFormat.JSON)` SHALL return `"json"`, `str(OutputFormat.RICH)` SHALL return `"rich"`, and `str(OutputFormat.PLAIN)` SHALL return `"plain"`.

#### Scenario: enum members serialize to their values

- **WHEN** `str(OutputFormat.JSON)` is evaluated
- **THEN** it returns `"json"`
- **AND** `str(OutputFormat.RICH)` returns `"rich"`
- **AND** `str(OutputFormat.PLAIN)` returns `"plain"`

#### Scenario: enum accepts lowercase construction

- **WHEN** `OutputFormat("json")`, `OutputFormat("rich")`, and `OutputFormat("plain")` are evaluated
- **THEN** each returns the corresponding enum member without error

### Requirement: Renderable views are domain-neutral frozen dataclasses

The package SHALL define eight frozen dataclasses in `domain/views.py`: `MessageView`, `ResultView`, `ListView`, `ErrorView`, `ConfigInfoView`, `RawView`, `ProgressEvent`, and `CustomView`. Each SHALL be a `@dataclass(frozen=True)`. The views SHALL carry no reference to any CLI domain type, exception, or enum. `ErrorView` SHALL have a `kind` field of type `str`, a `message` field of type `str`, and a `details` field of type `dict[str, str]` defaulting to an empty dict. `CustomView` SHALL have a `plain` field of type `str`, an `object` field of arbitrary type, and a `rich` field of type `str | Callable[[Console], None]`.

#### Scenario: views are immutable

- **WHEN** a `MessageView(text="hello")` is constructed
- **THEN** assigning to `view.text` raises `FrozenInstanceError`

#### Scenario: ErrorView kind is an opaque string

- **WHEN** an `ErrorView(kind="invalid_image", message="boom", details={"path": "/x"})` is constructed
- **THEN** the `kind` field holds the string `"invalid_image"`
- **AND** the view is constructible with any arbitrary `kind` string without validation

#### Scenario: CustomView carries pre-built backend forms

- **WHEN** a `CustomView(plain="line", object={"a": 1}, rich="[red]x[/red]")` is constructed
- **THEN** all three fields hold the given values

### Requirement: Renderer port with named verb methods

The package SHALL define a `Renderer` protocol in `ports/renderer.py` annotated with `@runtime_checkable`. The protocol SHALL declare the methods `message(view: MessageView) -> None`, `result(view: ResultView) -> None`, `list(view: ListView) -> None`, `error(view: ErrorView) -> None`, `config(view: ConfigInfoView) -> None`, `raw(view: RawView) -> None`, and `custom(view: CustomView) -> None`. Each SHALL return `None`. The protocol SHALL additionally declare `status(message: str)` returning an `AbstractContextManager[None]` and `progress(total: int, message: str)` returning an `AbstractContextManager` that exposes an `advance()` method.

#### Scenario: renderer protocol is runtime-checkable

- **WHEN** `isinstance` is called on a concrete renderer adapter against `Renderer`
- **THEN** it evaluates `True` for each of the three renderer adapters

#### Scenario: renderer methods are structural

- **WHEN** a class implementing all seven verb methods and both context-manager methods is checked against `Renderer`
- **THEN** `isinstance` evaluates `True`

### Requirement: Three renderer adapters implementing the port

The package SHALL provide `JsonRenderer`, `PlainRenderer`, and `RichRenderer` in `adapters/output/`, each structurally implementing `Renderer`. `JsonRenderer` SHALL emit valid JSON, one object per top-level render call, with an indent of 2 and a trailing newline. `PlainRenderer` SHALL emit human-readable plain text lines. `RichRenderer` SHALL accept an optional `rich.console.Console` in its constructor (defaulting to a new `Console()` when omitted). All three renderers SHALL emit `error(ErrorView)` output to `sys.stderr`, not `sys.stdout`.

#### Scenario: JsonRenderer emits valid JSON

- **WHEN** `JsonRenderer().result(ResultView(success=True, fields={"output_path": "/x.png"}))` is invoked with stdout captured
- **THEN** stdout contains a valid JSON object with `"success": true` and `"output_path": "/x.png"`

#### Scenario: JsonRenderer emits a single JSON object per call

- **WHEN** two consecutive `result(...)` calls are made on the same `JsonRenderer`
- **THEN** stdout contains exactly two newline-separated JSON objects

#### Scenario: RichRenderer accepts an injected Console

- **WHEN** a `RichRenderer` is constructed with a `Console(file=StringIO())` and a `message(MessageView("hi"))` is invoked
- **THEN** the StringIO buffer receives the rendered message

#### Scenario: errors go to stderr in all three backends

- **WHEN** `JsonRenderer().error(ErrorView(kind="x", message="boom"))`, `PlainRenderer().error(ErrorView(kind="x", message="boom"))`, and `RichRenderer().error(ErrorView(kind="x", message="boom"))` are each invoked with both stdout and stderr captured
- **THEN** in every case stderr receives the rendered error
- **AND** stdout receives nothing

### Requirement: create_renderer factory

The package SHALL provide `create_renderer(fmt: OutputFormat, console: Console | None = None) -> Renderer` in `adapters/factory.py`. It SHALL return a `JsonRenderer` for `OutputFormat.JSON`, a `PlainRenderer` for `OutputFormat.PLAIN`, and a `RichRenderer` (passing `console` when provided) for `OutputFormat.RICH`. It SHALL raise `ValueError` for any other value.

#### Scenario: factory dispatches on format

- **WHEN** `create_renderer(OutputFormat.JSON)`, `create_renderer(OutputFormat.PLAIN)`, and `create_renderer(OutputFormat.RICH)` are each invoked
- **THEN** each returns the corresponding renderer type

#### Scenario: factory forwards console to RichRenderer

- **WHEN** `create_renderer(OutputFormat.RICH, console=Console(file=StringIO()))` is invoked
- **THEN** the returned `RichRenderer` writes to the given console

#### Scenario: factory rejects unknown format

- **WHEN** `create_renderer("bogus")` is invoked with a string that is not a valid `OutputFormat`
- **THEN** a `ValueError` is raised

### Requirement: status and progress context managers

`Renderer.status(message: str)` and `Renderer.progress(total: int, message: str)` SHALL return context managers usable with a `with` statement. In `RichRenderer`, `status` SHALL render a live spinner and `progress` SHALL render a progress bar with `total` items and expose an `advance()` method. In `JsonRenderer` and `PlainRenderer`, both SHALL be no-ops that emit nothing to stdout or stderr while still being valid context managers.

#### Scenario: rich status renders a spinner

- **WHEN** `RichRenderer().status("working")` is entered and exited
- **THEN** the console receives the status output

#### Scenario: json status is a silent no-op

- **WHEN** `JsonRenderer().status("working")` is entered and exited with stdout and stderr captured
- **THEN** neither stdout nor stderr receives any output

#### Scenario: rich progress exposes advance

- **WHEN** `RichRenderer().progress(total=3, message="batch")` is entered and `advance()` is called
- **THEN** the progress bar advances by one item

#### Scenario: plain progress is a silent no-op

- **WHEN** `PlainRenderer().progress(total=3, message="batch")` is entered and `advance()` is called with stdout and stderr captured
- **THEN** neither stdout nor stderr receives any output

### Requirement: CustomView escape hatch rendering

All three renderers SHALL render a `CustomView` by emitting its `plain` field verbatim in plain mode, its `object` field serialized in JSON mode, and its `rich` field in rich mode. When the `rich` field is a `Callable[[Console], None]`, `RichRenderer` SHALL invoke it with the renderer's console.

#### Scenario: plain renderer emits custom plain form

- **WHEN** `PlainRenderer().custom(CustomView(plain="a\nb", object={}, rich=""))` is invoked
- **THEN** stdout contains `"a\nb"`

#### Scenario: json renderer serializes custom object form

- **WHEN** `JsonRenderer().custom(CustomView(plain="", object={"palette": ["#111111"]}, rich=""))` is invoked
- **THEN** stdout contains a JSON object with the `palette` key

#### Scenario: rich renderer invokes rich callable

- **WHEN** `RichRenderer(console=Console(file=StringIO())).custom(CustomView(plain="", object={}, rich=lambda c: c.print("swatch")))` is invoked
- **THEN** the console buffer contains `"swatch"`

