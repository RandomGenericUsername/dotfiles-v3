# CSG Backend Catalog Min Version

## Why

`YamlBackendCatalogLoader._schema_to_domain` hardcoded `min_version="0.0.0"` on every `BackendDefinition`, and `BackendDefinitionSchema` had no `min_version` field so a YAML-declared `min_version` was silently dropped by pydantic. This capability pins the corrected contract: declared values round-trip.

## ADDED Requirements

### Requirement: BackendDefinitionSchema carries min_version
`BackendDefinitionSchema` SHALL declare a `min_version` field defaulting to `"0.0.0"`. YAML catalogs that omit the key continue to resolve to `"0.0.0"`; catalogs that declare it SHALL round-trip through the loader into `BackendDefinition.min_version`.

#### Scenario: Declared min_version round-trips
- **WHEN** a `backends.yaml` declares `custom: { min_version: "1.2.3", parameters: [] }` and is loaded via `YamlBackendCatalogLoader.load(explicit_path=...)`
- **THEN** `result[Backend.CUSTOM].min_version == "1.2.3"`

#### Scenario: Absent min_version keeps the default
- **WHEN** a `backends.yaml` omits `min_version` and is loaded
- **THEN** `result[Backend.CUSTOM].min_version == "0.0.0"`