# csg-settings-schema-validation Specification

## Purpose
`OutputSettingsSchema.default_formats` rejects any string that is not a `ColorFormat` enum value at validation time, while preserving the `list[str]` field type (validation without coercion).

## Requirements

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