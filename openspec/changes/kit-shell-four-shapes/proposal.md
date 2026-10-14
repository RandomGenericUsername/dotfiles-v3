# kit-shell-four-shapes

## Why

The AGS bar kit (`dotfiles/config/ags/kit/`) froze two vocabularies too early for
the platform extraction (spine **AD-4**, **AD-7**, **AD-8**; doc 101 §5, §7):

- **One widget type, no shared shell.** `BarWidgetSpec<S>` (`kit/widget.tsx:19`)
  is the only shape. Doc 101 §5 / **AD-8** fix four shapes — `DescriptorSpec`,
  `RichWidgetSpec`, `CollectionSpec`, `ForeignCollectionSpec` — all sharing one
  `Shell<S>`, so anchoring, gestures, tooltip, visibility and class handling can
  never diverge per widget.
- **One icon contract with no last resort.** `IconRef` (`kit/icon.ts:13`) has no
  `fallback`, and `resolveIcon` (`kit/icon.ts:43`) returns a bare path `string`.
  **AD-4** adds `IconRef.fallback?: (variant: string) => IconSource | null` and a
  tagged-union `IconSource` (`{kind:"file"|"name"}`); **AD-7** fixes the
  resolution chain `provider.barMappings(group)?.states[v] → provider.resolve(...)`
  → `ref.fallback(v)` → blank.

Evidence: `kit/widget.tsx:19-49` (one type, no `Shell`); `kit/icon.ts:13-17`
(`IconRef` without `fallback`); `kit/icon.ts:43-46` (`resolveIcon` returns `string`).
Verify: `grep -n "interface BarWidgetSpec\|interface IconRef\|function resolveIcon" dotfiles/config/ags/kit/widget.tsx dotfiles/config/ags/kit/icon.ts`.

## What Changes

### Icon contract (AD-4, AD-7)

- New pure module `kit/icon-source.ts`: `IconSource` tagged union, the
  `IconProvider` port (`barMappings?`, `resolve`), `IconRef<S>` with `fallback?`,
  the `iconByVariant` / `iconByStateKey` constructors, and the pure
  `resolveIconSource(provider, ref, state)` implementing the full chain.
- `kit/icon.ts` becomes the registry-backed facade: it adapts `registry` to
  `IconProvider` (returning `{kind:"file"}`, as today), re-exports the pure
  contract, and keeps `resolveIcon(ref, state): IconSource | null` delegating to
  the chain.
- `BarWidgetButton` adapts to the tagged union: `file` → `set_from_file(path)`
  (the current path-returning behavior, preserved), `name` → `set_from_icon_name`,
  blank → `set_from_file("")`.

### Shell + four shapes (AD-8)

- New pure module `kit/shapes.ts`: one `Shell<S>` (`id`, `read`, `tooltip?`,
  `visible?`, `class?`, `stateClass?`, `pixelSize?`, `primary?`, `secondary?`,
  `scroll?`) and the four shapes extending it. `DescriptorSpec<S>` adds
  `icon?`/`label?` and is realized from today's `BarWidgetSpec<S>` (kept as an
  alias so the four live descriptors — btop, thunderbird, settings, power-menu —
  typecheck unchanged). `RichWidgetSpec<S>` adds the rich
  `content: (state, ctx: BarContext) => JSX.Element`.
- A minimal `BarContext` port names the two capabilities AD-8 calls out
  (`popup(...)`, `hub.control(...)`) — **capabilities, not shapes**. No
  `PopupSpec`/`ControlSpec` is introduced.

### Tests

- Unit tests for the fallback chain (`resolveIconSource`) and for the shape /
  `Shell` typing, added to the pure `ags-test` suite.

## Non-goals / out of scope

- **No widget migration.** The hand-rolled widgets (network, battery, bluetooth,
  audio, clock, recording, workspaces, tray) are NOT rewritten onto the new
  shapes — that is REQ-008. This change defines the vocabulary and the fallback.
- **No new renderer.** `BarWidgetButton` remains the `DescriptorSpec` renderer;
  `RichWidgetSpec` / `CollectionSpec` / `ForeignCollectionSpec` are vocabulary
  only until REQ-008 supplies their renderers.
- **No platform port extraction.** The full `BarContext` (hub, surfaces,
  notifier, preferences, theme) and a named `OverlayCoordinator` are minted in
  the platform extraction, not here; this change only types the capability seam
  the `content` signature needs.
- **No injection rework.** The registry stays a module value behind the `icon.ts`
  facade (AD-2's no-globals rule lands with the platform extraction).

## Impact

- `dotfiles/config/ags/kit/{icon.ts,widget.tsx}` edited; `kit/icon-source.ts`,
  `kit/shapes.ts` new.
- `dotfiles/config/ags/tests/tsconfig.tests.json` include list extended;
  `tests/ts/kit-icon-source.test.ts`, `tests/ts/kit-shapes.test.ts`,
  `tests/ts/jsx.d.ts` new.
- No behavior change on a provisioned host: the four live descriptors resolve to
  the same file paths they do today.
