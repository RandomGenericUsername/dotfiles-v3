## 0. Precondition Gates

- [x] 0.1 Verify working tree is clean: `git status --short` shows only expected changes
- [x] 0.2 Establish CSG test baseline: `uv run pytest --tb=short -q 2>&1 | tee /tmp/csg-baseline.txt`. Save output.
- [x] 0.3 Confirm no pre-existing failures before delta.

## 1. Domain layer — models, service, exception

- [x] 1.1 Add `ColorSchemeTemplate` dataclass to `domain/models.py` (frozen, fields: `name: str`, `format: ColorFormat`)
- [x] 1.2 Add `TemplateCatalog` dataclass to `domain/models.py` (frozen, fields: `templates: tuple[ColorSchemeTemplate, ...]`, `source_dir: Path | None`)
- [x] 1.3 Add `TemplatesValidationError` to `domain/exceptions.py` (subclass `ColorSchemeError`)
- [x] 1.4 Add `TemplateCatalogService` to `domain/services.py` with `derive(dir_path: Path) -> TemplateCatalog` method: scans `*.j2` files, parses `colors.<fmt>.j2` naming, validates against `ColorFormat` enum, raises on unknown
- [x] 1.5 Add tests: `TestTemplateCatalogService` in `tests/unit/domain/test_services.py`

## 2. Ports layer — new port + OutputPort contract

- [x] 2.1 Create `ports/template_catalog_loader.py` — `TemplateCatalogLoaderPort` protocol with `load(explicit_dir=...)` and `get_resolved_path()`
- [x] 2.2 Declare `config_info(self, settings, backends, sources, templates)` on `OutputPort` in `ports/output.py` (add import under `TYPE_CHECKING`)
- [x] 2.3 Register `TemplateCatalogLoaderPort` in `ports/__init__.py` (import + `__all__`)
- [x] 2.4 Add port contract tests in `tests/unit/ports/test_interfaces.py`: valid implementation, invalid implementation, missing method

## 3. Adapter — DirectoryTemplateCatalogLoader

- [x] 3.1 Create `adapters/template_catalog_loader.py` — `DirectoryTemplateCatalogLoader(g resolver)` with `load()` + `get_resolved_path()`, caching by key
- [x] 3.2 Add adapter tests: explicit dir, resolver fallback, cache behavior, null resolved path pre-load

## 4. Output adapters — render templates block

- [x] 4.1 Update `adapters/output/json_output.py` `config_info`: drop unused `catalog` arg, add `templates` param, emit `templates`: `{templates_count, formats[], source_dir}` block
- [x] 4.2 Update `adapters/output/plain_output.py` `config_info`: same signature change, print `Templates:` section with count + formats
- [x] 4.3 Update `adapters/output/rich_output.py` `config_info`: same signature change, render Templates table with Format and File columns

## 5. Factory + CLI wiring

- [x] 5.1 Add `create_template_catalog_loader()` factory function in `factory.py`
- [x] 5.2 Add `template_catalog_loader: TemplateCatalogLoaderPort | None` field to `CliDependencies` dataclass
- [x] 5.3 Import + wire `create_template_catalog_loader()` in `cli/main.py` `build_deps()`
- [x] 5.4 Rewire `cli/info_cmd.py`: import from deps `template_catalog_loader` (not `template_dir_resolver`), call `loader.load(explicit_dir=templates_dir)`, pass `templates` to `adapter.config_info()`

## 6. Test maintenance

- [x] 6.1 Update `mock_deps` fixture in `tests/unit/cli/test_info_command.py`: add `mock_template_catalog_loader` fixture, wire into CliDependencies
- [x] 6.2 Update `test_info_outputs_json` to assert `"templates"` in payload
- [x] 6.3 Update `test_info_shows_templates_directory` to assert `templates.templates_count == 2` and `formats` list
- [x] 6.4 Update `MockOutput` in port tests to include `config_info` method

## 7. Verify

- [x] 7.1 Run full CSG test suite: `uv run pytest --tb=short -q`. Compare with baseline. NO new failures.
- [x] 7.2 Run ruff: `uv run ruff check src tests`. Only pre-existing errors remain (E501, B008, E741, etc.).
- [x] 7.3 Run mypy: `uv run mypy src tests`. No new type errors.
- [x] 7.4 `csg info --output-format json` contains `templates` block with correct `templates_count` and `formats`
- [x] 7.5 `csg info --output-format plain` shows `Templates:` section
- [x] 7.6 `csg info --output-format rich` shows Templates table
- [x] 7.7 `csg info --templates-dir /custom/path` uses the explicit dir for catalog derivation
- [x] 7.8 Verify WEG tests are unaffected: `cd ../wallpaper-effects-generator && uv run pytest -q`
