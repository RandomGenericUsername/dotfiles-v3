## ADDED Requirements

### Requirement: Three-region layout with a persistent diff pane
The editor window SHALL be arranged in three regions: a left column carrying the inputs panel and the group tree, a center column carrying the preview canvas with the pending-diff pane beneath it, and a right column carrying selection details, scope switch, token picker, and the Save/Revert footer. The diff pane SHALL always be visible above the footer, showing the pending edits or an explicit empty state.

#### Scenario: all three regions are present
- **WHEN** the editor is open
- **THEN** inputs and group tree are in the left region
- **AND** the preview canvas and diff pane are in the center region
- **AND** selection, scope, picker, and footer actions are in the right region

#### Scenario: empty diff states itself
- **WHEN** there are no pending edits
- **THEN** the diff pane shows an explicit no-changes state rather than a blank area

### Requirement: Uniform grid with a marked active variant
All variant cards SHALL render at the same size in a wrapping left-aligned grid. The active variant SHALL be distinguished by the accent border alone, with no size difference.

#### Scenario: no enlarged variant
- **WHEN** a group with several variants is loaded
- **THEN** every card renders at the same size and exactly one carries the active border

#### Scenario: only the active card accepts shape clicks
- **WHEN** the user clicks a shape in a non-active card
- **THEN** no shape selection occurs (the click promotes that variant instead)

### Requirement: The canvas bar names the active template
The canvas bar SHALL display the active variant's template path alongside the view toggles, updating on every variant switch.

#### Scenario: breadcrumb tracks the active variant
- **WHEN** the user switches from `battery-50-charging` to `battery-50`
- **THEN** the canvas bar shows the `battery-50` template path

### Requirement: Every state has a distinct visual affordance
Each interactive state SHALL be visibly distinct: the selected shape is outlined in the main preview, the currently mapped token is ringed in the picker, tokens absent from `colors.yaml` are visibly disabled with their reason, unresolvable shapes carry the unresolved fill, and variants with variant-scoped overrides carry the override marker. The picker and scope switch are visibly dimmed whenever no shape is selected.

#### Scenario: current mapping is ringed
- **WHEN** a shape mapped to `color12` is selected
- **THEN** the `color12` swatch carries the current-marker and no other swatch does

#### Scenario: everything dimmed without a selection
- **WHEN** no shape is selected
- **THEN** the token grid, named-token rows, and scope switch are dimmed and non-interactive

### Requirement: The picker lists indexed tokens before named tokens
The token picker SHALL render the `color0`–`color15` swatch grid first and the named-token rows (present and missing) beneath it, preserving that order regardless of which tokens the group currently maps to.

#### Scenario: picker order is stable
- **WHEN** a shape is selected in any group
- **THEN** the indexed swatch grid precedes the named-token rows

### Requirement: Headings name the placeholder or invite a selection
The picker heading SHALL read `Set {{PLACEHOLDER}} to which palette token?` naming the selected placeholder, or `Select a shape to change its color` when nothing is selected. The scope control SHALL label its three options `Whole group`, `This variant only`, and `All icons`.

#### Scenario: heading tracks the selection
- **WHEN** a shape using `COLOR_ACCENT` is selected and then deselected
- **THEN** the heading switches from `Set {{COLOR_ACCENT}} to which palette token?` to `Select a shape to change its color`

### Requirement: Footer orders Revert before Save
The footer SHALL present `Revert` before the primary `Save mappings` action, and both SHALL remain visible without scrolling the picker column.

#### Scenario: footer actions are always reachable
- **WHEN** the picker column overflows
- **THEN** `Revert` and `Save mappings` stay pinned and clickable

### Requirement: The preview starts on the neutral backdrop
The preview SHALL default to the neutral backdrop on launch and on every group switch; the bar-background toggle switches the backdrop without altering any rendered icon color.

#### Scenario: neutral by default
- **WHEN** the editor launches or loads a new group
- **THEN** the preview backdrop is neutral until the user toggles it
