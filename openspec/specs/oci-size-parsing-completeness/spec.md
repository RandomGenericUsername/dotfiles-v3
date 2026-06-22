## ADDED Requirements

### Requirement: parse_size_to_bytes accepts all common size units

`parse_size_to_bytes` must accept single-letter units (`K`, `M`, `G`, `T`), their lowercase equivalents, and `TIB` (tebibyte), in addition to the currently supported `KB`/`MB`/`GB`/`TB`/`KIB`/`MIB`/`GIB`. It must use `re.fullmatch` so that substring matches (e.g. `"junk 1.5GB trailing"`) are rejected rather than silently parsed.

#### Scenario: Single-letter megabyte
- **WHEN** `parse_size_to_bytes("500M")` is called
- **THEN** it returns `500 * 1024**2` (524288000), not `ValueError`

#### Scenario: Single-letter terabyte
- **WHEN** `parse_size_to_bytes("2T")` is called
- **THEN** it returns `2 * 1024**4`, not `ValueError`

#### Scenario: Tebibyte unit
- **WHEN** `parse_size_to_bytes("3TIB")` is called
- **THEN** it returns `3 * 1024**4`, not `ValueError`

#### Scenario: Substring match rejected
- **WHEN** `parse_size_to_bytes("junk 1.5GB trailing")` is called
- **THEN** it raises `ValueError` (the full string is not a valid size, not just a substring)

#### Scenario: Standard units still work
- **WHEN** `parse_size_to_bytes("1.5GB")` is called
- **THEN** it returns `1610612736` (unchanged from current behavior)
