# csg-backend-catalog-min-version Specification

## Purpose
`BackendDefinitionSchema` carries a `min_version` field that round-trips a YAML-declared value through the loader into `BackendDefinition.min_version`, defaulting to `"0.0.0"` when absent.

## Requirements

### Requirement: BackendDefinitionSchema carries min_version
`BackendDefinitionSchema` SHALL declare a `min_version` field defaulting to `"0.0.0"`. YAML catalogs that omit the key continue to resolve to `"0.0.0"`; catalogs that declare it SHALL round-trip through the loader into `BackendDefinition.min_version`.

#### Scenario: Declared min_version round-trips
- **WHEN** a `backends.yaml` declares `custom: { min_version: "1.2.3", parameters: [] }` and is loaded via `YamlBackendCatalogLoader.load(explicit_path=...)`
- **THEN** `result[Backend.CUSTOM].min_version == "1.2.3"`

#### Scenario: Absent min_version keeps the default
- **WHEN** a `backends.yaml` omits `min_version` and is loaded
- **THEN** `result[Backend.CUSTOM].min_version == "0.0.0"`