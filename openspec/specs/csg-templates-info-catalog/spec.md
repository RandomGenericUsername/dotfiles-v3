# csg-templates-info-catalog Specification

## Purpose
TBD - created by archiving change csg-templates-info-catalog. Update Purpose after archive.
## Requirements
### Requirement: Templates catalog metadata in info output

`csg info` SHALL emit a `templates` block in JSON output, a `Templates:` section in plain output, and a Templates table in rich output — analogous to WEG's `catalog` block.

The templates catalog SHALL be derived by scanning the resolved templates directory and parsing the naming convention `colors.<fmt>.j2`, mapping `<fmt>` to the `ColorFormat` enum.

#### Scenario: info shows templates block with count and formats

- **WHEN** `csg info` is run
- **THEN** the JSON output contains a `templates` key
- **THEN** `templates.templates_count` is a positive integer (e.g. 8 for bundled templates)
- **THEN** `templates.formats` is a list of strings (e.g. {"json", "sh", "css"})
- **THEN** `templates.source_dir` is a string path to the resolved templates directory

#### Scenario: plain output shows Templates section

- **WHEN** `csg info --output-format plain` is run
- **THEN** output contains a line starting with `count:` under a `Templates:` heading
- **THEN** output contains `formats:` followed by listed formats

#### Scenario: rich output shows Templates table

- **WHEN** `csg info --output-format rich` is run
- **THEN** a table titled "Templates" is rendered with Format and File columns

#### Scenario: templates catalog is derived from explicit --templates-dir

- **WHEN** `csg info --templates-dir /custom/path` is run
- **THEN** the templates catalog is derived from `/custom/path` (not the auto-resolved path)
- **THEN** `templates.source_dir` equals `/custom/path`

### Requirement: OutputPort protocol declares config_info

`OutputPort` SHALL declare `config_info(self, settings, backends, sources, templates)` as part of its protocol contract. The previously-dead `catalog` parameter (was passed but never consumed by any adapter) SHALL be removed.

#### Scenario: OutputPort implementation requires config_info

- **WHEN** a class implements `process_result`, `error`, `palette_display`, and `message`
- **BUT** does NOT implement `config_info`
- **THEN** `isinstance(instance, OutputPort)` returns `False`

#### Scenario: existing adapters satisfy OutputPort protocol

- **WHEN** `JsonOutput`, `PlainOutput`, and `RichOutput` are checked against `OutputPort`
- **THEN** all three satisfy the protocol

### Requirement: TemplateCatalogLoaderPort

A new port `TemplateCatalogLoaderPort` SHALL be added with two methods:
- `load(explicit_dir: Path | None = None) -> TemplateCatalog` — loads and derives a template catalog
- `get_resolved_path() -> Path | None` — returns the source directory path after loading

The single adapter `DirectoryTemplateCatalogLoader` SHALL wrap the existing `TemplateDirResolver`, call `TemplateCatalogService.derive()` on the resolved directory, and cache by key (explicit path or auto-resolved).

#### Scenario: loader with explicit dir

- **WHEN** `loader.load(explicit_dir=Path("/x"))` is called
- **THEN** the resolver is bypassed and the catalog is derived from `/x`
- **THEN** `loader.get_resolved_path()` returns `/x`

#### Scenario: loader without explicit dir

- **WHEN** `loader.load()` is called
- **THEN** the resolver's auto-resolution chain (env/CWD/XDG/default) is used to locate the directory
- **THEN** the catalog is derived from that directory

#### Scenario: loader caches by key

- **WHEN** `loader.load(explicit_dir=tmp)` is called twice with the same dir
- **THEN** the second call returns the same cached `TemplateCatalog` instance (no re-scan)
- **WHEN** a different key is used
- **THEN** a new scan occurs and a different `TemplateCatalog` is returned

### Requirement: TemplateCatalogService derivation with strict validation

`TemplateCatalogService.derive(dir_path)` SHALL:
- Scan `*.j2` files in `dir_path`
- Parse the naming pattern `colors.<fmt>.j2` — strip `colors.` prefix and `.j2` suffix to isolate `<fmt>`
- Map `<fmt>` to `ColorFormat` enum
- Ignore non-`.j2` files (e.g. `README.md`, `.gitkeep`)
- Raise `TemplatesValidationError` if any `.j2` file's `<fmt>` does not match a known `ColorFormat`
- Return `TemplateCatalog(templates=tuple, source_dir=dir_path)`

#### Scenario: derive from bundled templates

- **WHEN** derive is called on the bundled `defaults/templates/` directory
- **THEN** all 8 standard format entries are present
- **THEN** each entry has a valid `ColorFormat`

#### Scenario: derive rejects unknown formats

- **WHEN** a directory contains `colors.unknown.j2`
- **THEN** derive raises `TemplatesValidationError`

#### Scenario: derive ignores non-J2 files

- **WHEN** a directory contains `colors.json.j2` and `README.md`
- **THEN** only the `.j2` file appears in the catalog
- **THEN** `README.md` is silently ignored

#### Scenario: derive handles empty directory

- **WHEN** a directory contains no `.j2` files
- **THEN** derive returns an empty `TemplateCatalog` (zero templates, valid source_dir)

#### Scenario: derive raises on nonexistent directory

- **WHEN** derive is called with a nonexistent path
- **THEN** derive raises `ConfigResolutionError`

