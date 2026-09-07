## ADDED Requirements

### Requirement: Preview reproduces `itr render` substitution
The preview SHALL resolve colors using the same rules as `PlaceholderSubstitutionService`: each `{{NAME}}` is looked up in the merged mapping table, a value starting with `#` is used literally, and any other value is resolved as a key of the loaded color scheme. Merged mappings SHALL follow the precedence vocabulary defaults → group `color_mappings` → variant `color_mappings`.

#### Scenario: variant override wins over group mapping
- **GIVEN** a group maps `COLOR_ACCENT: color12` and a variant overrides `COLOR_ACCENT: color3`
- **WHEN** that variant is previewed
- **THEN** its accent shapes render with the hex of `color3`

#### Scenario: literal hex values pass through
- **GIVEN** a mapping value beginning with `#`
- **WHEN** the shape using that placeholder is previewed
- **THEN** the literal value is used without a color-scheme lookup

### Requirement: Unresolvable placeholders render as unresolved, not as an error
A placeholder with no entry in the merged mapping table, or whose token is absent from `colors.yaml`, SHALL render with a distinct "unresolved" fill and SHALL be reported in the panel as unresolved with the reason (missing mapping or missing token). The preview SHALL NOT crash or blank the icon.

#### Scenario: mapping points at a token absent from the palette
- **GIVEN** a placeholder maps to `accent` and `colors.yaml` has no `accent` key
- **WHEN** the icon is previewed
- **THEN** the affected shapes show the unresolved fill
- **AND** the panel reports the token as missing from `colors.yaml`

### Requirement: The whole group previews live
The preview SHALL render every variant of the selected group simultaneously, with the selected variant enlarged, and SHALL re-render all of them on every pending edit so that group-scoped changes are visible across variants before saving.

#### Scenario: a group-scoped pick updates every variant
- **WHEN** the user picks a new token for a placeholder in group scope
- **THEN** every previewed variant that uses that placeholder updates immediately

#### Scenario: a variant-scoped pick updates only that variant
- **WHEN** the user picks a new token in `This variant only` scope
- **THEN** only the selected variant's preview changes

### Requirement: Preview backdrop is switchable
The preview SHALL offer a backdrop toggle between a neutral surface and the status-bar background color, so icon contrast can be judged against its real destination.

#### Scenario: toggling the backdrop
- **WHEN** the user activates the bar-background toggle
- **THEN** the preview backdrop changes and the rendered icon colors are unchanged
