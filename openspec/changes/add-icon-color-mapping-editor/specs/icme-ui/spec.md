## ADDED Requirements

### Requirement: Three inputs, only the mapping files writable
The editor SHALL take exactly three inputs: an SVG template root, an icons manifest (`icons.yaml`, with `defaults.yaml` resolved alongside it), and a generated color scheme (`colors.yaml`). The template root and the color scheme SHALL be treated as read-only for the lifetime of the session; `icons.yaml` and `defaults.yaml` SHALL be the only files the tool writes. Each input SHALL be displayed with its resolved path and its read-only/writable status.

#### Scenario: inputs are labeled by writability
- **WHEN** the editor is open
- **THEN** the template root and color scheme are labeled read-only
- **AND** the mapping files are labeled as edited by the tool

#### Scenario: inputs resolve to defaults on launch
- **WHEN** the editor launches without explicit input paths
- **THEN** the template root resolves to `dotfiles/assets/icon-templates/` in the checkout
- **AND** the manifest resolves to `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` with `defaults.yaml` resolved alongside it
- **AND** the color scheme resolves to `~/.local/share/dotfiles/generated/palettes/colors.yaml`

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

#### Scenario: usage count counts only variants using the placeholder
- **GIVEN** `COLOR_ACCENT` is used by 2 shapes in 2 of the group's 4 variants
- **WHEN** a shape using `COLOR_ACCENT` is selected
- **THEN** the panel shows `2 shapes across 2 variants`

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
The picker SHALL list every token with a `#rrggbb` color value present in the loaded `colors.yaml` — `color0` through `color15` plus every top-level scalar color token such as `foreground`, `background`, and `cursor` — as selectable swatches showing token name and hex. Non-color file metadata entries (e.g. `source_image`, `backend`) SHALL NOT be listed. Any token referenced by a resolved mapping but absent from `colors.yaml` SHALL be listed disabled and annotated `not in colors.yaml`. Absent tokens SHALL NOT be hidden and SHALL NOT be selectable. The picker SHALL offer palette tokens only: there is no free-form color entry, and the GUI SHALL NOT write literal `#rrggbb` mappings (literals already on disk keep passing through the preview per `icme-rendering`).

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

#### Scenario: scope hints use fixed copy
- **WHEN** scope is `Whole group` with placeholder `COLOR_ACCENT` in group `battery` spanning 4 variants
- **THEN** the hint reads `Changes battery.color_mappings.COLOR_ACCENT — affects all 4 variants`
- **WHEN** scope is `This variant only` with variant `battery-50-charging` selected
- **THEN** the hint reads `Adds a color_mappings override on variant "battery-50-charging" only`
- **GIVEN** the manifest holds 10 groups and 1 of them overrides `COLOR_ACCENT`
- **WHEN** scope is `All icons` with a `COLOR_ACCENT` shape selected
- **THEN** the hint reads `Changes defaults.COLOR_ACCENT in defaults.yaml — affects all 9 icon groups that don't override it`

### Requirement: Displayed counts and lists derive from loaded data
Every count and list the UI states — affected variants, affected groups, shadowing groups, usage counts, and the token table — SHALL be computed from the loaded session data (`itr mapping show` output plus pending edits). The implementation SHALL contain no hardcoded group, variant, token, or count constants; adding, removing, or renaming a group, variant, placeholder, or token in the inputs SHALL change the displayed values with no code change.

#### Scenario: variant count follows the loaded group
- **GIVEN** a loaded group with 3 variants
- **WHEN** scope is `Whole group` with any of its placeholders selected
- **THEN** the hint states 3 variants, not any fixed number

#### Scenario: affected-group count follows the shadow set
- **GIVEN** the manifest holds 10 groups and 4 of them override the selected placeholder
- **WHEN** scope is `All icons`
- **THEN** the hint states 6 affected groups and names the 4 shadowing ones

#### Scenario: usage count follows the templates
- **GIVEN** a placeholder used by 3 shapes in 2 of the group's 5 variants
- **WHEN** a shape using it is selected
- **THEN** the panel shows `3 shapes across 2 variants`

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

### Requirement: Inputs are changeable through a picker that reloads the session
Each input row SHALL offer a picker control that lets the user point the session at a different SVG template root, icons manifest, or color scheme. Choosing a new input SHALL reload the session from the new path, clear the shape selection, and reset the pending-edit set to empty. While the pending-edit set is non-empty, all three input pickers SHALL be disabled until the user saves or reverts.

#### Scenario: picking a new manifest reloads the session
- **WHEN** the user chooses a different icons manifest through the picker
- **THEN** the group tree, previews, and mappings reload from the new file
- **AND** the shape selection is cleared and the diff pane is empty

#### Scenario: input pickers are locked while edits are pending
- **GIVEN** at least one pending edit exists
- **WHEN** the user looks at the inputs panel
- **THEN** all three pickers are disabled until the pending edits are saved or reverted

### Requirement: The group tree navigates groups and variants
The tree SHALL list every icon group with its variants. Selecting a group SHALL load that group into the preview pane; selecting a variant (in the tree or by clicking its thumbnail) SHALL make it the enlarged main preview and SHALL clear the shape selection.

#### Scenario: selecting another group loads it
- **WHEN** the user selects a group other than the loaded one
- **THEN** the center pane renders that group's variants with the first variant enlarged

#### Scenario: selecting a sibling variant re-targets the main preview
- **WHEN** the user clicks a sibling thumbnail or its tree entry
- **THEN** that variant becomes the enlarged preview
- **AND** the shape selection is cleared

### Requirement: Variant thumbnails mark variant-scoped overrides
A variant thumbnail SHALL carry an override marker when that variant has a variant-scoped `color_mappings` entry on disk or a pending variant-scoped edit in the pending-edit set.

#### Scenario: pending variant edit marks the thumbnail
- **WHEN** the user makes a `This variant only` pick for a variant
- **THEN** that variant's thumbnail shows the override marker before saving

### Requirement: The preview offers a whole-group versus single-variant view
The canvas bar SHALL offer a toggle switching the center pane between the whole-group view (default) and a single-variant view showing only the selected variant. Switching views SHALL NOT alter the selection, scope, or pending edits.

#### Scenario: collapsing to a single variant
- **WHEN** the user deactivates the whole-group toggle
- **THEN** only the selected variant is previewed
- **AND** the selection, scope, and pending edits are unchanged

### Requirement: Failures surface without losing work
`itr` and filesystem failures SHALL be shown in the GUI without discarding session state. A picker choice pointing at a missing or unreadable file SHALL show an error and keep the previous input. A failed `Save` SHALL show the error and retain every pending edit. Saving while `icons.yaml` or `defaults.yaml` changed on disk since load SHALL be blocked with an error offering reload.

#### Scenario: unreadable input keeps the session
- **WHEN** the user picks a manifest path that cannot be read
- **THEN** an error is shown
- **AND** the session keeps the previous manifest, selection, and pending edits

#### Scenario: failed save retains pending edits
- **WHEN** `Save` fails partway through applying pending edits
- **THEN** the error is shown and the unsaved edits remain in the diff pane

#### Scenario: stale files block saving
- **WHEN** the user saves after `icons.yaml` changed on disk since load
- **THEN** the save is blocked with an error offering to reload from disk
