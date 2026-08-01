## 1. Scaffold the shared package

- [x] 1.1 Create `src/shared/cli-output/pyproject.toml` mirroring `config-assembler-engine`: `name = "cli-output"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, dependency `rich>=13.0`, hatchling build with `packages = ["src/cli_output"]`, `[tool.uv.sources]`, `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src", "."]`), and the standard `[tool.ruff]` block (target-version `py312`, line-length 100, lint select `["E","F","I","N","W","UP","B"]`, ignore `["B905"]`, quote-style double)
- [x] 1.2 Create `src/shared/cli-output/src/cli_output/__init__.py` re-exporting `OutputFormat`, the eight view classes, `Renderer`, and `create_renderer`
- [x] 1.3 Create package subdirectories with `__init__.py`: `src/shared/cli-output/src/cli_output/domain/`, `ports/`, `adapters/`, and `adapters/output/`
- [x] 1.4 Create `src/shared/cli-output/tests/` directory with `__init__.py`

## 2. Domain layer

- [x] 2.1 Create `domain/enums.py` with `OutputFormat` enum: `JSON = "json"`, `RICH = "rich"`, `PLAIN = "plain"`, with `__str__` returning the value (matching WEG `domain/enums.py:45-51` and CSG `domain/enums.py:52-58`)
- [x] 2.2 Create `domain/views.py` with `MessageView(text: str)` as a frozen dataclass
- [x] 2.3 Add `ResultView(success: bool, fields: dict[str, Any], title: str | None = None)` frozen dataclass
- [x] 2.4 Add `ListView(columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...], title: str | None = None, summary: dict[str, Any] | None = None)` frozen dataclass
- [x] 2.5 Add `ErrorView(kind: str, message: str, details: dict[str, str] = field(default_factory=dict))` frozen dataclass (kind is an opaque string — no validation)
- [x] 2.6 Add `ConfigInfoView(resolved_path: str | None, sources: tuple[str, ...], sections: tuple[tuple[str, dict[str, Any]], ...], applied_overrides: tuple[dict[str, Any], ...] = ())` frozen dataclass
- [x] 2.7 Add `RawView(content: str, content_type: str | None = None)` frozen dataclass
- [x] 2.8 Add `ProgressEvent(phase: str, message: str, done: int | None = None, total: int | None = None)` frozen dataclass
- [x] 2.9 Add `CustomView(plain: str, object: Any, rich: str | Callable[[Console], None])` frozen dataclass
- [x] 2.10 Add `from __future__ import annotations` to `views.py` and `enums.py`

## 3. Ports layer

- [x] 3.1 Create `ports/renderer.py` with `Renderer` protocol using `@runtime_checkable Protocol` and `from __future__ import annotations`
- [x] 3.2 Declare verb methods on `Renderer`: `message(MessageView) -> None`, `result(ResultView) -> None`, `list(ListView) -> None`, `error(ErrorView) -> None`, `config(ConfigInfoView) -> None`, `raw(RawView) -> None`, `custom(CustomView) -> None`
- [x] 3.3 Declare `status(message: str) -> AbstractContextManager[None]` on `Renderer`
- [x] 3.4 Declare `progress(total: int, message: str) -> AbstractContextManager[Progress]` on `Renderer` (the manager exposes `advance()`)
- [x] 3.5 Re-export `Renderer` from `ports/__init__.py` with `__all__`

## 4. Renderer adapters

- [x] 4.1 Create `adapters/output/json_renderer.py` with `JsonRenderer` implementing the seven verb methods; emit one JSON object per call with `indent=2` + trailing newline to stdout; `error` to stderr; a `_CustomEncoder` handling `Path`/`Enum` (mirroring WEG `json_output.py:19-25`)
- [x] 4.2 Implement `JsonRenderer.status` and `JsonRenderer.progress` as silent no-op context managers emitting nothing
- [x] 4.3 Create `adapters/output/plain_renderer.py` with `PlainRenderer` implementing the seven verb methods as plain-text lines (ResultView → `key: value`, ListView → aligned columns, ErrorView → `error: kind: message` to stderr, RawView → verbatim); `status`/`progress` as silent no-op context managers
- [x] 4.4 Create `adapters/output/rich_renderer.py` with `RichRenderer(Console | None = None)` (default `Console()`) implementing the seven verb methods using rich `Table`/`Panel`/markup; `error` renders a red `Panel` to stderr
- [x] 4.5 Implement `RichRenderer.status(message)` returning a `console.status(message)` context manager (live spinner)
- [x] 4.6 Implement `RichRenderer.progress(total, message)` returning a `rich.progress.Progress` context manager with `advance()`
- [x] 4.7 Re-export `JsonRenderer`, `PlainRenderer`, `RichRenderer` from `adapters/output/__init__.py` with `__all__`

## 5. Factory

- [x] 5.1 Create `adapters/factory.py` with `create_renderer(fmt: OutputFormat, console: Console | None = None) -> Renderer`
- [x] 5.2 Dispatch: `OutputFormat.JSON` → `JsonRenderer()`, `OutputFormat.PLAIN` → `PlainRenderer()`, `OutputFormat.RICH` → `RichRenderer(console or Console())`; raise `ValueError` for anything else

## 6. Tests

- [x] 6.1 Add `tests/test_enums.py`: enum values, `__str__`, lowercase construction
- [x] 6.2 Add `tests/test_views.py`: frozen immutability (FrozenInstanceError), `ErrorView.kind` accepts arbitrary strings, `CustomView` carries all three forms
- [x] 6.3 Add `tests/test_renderers.py`: the views × 3 backends matrix — for each of the seven verb methods, assert the JSON/plain/rich output shape
- [x] 6.4 Add `tests/test_errors.py`: `error()` routes to stderr (not stdout) for all three backends
- [x] 6.5 Add `tests/test_progress.py`: `status`/`progress` are live in rich, silent no-ops in json/plain; `progress.advance()` advances a rich bar
- [x] 6.6 Add `tests/test_custom_view.py`: plain verbatim, json object serialization, rich callable invocation
- [x] 6.7 Add `tests/test_factory.py`: dispatch per format, console forwarding to RichRenderer, `ValueError` on unknown format
- [x] 6.8 Add `tests/test_structural.py`: `isinstance` conformance of all three adapters against the `Renderer` protocol
- [x] 6.9 Run `pytest` in `src/shared/cli-output/` — all tests pass
- [x] 6.10 Run `ruff check` and `ruff format --check` in `src/shared/cli-output/` — clean

## 7. Wire dependency into both CLIs

- [x] 7.1 Add `cli-output` to WEG `src/cli-tools/wallpaper-effects-generator/pyproject.toml` dependencies and add `cli-output = { path = "../../shared/cli-output", editable = true }` to its `[tool.uv.sources]`
- [x] 7.2 Add `cli-output` to CSG `src/cli-tools/color-scheme-generator/pyproject.toml` dependencies and add `cli-output = { path = "../../shared/cli-output", editable = true }` to its `[tool.uv.sources]`
- [x] 7.3 Run `uv sync` in both CLI projects to lock the new dependency
- [x] 7.4 Run the full WEG and CSG test suites — all pass (regression check; no CLI code consumes `cli-output` yet)
