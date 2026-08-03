## MODIFIED Requirements

### Requirement: Templates catalog metadata in info output

The bundled template count referenced by this spec SHALL be 9 (was 8) and `templates.formats` SHALL include `"conf"` in addition to the existing `"json"`, `"sh"`, `"css"`, and other standard entries.

#### Scenario: derive from bundled templates

- **WHEN** derive is called on the bundled `defaults/templates/` directory
- **THEN** all 9 standard format entries are present
- **AND** each entry has a valid `ColorFormat`
