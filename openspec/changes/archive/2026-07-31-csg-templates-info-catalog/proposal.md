## Why

`csg info` shows settings, backends, and source paths — but gives the user no information about available templates (`.j2` files). Users cannot discover which output formats exist or where templates are located without checking the resolved path and inspecting the directory manually.

WEG's `weg info` solves the same problem for effects by emitting a `catalog` block with `effects_count`, `composites_count`, `presets_count`. CSG needs the parallel for templates.

## What Changes

Teach `csg info` to scan the resolved templates directory, derive a `TemplateCatalog` from the `colors.<fmt>.j2` naming convention, and emit a `templates` block in the info output:

```json
{
  "templates": {
    "templates_count": 8,
    "formats": ["json", "sh", "css", "gtk.css", "yaml", "sequences", "rasi", "scss"],
    "source_dir": "/path/to/templates"
  }
}
```

### New domain abstractions
- `ColorSchemeTemplate` — dataclass representing a single template file.
- `TemplateCatalog` — dataclass wrapping a tuple of templates + source dir.
- `TemplateCatalogService` — stateless service that scans a directory and derives the catalog by parsing `colors.<fmt>.j2` naming.
- `TemplatesValidationError` — raised when a `.j2` file's format key is not a known `ColorFormat` enum value.

### New port
- `TemplateCatalogLoaderPort` — protocol with `load(explicit_dir=...)` and `get_resolved_path()`, mirroring WEG's `EffectLoaderPort`.

### New adapter
- `DirectoryTemplateCatalogLoader` — wraps the existing `TemplateDirResolver`, calls `TemplateCatalogService.derive()` on the resolved path, caches by key.

### Protocol contract
- `OutputPort` gains `config_info(self, settings, backends, sources, templates)` — currently implicit in all 3 output adapters but undeclared in the protocol, now declared.

### Output format change
- **JSON**: new `templates` block with `templates_count`, `formats` (list), `source_dir`.
- **Plain**: prints `Templates:` section with count and comma-separated formats.
- **Rich**: renders a `Templates` table with Format and File columns.

### CLI change
- `info_cmd.py` stops importing the concrete `TemplateDirResolver` and instead depends on `TemplateCatalogLoaderPort` via deps.
- `factory.py` gains `create_template_catalog_loader()`; `CliDependencies` gains `template_catalog_loader` field; `build_deps()` wires it.

## Capabilities

### New Capabilities
- `csg info` now shows templates catalog with count + formats

### Modified Capabilities
- `cli-runtime-engine-scope`: The `info` command now provides structured template metadata (not just a path string). The `OutputPort` protocol contract now explicitly requires `config_info`.

## Impact

- **CSG domain layer**: 2 new dataclasses (`ColorSchemeTemplate`, `TemplateCatalog`), 1 new service (`TemplateCatalogService`), 1 new exception (`TemplatesValidationError`).
- **CSG ports layer**: 1 new port (`TemplateCatalogLoaderPort`). `OutputPort` gains the declared `config_info` method.
- **CSG adapters**: 1 new adapter (`DirectoryTemplateCatalogLoader`). All 3 output adapters updated to render `templates` block.
- **CSG factory**: `create_template_catalog_loader()` added; `CliDependencies` gets `template_catalog_loader` field.
- **CSG CLI**: `info_cmd.py` rewired to use catalog loader instead of concrete resolver.
- **Tests**: 13+ new test cases (domain service, adapter, port contract, extension of existing info command tests).
- **WEG**: no changes.
