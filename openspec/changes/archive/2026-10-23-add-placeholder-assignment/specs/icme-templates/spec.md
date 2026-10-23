## ADDED Requirements

### Requirement: `itr template analyze` reports shapes, mode, and paint attributes
`itr template analyze <template_file> [--json]` SHALL emit, for each top-level shape in document order (numbered identically to the GUI extractor): the shape id, its tag, its paint attribute (`fill` or `stroke`, resolved through `<svg>`-root inheritance), and its current paint value (`{{NAME}}` placeholder or literal color). It SHALL classify the file as `templated` when any shape carries a placeholder and `bare` otherwise. The command SHALL NOT write any file.

#### Scenario: bare file classification
- **GIVEN** a template whose shapes paint only with literal hex colors
- **WHEN** `itr template analyze <file> --json` runs
- **THEN** mode is `bare` and every shape reports a literal paint value

#### Scenario: inherited stroke is resolved
- **GIVEN** an icon declaring `fill="none"` on the `<svg>` root and `stroke="{{COLOR_FOREGROUND}}"` on its paths
- **WHEN** `itr template analyze <file> --json` runs
- **THEN** each path reports paint attribute `stroke` with placeholder `COLOR_FOREGROUND`

### Requirement: `itr template set-placeholder` rewrites exactly one shape's paint attribute
`itr template set-placeholder <template_file> --shape <id> --name <NAME>` SHALL rewrite that shape's paint attribute value to `{{NAME}}` — replacing a previous placeholder or a literal color alike — leaving every other byte of the file (comments, attributes, formatting, line endings) unchanged. It SHALL fail without writing when the shape id is unknown, the name fails `[A-Z][A-Z0-9_]*`, or the file lacks the shape's paint attribute.

#### Scenario: re-place a placeholder on one shape
- **GIVEN** a templated file where shapes 1–3 all paint `{{COLOR_FOREGROUND}}`
- **WHEN** `itr template set-placeholder <file> --shape 2 --name COLOR_COUNTOUR` runs
- **THEN** shape 2 paints `{{COLOR_COUNTOUR}}`
- **AND** shapes 1 and 3 still paint `{{COLOR_FOREGROUND}}`
- **AND** all other file content is byte-identical

#### Scenario: onboard a bare shape
- **GIVEN** a bare file whose shape 1 paints `fill="#c2c2c5"`
- **WHEN** `itr template set-placeholder <file> --shape 1 --name COLOR_FOREGROUND` runs
- **THEN** shape 1 paints `fill="{{COLOR_FOREGROUND}}"`
- **AND** the remaining shapes keep their literal colors

#### Scenario: invalid name is rejected
- **GIVEN** any template file
- **WHEN** `itr template set-placeholder <file> --shape 1 --name "color contour"` runs
- **THEN** the command exits non-zero and the file is unchanged

### Requirement: New placeholders gain a vocabulary default through the existing mapping writer
When the GUI assigns a new placeholder name, the save pipeline SHALL create its vocabulary default via `itr mapping set-default defaults.yaml --placeholder <NAME> --token <TOKEN> --icons icons.yaml`, inheriting that verb's comment-preservation and shadow reporting. A template file SHALL NOT be left with an unmapped placeholder by the tool's own actions.

#### Scenario: new placeholder resolves after save
- **GIVEN** the user assigned the new placeholder `COLOR_COUNTOUR` with default `color5`
- **WHEN** the save pipeline completes
- **THEN** `defaults.yaml` contains `COLOR_COUNTOUR: color5`
- **AND** `itr render` produces the chosen color for that shape

### Requirement: Manifest registration applies only to brand-new template files
When saving edits to a template file that no `icons.yaml` entry references, the save pipeline SHALL add a manifest entry (group from the first path segment, variant from the second, `default` unless the file name differs) through the existing manifest-write verbs. Template files already referenced SHALL NOT be restructured.

#### Scenario: onboarding a downloaded icon
- **GIVEN** a bare SVG saved at `status-bar/battery/battery-unplugged/default/icon.svg` with no manifest entry
- **WHEN** the save pipeline completes
- **THEN** `icons.yaml` gains a battery variant referencing that template
- **AND** existing battery variants are untouched

### Requirement: Template writes are atomic and crash-safe
Each template file write SHALL be atomic (write to a temporary file, rename over the target) so an interrupted save never leaves a truncated template.

#### Scenario: interrupted save leaves the original intact
- **WHEN** the write is interrupted before the rename completes
- **THEN** the template file still contains its previous content
