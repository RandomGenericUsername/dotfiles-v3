## ADDED Requirements

### Requirement: Three inputs, only the mapping files writable
The editor SHALL take exactly three inputs: an SVG template root, an icons manifest (`icons.yaml`, with `defaults.yaml` resolved alongside it), and a generated color scheme (`colors.yaml`). The template root and the color scheme SHALL be treated as read-only for the lifetime of the session; `icons.yaml` and `defaults.yaml` SHALL be the only files the tool writes. Each input SHALL be displayed with its resolved path and its read-only/writable status.

#### Scenario: inputs are labeled by writability
- **WHEN** the editor is open
- **THEN** the template root and color scheme are labeled read-only
- **AND** the mapping files are labeled as edited by the tool

#### Scenario: templates and generated icons are never written
- **WHEN** any sequence of shape selections and token picks is saved
- **THEN** no file under the SVG template root is modified
- **AND** no file under `generated/` is modified
- **AND** no render is triggered

### Requirement: Selecting a shape reveals its placeholder and current mapping
Clicking a shape in the preview SHALL select it and the panel SHALL display: the shape identifier, the placeholder the shape uses in the form `{{NAME}}`, the palette token that placeholder currently resolves to together with its hex value, and a usage count of the form "N shapes across M variants" for that placeholder within the group.

#### Scenario: selecting the accent shape of a battery variant
- **WHEN** the user clicks the lightning-bolt shape of `battery-50-charging`
- **THEN** the panel shows placeholder `{{COLOR_ACCENT}}`
- **AND** shows it maps to `color12` with that token's hex
- **AND** shows how many shapes across how many variants use `COLOR_ACCENT`

#### Scenario: shape list is an equivalent selection path
- **WHEN** the user selects a shape from the panel's shape list instead of clicking the preview
- **THEN** the same selection state is produced

### Requirement: The token picker targets the selected placeholder and is inert without a selection
The token picker SHALL be titled `Set {{PLACEHOLDER}} to which palette token?` naming the currently selected placeholder. When no shape is selected, the picker and the scope switch SHALL be visibly disabled and non-interactive, and the title SHALL read `Select a shape to change its color`.

#### Scenario: no selection disables the picker
- **WHEN** no shape is selected
- **THEN** the token grid and scope switch are dimmed and do not respond to clicks
- **AND** the heading reads `Select a shape to change its color`

#### Scenario: picker names the selected placeholder
- **WHEN** a shape using `COLOR_ACCENT` is selected
- **THEN** the heading reads `Set {{COLOR_ACCENT}} to which palette token?`

### Requirement: The picker offers every palette token, disabling absent ones
The picker SHALL list every token present in the loaded `colors.yaml` — `color0` through `color15` plus every top-level scalar token such as `foreground`, `background`, and `cursor` — as selectable swatches showing token name and hex. Any token referenced by a resolved mapping but absent from `colors.yaml` SHALL be listed disabled and annotated `not in colors.yaml`. Absent tokens SHALL NOT be hidden and SHALL NOT be selectable.

#### Scenario: all sixteen indexed colors are selectable
- **WHEN** a shape is selected
- **THEN** `color0` … `color15` are all selectable regardless of which tokens the group currently maps to

#### Scenario: a mapped-but-missing token is disabled
- **GIVEN** `defaults.yaml` maps a placeholder to `surface` and `colors.yaml` has no `surface` key
- **WHEN** the picker is shown
- **THEN** `surface` appears disabled and annotated `not in colors.yaml`

### Requirement: Edit scope is explicit and states its blast radius
The editor SHALL offer three scopes — `This variant only`, `Whole group` (default), and `All icons` — and SHALL display, before any pick, which file and mapping key the pick will write and how many variants or groups it affects.

#### Scenario: group scope states the affected variants
- **WHEN** scope is `Whole group` for a group with four variants
- **THEN** the panel states the pick changes `<group>.color_mappings.<PLACEHOLDER>` and affects all 4 variants

#### Scenario: variant scope states the override
- **WHEN** scope is `This variant only`
- **THEN** the panel states the pick adds a `variants[].color_mappings` override for the selected variant only

#### Scenario: all-icons scope targets the vocabulary
- **WHEN** scope is `All icons`
- **THEN** the panel states the pick changes `defaults.<PLACEHOLDER>` in `defaults.yaml`
- **AND** states how many groups it affects

### Requirement: Vocabulary edits disclose the groups that shadow them
Because vocabulary defaults are the lowest-precedence mappings, in `All icons` scope the editor SHALL name every group whose own `color_mappings` overrides the selected placeholder, and SHALL warn explicitly when the currently previewed group is one of them, before the pick is made. The editor SHALL NOT remove or alter those overrides.

#### Scenario: previewed group shadows the vocabulary edit
- **GIVEN** `battery` overrides `COLOR_ACCENT` and `battery` is previewed
- **WHEN** scope is set to `All icons` with a `COLOR_ACCENT` shape selected
- **THEN** the panel warns that the change will not affect the previewed group
- **AND** lists `battery` among the shadowing groups

#### Scenario: shadowing overrides are left intact
- **WHEN** a vocabulary edit is saved while some groups override the placeholder
- **THEN** those groups' `color_mappings` entries are unchanged

### Requirement: Pending edits are deferred, diffed, and revertible
Picking a token SHALL NOT write to disk. Pending edits SHALL be accumulated and rendered as a YAML diff showing removed and added mapping lines under their owning key. `Save` SHALL apply all pending edits to the icons manifest and clear the pending set; `Revert` SHALL discard them and restore the preview to the on-disk state.

#### Scenario: a pick produces a diff and no write
- **WHEN** the user picks `color10` for `COLOR_ACCENT` in group scope
- **THEN** the diff shows `- COLOR_ACCENT: color12` and `+ COLOR_ACCENT: color10` under `battery.color_mappings`
- **AND** the icons manifest on disk is unchanged

#### Scenario: revert restores the loaded state
- **WHEN** the user reverts after several picks
- **THEN** the diff is empty and every preview matches the on-disk mappings
