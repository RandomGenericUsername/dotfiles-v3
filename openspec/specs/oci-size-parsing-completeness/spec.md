# Size Parsing Completeness

## Purpose

Extends parse_size_to_bytes to accept unitless integers (interpreted as bytes) and trailing whitespace.

## Requirements

### Requirement: parse_size_to_bytes accepts unitless integers and trailing whitespace

`domain/size_parsing.parse_size_to_bytes()` must accept size strings without a unit suffix (interpreted as bytes) and strings with trailing whitespace.

Regex relaxed to: `r"^\s*(\d*\.?\d+)\s*([a-zA-Z]+)?\s*$"` (unit optional, leading/trailing whitespace allowed). When unit is missing, multiplier defaults to 1 (bytes). Examples: `"1024"` → `1024`, `" 512 "` → `512`, `"1.5GB "` → `1610612736`.

#### Scenario: Unitless integer parses as bytes
- **WHEN** `parse_size_to_bytes("1024")` is called
- **THEN** returns `1024` (int)

#### Scenario: Trailing whitespace ignored
- **WHEN** `parse_size_to_bytes(" 1.5GB ")` is called
- **THEN** returns `1610612736` (same as `"1.5GB"`)

#### Scenario: Leading whitespace ignored
- **WHEN** `parse_size_to_bytes("\t1.5GB")` is called
- **THEN** returns `1610612736`

#### Scenario: Case-insensitive units preserved
- **WHEN** `parse_size_to_bytes("1.5gb")` is called
- **THEN** returns `1610612736`

### Requirement: parse_size_to_bytes rejects embedded garbage

Full-match regex still rejects strings with extra non-whitespace content after the unit (e.g., `"junk 1.5GB trailing"` raises `ValueError`).

#### Scenario: Embedded garbage rejected
- **WHEN** `parse_size_to_bytes("junk 1.5GB trailing")` is called
- **THEN** raises `ValueError`