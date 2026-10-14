# ags-bar-kit (delta)

## ADDED Requirements

### Requirement: The icon contract carries a last-resort fallback

`IconRef<S>` SHALL declare `fallback?: (variant: string) => IconSource | null`,
and `IconSource` SHALL be a tagged union
`{ kind: "file"; path } | { kind: "name"; name }`.

Source: spine **AD-4**, **AD-7**.

#### Scenario: a tableless provider degrades to the ref's fallback

- **WHEN** a ref declares a `fallback` and the provider has no `bar_mappings`
  table for its group
- **THEN** resolution returns the `IconSource` the fallback produced

#### Scenario: a blank is returned when nothing resolves

- **WHEN** neither the provider table, `provider.resolve`, nor `ref.fallback`
  yields an `IconSource`
- **THEN** resolution returns `null` (blank), never throws

### Requirement: One resolution chain for every icon

Icon resolution SHALL follow one chain — `provider.barMappings(group)?.states[v]`
→ `provider.resolve(group, …)` → `ref.fallback(v)` → blank — where `v` is the
ref's emitted state key or variant name. `resolveIcon` SHALL implement this chain
and keep returning a file path for `{kind:"file"}` sources.

Source: spine **AD-4**, **AD-7**; doc 101 §7.

#### Scenario: the provider table wins over the fallback

- **WHEN** the provider has a table mapping the emitted key to a variant it can
  resolve
- **THEN** the provider's `IconSource` is returned and the fallback is not called

#### Scenario: the fallback is consulted after the provider misses

- **WHEN** the provider table maps the key but `provider.resolve` yields nothing
- **THEN** `ref.fallback(v)` is consulted, and the chain returns blank only if it
  yields nothing

### Requirement: One Shell shared by four widget shapes

The widget vocabulary SHALL be four shapes — `DescriptorSpec<S>`,
`RichWidgetSpec<S>`, `CollectionSpec<I, S>`, `ForeignCollectionSpec<I, S>` — all
extending one `Shell<S>` carrying `id`, `read`, `tooltip?`, `visible?`, `class?`,
`stateClass?`, `pixelSize?`, `primary?`, `secondary?`, `scroll?`. Anchoring,
gestures, tooltip, visibility and class handling SHALL live only in the `Shell`.

Source: spine **AD-8**; doc 101 §5.

#### Scenario: a shape is a Shell

- **WHEN** any of the four shapes is used where a `Shell<S>` is expected
- **THEN** it is assignable, so a shared renderer can handle the common fields

#### Scenario: the descriptor vocabulary is unchanged

- **WHEN** the four live descriptors (btop, thunderbird, settings, power-menu)
  declare `BarWidgetSpec<S>`
- **THEN** they typecheck, because `BarWidgetSpec<S>` is realized from
  `DescriptorSpec<S>`

### Requirement: The rich shape renders through `content`

`RichWidgetSpec<S>` SHALL add a `content: (state: S, ctx: BarContext) => JSX.Element`
field, so an irregular widget (clock, recording) is a named shape rather than a
generic catch-all.

Source: spine **AD-8**; doc 101 §5.

#### Scenario: a rich widget supplies content

- **WHEN** a `RichWidgetSpec` is constructed
- **THEN** it must supply `content`, and it still satisfies `Shell<S>`

### Requirement: `popup` and `hub.control` are capabilities, not shapes

`popup(...)` and `hub.control(...)` SHALL be `BarContext` capabilities that any
shape may call. No widget shape SHALL be minted for them.

Source: spine **AD-8**; doc 101 §5.

#### Scenario: the vocabulary has exactly four shapes

- **WHEN** the kit's exported widget shapes are enumerated
- **THEN** there are four (`DescriptorSpec`, `RichWidgetSpec`, `CollectionSpec`,
  `ForeignCollectionSpec`) and no popup/control spec
