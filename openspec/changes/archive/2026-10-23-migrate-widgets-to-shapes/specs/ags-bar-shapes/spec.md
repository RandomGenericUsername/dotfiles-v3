# ags-bar-shapes (delta)

## ADDED Requirements

### Requirement: One Shell renderer for all four shapes

Every widget shape SHALL render through one shared shell implementation that
owns `class` / `stateClass`, `visible`, `tooltip`, the three gestures
(`primary` / `secondary` / `scroll`) and the pointer-anchor record. No shape
renderer SHALL re-implement any of them.

Source: spine **AD-8**; doc 101 §5.

#### Scenario: the shell is implemented once

- **WHEN** the four shape renderers in `kit/widget.tsx` are inspected
- **THEN** each builds its class/visible/tooltip and installs its gestures
  through the one shared `useShell` helper

#### Scenario: a rich widget renders its content

- **WHEN** a `RichWidgetSpec` with `content` is rendered
- **THEN** the renderer wraps `content(state, ctx)` in the shell and applies
  `visible`, `tooltip` and the gestures

#### Scenario: a collection renders its items

- **WHEN** a `CollectionSpec` is rendered
- **THEN** the renderer maps `items(state)` to the `item(item, state, ctx)`
  renderer keyed by `key(item)`

#### Scenario: a foreign collection renders adapter items

- **WHEN** a `ForeignCollectionSpec` is rendered
- **THEN** the renderer maps `items(state)` through the adapter-supplied
  `render(item, state, ctx)`

### Requirement: Layout is placement, resolved whole, repo default non-null

A `LayoutProvider` SHALL return a whole `BarLayout` or null. The resolution
chain SHALL be **user › runtime › repo-default**, the first non-null provider
wins, and the repo default SHALL always be non-null, so the bar renders with
nothing external. A `BarLayout` SHALL carry no version field of its own.

Source: spine **AD-9**; doc 101 §4.3.

#### Scenario: the highest-priority non-null provider wins

- **WHEN** the user provider returns a layout
- **THEN** its layout is used and the runtime and repo-default are not consulted

#### Scenario: a null provider is skipped

- **WHEN** the user provider returns null and the runtime provider returns a
  layout
- **THEN** the runtime layout is used

#### Scenario: the repo default is non-null

- **WHEN** every higher-priority provider returns null
- **THEN** the repo default's layout is returned, never null

#### Scenario: the default layout names each widget once

- **WHEN** the repo-default layout is inspected
- **THEN** every entry id is non-empty and appears at most once across the
  sections

### Requirement: The bar renders from the repo-default layout

`Bar.tsx` SHALL resolve the layout through the chain and render each section's
entries through the shape dispatcher, keyed by entry id. It SHALL NOT hardcode
the widget composition.

Source: spine **AD-8**, **AD-9**; doc 101 §4.3, §5.

#### Scenario: the composition is data

- **WHEN** `Bar.tsx` is searched for the widget components (`Workspaces`,
  `Clock`, `BatteryIndicator`, `NetworkStatus`, …)
- **THEN** none is present; the widgets are chosen from the layout

#### Scenario: an unknown entry degrades

- **WHEN** a layout entry id has no registered spec
- **THEN** that entry renders nothing (it is skipped, never a crash)

### Requirement: Each widget is declared on its frozen shape

The live widgets SHALL be declared as specs of the shape doc 101 §5 assigns
them: `clock` and `recording` as `RichWidgetSpec`; `workspaces` as
`CollectionSpec`; `tray` as `ForeignCollectionSpec`; `network`, `battery`,
`bluetooth` and `audio-output` as `DescriptorSpec`.

Source: spine **AD-8**; doc 101 §5, §13 step 6.

#### Scenario: the hand-rolled roots are gone

- **WHEN** the migrated widget files are searched for their own root markup and
  pointer-anchor bookkeeping (`EventControllerMotion`, `lastIconX`)
- **THEN** the shell owns them and the widget files do not

#### Scenario: behaviour is preserved

- **WHEN** a migrated widget is rendered
- **THEN** it resolves the same glyph, shows the same tooltip, fires the same
  click/secondary/scroll actions and honours the same visibility as before

### Requirement: The network descriptor replaces the hand-rolled widget

`network-descriptor.tsx` SHALL be wired as the bar's network entry and
`network.tsx` SHALL be retired, so the network glyph comes from the descriptor
read model and the state-key icon chain.

Source: spine **AD-8**, **AD-7**; doc 101 §5.

#### Scenario: the network descriptor is the network entry

- **WHEN** the bar's network entry renders
- **THEN** it uses the descriptor read model and the state-key icon chain, and
  `network.tsx` no longer exists

### Requirement: The audio microphone keeps its live-dot badge

The audio microphone indicator SHALL keep its live-dot badge. Because the
descriptor vocabulary carries no badge content, it SHALL be a
`RichWidgetSpec` (the one deviation from doc 101 §5's table, taken to preserve
the badge).

Source: spine **AD-8**; doc 101 §5.

#### Scenario: the live dot survives the migration

- **WHEN** the audio microphone indicator is rendered while an input stream is
  live
- **THEN** the microphone glyph and its live-dot badge both show

### Requirement: The recording indicator is its own placement entry

The recording indicator SHALL be a `RichWidgetSpec` placed by the layout (it is
no longer rendered inside the tray's foreign collection), so placement is data.

Source: spine **AD-8**, **AD-9**.

#### Scenario: the tray no longer owns the recording indicator

- **WHEN** `tray.tsx` is searched for the recording indicator
- **THEN** it does not render it (the layout places it separately)

### Requirement: New sources are registered for deployment

`kit/layout.ts`, `bar/layout.default.ts` and `bar/registry.ts` SHALL be
registered in `compositor_configs_skeleton_files` and mirrored in the verify
role; the retired `bar/widgets/network.tsx` entry SHALL be removed from both.

Source: spine **AD-17** (per-file placement); `deploy-coverage` gate.

#### Scenario: deploy coverage is green

- **WHEN** `make deploy-coverage` runs
- **THEN** every AGS module reachable from `app.tsx` is registered, including
  the three new sources

#### Scenario: no manifest entry points at a deleted source

- **WHEN** the manifests are searched for `bar/widgets/network.tsx`
- **THEN** no entry is present (the file is retired)
