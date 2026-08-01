# CSG Settings Schema Validation

## Why

`OutputSettingsSchema.default_formats` was declared `list[str]` with no validator, so arbitrary strings (`"weird"`) were accepted at the schema boundary and only failed late in `cli/main.py` when `ColorFormat(f)` was called. This capability pins the corrected contract: the schema rejects invalid color-format strings at validation time.

## ADDED Requirements

### Requirement: default_formats rejects strings outside the ColorFormat enum
`OutputSettingsSchema.default_formats` SHALL reject any string that is not a `ColorFormat` enum value with a `ValidationError`. The field SHALL remain `list[str]` (validation without coercion); enum coercion stays the responsibility of the downstream serializer/CLI layer.

#### Scenario: Nested schema rejects invalid format
- **WHEN** `OutputSettingsSchema(directory="/out", default_formats=["weird"])` is validated
- **THEN** a `ValidationError` is raised

#### Scenario: Core settings rejects invalid format
- **WHEN** `CoreSettingsSchema` is validated with `output.default_formats = ["not-a-format"]`
- **THEN** a `ValidationError` is raised

#### Scenario: Valid formats still accepted
- **WHEN** `OutputSettingsSchema(directory="/out", default_formats=["json", "sh"])` is validated
- **THEN** the value is accepted unchanged as `["json", "sh"]`