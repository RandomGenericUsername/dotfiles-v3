# csg-default-formats-empty-expansion Specification

## Purpose
`csg generate` with an empty `output.default_formats` setting (and no `-f/--format` flag) resolves the output format set to every format available in the loaded templates directory, instead of rendering zero files. The expansion is guarded when no template catalog loader is available, catalog load failures surface as typed errors, and the config-resolution fallback uses canonical `json`/`sh` defaults.

## Requirements

### Requirement: Empty default_formats expands to all loaded templates
When `csg generate` is invoked without any `-f/--format` flag and the resolved `output.default_formats` setting is empty, the CLI SHALL resolve the output format set to every format present in the loaded template catalog (one format per `colors.<fmt>.j2` template in the resolved templates directory). When `output.default_formats` is non-empty, those formats SHALL be used unchanged. When `-f/--format` flags are supplied, those flags SHALL be used unchanged.

#### Scenario: empty default_formats renders every template format
- **WHEN** a settings file sets `output.default_formats = []` and the templates directory contains templates for `json`, `sh`, `css`, and `rasi`
- **AND** `csg generate <image>` is invoked without `-f/--format`
- **THEN** the generated output includes `colors.json`, `colors.sh`, `colors.css`, and `colors.rasi`

#### Scenario: non-empty default_formats is respected unchanged
- **WHEN** a settings file sets `output.default_formats = ["json"]` and the templates directory contains more formats
- **AND** `csg generate <image>` is invoked without `-f/--format`
- **THEN** only `colors.json` is generated

#### Scenario: explicit format flags bypass expansion
- **WHEN** a settings file sets `output.default_formats = []` and a catalog with multiple formats is loaded
- **AND** `csg generate <image> -f css -f rasi` is invoked
- **THEN** only `colors.css` and `colors.rasi` are generated
- **AND** the template catalog loader is not consulted

### Requirement: Expansion respects the --templates-dir override
When `--templates-dir <dir>` is supplied with an empty `output.default_formats` and no `-f/--format`, the format expansion SHALL derive the format set from the catalog of the given directory, not from the resolved default templates directory.

#### Scenario: expansion uses the explicit templates directory
- **WHEN** `csg generate <image> --templates-dir /custom/templates` is invoked with empty `output.default_formats`
- **THEN** the template catalog loader is invoked with the explicit templates directory
- **AND** the resolved formats match the templates in that directory

### Requirement: Expansion is guarded when no catalog loader is available
When no template catalog loader is available (`deps.template_catalog_loader` is `None`), an empty `output.default_formats` SHALL NOT trigger catalog expansion; the resolved format set SHALL remain empty, preserving prior behavior.

#### Scenario: empty default_formats with no loader stays empty
- **WHEN** `csg generate <image>` is invoked with empty `output.default_formats` and no template catalog loader available
- **THEN** the resolved format set is empty
- **AND** the command exits successfully without generating output files

### Requirement: Catalog load failures surface as typed errors
When format expansion triggers a template catalog load and the load raises a `ColorSchemeError` (e.g. `TemplatesValidationError` for an unknown template format), `csg generate` SHALL report the typed error through the output adapter and exit with a non-zero code, instead of silently rendering nothing.

#### Scenario: invalid template format in the templates directory
- **WHEN** `csg generate <image>` is invoked with empty `output.default_formats` and the templates directory contains a template whose format is not a valid `ColorFormat`
- **THEN** the command exits non-zero
- **AND** the error payload reports `TemplatesValidationError`

### Requirement: Config-resolution fallback uses canonical default formats
When config resolution fails and the CLI falls back to `default_app_settings()`, the fallback settings SHALL use `default_formats = ["json", "sh"]` rather than an empty list, so the fallback does not trigger full-catalog expansion.

#### Scenario: failed config resolution falls back to json and sh
- **WHEN** `csg generate <image>` is invoked and settings resolution fails
- **THEN** the command uses the fallback defaults
- **AND** the fallback default formats are `["json", "sh"]`
