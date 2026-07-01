## ADDED Requirements

### Requirement: RunConfig memory_limit accepts two-letter size units

`RunConfig._MEMORY_LIMIT_RE` SHALL accept the same size-unit forms that `parse_size_to_bytes` accepts, including two-letter units: `2GB`, `512MB`, `1.5gb`, `2g`, `2G`, `1024` (unitless). The regex is `^\d+(\.\d+)?[kmg]b?$` with `re.IGNORECASE` (allows `2g`, `2G`, `2gb`, `2GB`, `2`, etc.). This makes `RunConfig(memory_limit="2GB")` valid, matching `docker run --memory=2GB` (docker/go-units) and consistent with the v3 relaxation of `parse_size_to_bytes`.

#### Scenario: Two-letter gigabyte unit accepted
- **WHEN** `RunConfig(image="x", memory_limit="2GB")` is constructed
- **THEN** no exception is raised and `config.memory_limit == "2GB"`

#### Scenario: Two-letter megabyte unit accepted
- **WHEN** `RunConfig(image="x", memory_limit="512MB")` is constructed
- **THEN** no exception is raised

#### Scenario: Lowercase two-letter unit accepted
- **WHEN** `RunConfig(image="x", memory_limit="1.5gb")` is constructed
- **THEN** no exception is raised

#### Scenario: Single-letter and unitless still accepted (no regression)
- **WHEN** `RunConfig(image="x", memory_limit="2g")` and `RunConfig(image="x", memory_limit="1024")` are constructed
- **THEN** neither raises

#### Scenario: Invalid memory limit still rejected
- **WHEN** `RunConfig(image="x", memory_limit="abc")` is constructed
- **THEN** `ValueError` is raised
