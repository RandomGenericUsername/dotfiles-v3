## ADDED Requirements

### Requirement: The editor exposes two tabs: Mappings and Templates
The editor window SHALL present a tab bar with two tabs: *Mappings* (the existing mapping editor, unchanged) and *Templates* (the placeholder-assignment surface). Switching tabs SHALL preserve each tab's state, including pending edits on both sides.

#### Scenario: tabs preserve state
- **GIVEN** pending mapping edits on the Mappings tab and a pending template edit on the Templates tab
- **WHEN** the user switches to Mappings and back to Templates
- **THEN** both pending edits are still present and shown in their respective views

### Requirement: Templates tab selects one template file from a badged tree
The Templates tab SHALL list template files under the template root, grouped by first path segment, each badged `templated` (at least one shape uses a `{{…}}` placeholder) or `bare` (no shape uses a placeholder). Selecting an entry SHALL preview that file's shapes large; the center pane SHALL show the file path and a mode badge (`templated` / `bare — assign placeholders`).

#### Scenario: bare template badge
- **GIVEN** a template file whose shapes paint only with literal hex colors
- **WHEN** the Templates tab loads its tree
- **THEN** that file is badged `bare`
- **AND** selecting it shows the mode badge `bare — assign placeholders`

### Requirement: Clicking a shape offers assignment of an existing or new placeholder
Selecting a shape SHALL show its paint state (current `{{NAME}}` or literal hex, resolved color, usage count) and an assignment panel listing every known placeholder — with resolved token, hex, and usage count — plus a new-placeholder field. *Assign* SHALL stage a pending edit rewriting that shape's paint attribute to `{{NAME}}`; the preview SHALL re-render with the new placeholder's resolved color.

#### Scenario: assign an existing placeholder
- **GIVEN** the selected shape paints `{{COLOR_FOREGROUND}}`
- **WHEN** the user picks `{{COLOR_ACCENT}}` from the list and assigns
- **THEN** the pending diff shows the template line `{{COLOR_FOREGROUND}}` → `{{COLOR_ACCENT}}` for that shape
- **AND** the preview paints the shape with `COLOR_ACCENT`'s resolved color

#### Scenario: create and assign a new placeholder
- **GIVEN** the user types `COLOR_COUNTOUR` (valid name) and picks token `color5`
- **WHEN** the user assigns
- **THEN** the shape's pending edit targets `{{COLOR_COUNTOUR}}`
- **AND** a pending `defaults.yaml` entry `COLOR_COUNTOUR: color5` appears
- **AND** the preview paints the shape with `color5`'s hex immediately

#### Scenario: invalid new placeholder name
- **GIVEN** the user types `color contour` in the new-placeholder field
- **WHEN** the field is evaluated
- **THEN** an inline validation error appears and assignment is disabled

### Requirement: Bare templates show partial-onboarding progress
For a bare template, the tab SHALL show an `assigned N/M` tracker (N = shapes with a placeholder). Each shape MAY be assigned independently; unassigned shapes SHALL keep rendering their literal colors, and saving is allowed with any number of shapes unassigned.

#### Scenario: partial onboarding
- **GIVEN** a bare template with 3 shapes, 2 assigned
- **WHEN** the user saves
- **THEN** the 2 assigned shapes carry `{{…}}` placeholders in the written file
- **AND** the third shape keeps its literal hex color
- **AND** the written file renders correctly as-is

### Requirement: Template edits join the shared pending buffer and diff pane
Template edits and new-placeholder vocabulary entries SHALL accumulate in the same pending model as mapping edits, shown in the same diff pane — template files as per-shape old→new lines under the template path, new placeholders as `defaults.yaml` entries. *Revert* SHALL discard both; *Save* SHALL apply template writes first, then vocabulary defaults, then manifest registration for brand-new files, then any mapping writes. A failed write SHALL keep all pending edits and surface the error.

#### Scenario: save writes template and vocabulary together
- **GIVEN** one pending template edit (new placeholder `COLOR_COUNTOUR`) and its pending vocabulary default
- **WHEN** the user saves
- **THEN** the template file's shape carries `{{COLOR_COUNTOUR}}` and nothing else in the file changed
- **AND** `defaults.yaml` gains `COLOR_COUNTOUR: <token>` preserving all comments and formatting
- **AND** the editor reloads both files and clears the pending buffer

#### Scenario: stale template file blocks save
- **GIVEN** a template file changed on disk after the editor loaded it
- **WHEN** the user attempts to save
- **THEN** the save is blocked with a stale state offering a Reload that retains pending edits

### Requirement: Templates tab runs headless when invoked without a display
The Templates tab's underlying operations (analyze, staged writes, save pipeline) SHALL be exercisable headlessly through the CLI verbs they shell out to, so the behavior is testable without a display.

#### Scenario: headless parity
- **WHEN** the same template edit is staged via the CLI and via the GUI save pipeline
- **THEN** the resulting file bytes are identical
