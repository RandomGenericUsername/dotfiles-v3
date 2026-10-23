# migrate-widgets-to-shapes

## Why

Spine **AD-8** freezes the widget vocabulary: every widget is one of four
shapes (`DescriptorSpec`, `RichWidgetSpec`, `CollectionSpec`,
`ForeignCollectionSpec`) sharing **one `Shell<S>`**, so anchoring, gestures,
tooltip, visibility and class handling are implemented once and can never diverge
per widget. Spine **AD-9** makes composition **placement only**: a layout
provider returns a whole `BarLayout` or null; the first non-null in the chain
**user › runtime › repo-default** wins, and the **repo default is always
non-null**. Doc 101 §5 maps each live widget to its shape; §13 step 6 ("Shapes")
is this step.

`kit-shell-four-shapes` (REQ-007 predecessor) defined the vocabulary but
deliberately supplied **no renderer** for the three non-descriptor shapes and
**no layout provider**; it recorded both as REQ-008. The hand-rolled widgets
still own their own roots, gestures and pointer-anchor bookkeeping, and
`Bar.tsx` still hardcodes the composition.

Evidence:

- `sed -n '32,52p' dotfiles/config/ags/bar/Bar.tsx` → the composition is
  hardcoded: `<Workspaces/> <Clock/> <Tray/> <OutputIndicator/> <MicIndicator/>
  <BatteryIndicator/> <BluetoothStatus/> <NetworkStatus/>` + four
  `<BarWidgetButton spec=…/>`.
- `grep -rn "RichWidgetSpec\|CollectionSpec\|ForeignCollectionSpec" dotfiles/config/ags/bar` →
  no matches (the widgets are not declared on the shapes).
- `ls dotfiles/config/ags/bar/layout.default.ts dotfiles/config/ags/kit/layout.ts` →
  both absent (there is no layout provider).
- `grep -n "network-descriptor\|NetworkStatus" dotfiles/config/ags/bar/Bar.tsx` →
  `Bar.tsx` imports `NetworkStatus` from `./widgets/network`; the descriptor
  (`network-descriptor.tsx`) is unreferenced.
- `grep -rn "lastIconX\|EventControllerMotion" dotfiles/config/ags/bar/widgets/*.tsx` →
  the pointer-anchor record is re-implemented in `network.tsx`, `battery.tsx`,
  `bluetooth.tsx` and `audio.tsx`.

Verify:

- `sed -n '32,52p' dotfiles/config/ags/bar/Bar.tsx`
- `grep -rn "RichWidgetSpec\|CollectionSpec\|ForeignCollectionSpec" dotfiles/config/ags/bar`
- `ls dotfiles/config/ags/bar/layout.default.ts dotfiles/config/ags/kit/layout.ts`
- `grep -n "network-descriptor\|NetworkStatus" dotfiles/config/ags/bar/Bar.tsx`
- `grep -rn "lastIconX\|EventControllerMotion" dotfiles/config/ags/bar/widgets/*.tsx`

## What Changes

### The shape renderers, on one Shell (AD-8)

- `kit/widget.tsx` gains a `BarWidget` dispatcher and the three missing
  renderers: `RichWidget` (`content`), `Collection` (`items`/`key`/`item`) and
  `ForeignCollection` (`items`/`render`). All four renderers (including the
  existing `BarWidgetButton`) build their class/visible/tooltip/gestures/anchor
  through **one** shared `useShell`, so no shape re-implements the shell.
- The collection shapes gain an optional `spacing` presentation hint (the one
  piece of collection layout the shared shell cannot express); the shared
  `Shell` is unchanged.

### The layout vocabulary and the repo default (AD-9)

- New pure `kit/layout.ts`: `BarEntry`, `BarLayout` (sections only — **no
  version field of its own**, AD-9), `LayoutProvider`, and the pure
  `resolveLayout(providers, repoDefault)` chain (first non-null wins; the repo
  default is returned when every provider yields null).
- New `bar/layout.default.ts`: the repo-default `LayoutProvider`
  (`repoDefaultLayout.load()` is **always non-null**) plus the default
  `BarLayout` placing the widgets in today's order.

### The widgets move onto the frozen shapes (AD-8)

- `clock.tsx` + `recording.tsx` → `RichWidgetSpec`.
- `workspaces.tsx` → `CollectionSpec`.
- `tray.tsx` → `ForeignCollectionSpec` (the recording indicator leaves the tray
  and becomes its own placement entry).
- `network-descriptor.tsx` is wired (the `DescriptorSpec`); `network.tsx` is
  retired. `battery.tsx`, `bluetooth.tsx` and `audio.tsx` become
  `DescriptorSpec`s, with the audio **microphone** rendered as a `RichWidgetSpec`
  because its live-dot badge is content the descriptor vocabulary cannot express
  (doc 101 §5 lists it as a descriptor; preserving the dot wins — see Impact).
- New `bar/registry.ts` maps a layout entry id to its spec (the four existing
  descriptors included); `Bar.tsx` resolves the layout and renders each section
  through `BarWidget` instead of a hardcoded composition.

### Tests prove the pure layout chain

- New `tests/ts/layout.test.ts`: the chain is whole-replacement (user wins over
  runtime over repo-default; a null provider is skipped) and the repo default is
  non-null; the default layout's ids are unique and non-empty.

### Deploy manifest (hard constraint)

- New `kit/layout.ts`, `bar/layout.default.ts` and `bar/registry.ts` are
  registered in `compositor_configs_skeleton_files` (+ the `verify` mirror);
  the retired `bar/widgets/network.tsx` entry is **removed** from both, so a
  fresh provision never points at a deleted source.

## Out of scope

- **The capability schema, validators and manifest** (AD-14/AD-15). This change
  maps ids to specs in a small hand-written registry; the pure-data
  `bar-manifest` and the two validators are a later step.
- **`BarContext` injection** (AD-2/AD-20 step 8). The renderer threads a minimal
  context (the real `hub.control`; `popup` reserved for the platform
  extraction); widgets that open a surface still go through the existing
  `overlays` coordinator.
- **The `bar.json` user/runtime layout override** (AD-9/AD-16). The chain is
  implemented and tested but only the repo default is wired; the artifact does
  not exist yet.
- **No visual restyle.** Window names, classes, anchors, glyphs, tooltips,
  gestures and visibility are preserved. The one structural difference: the
  recording indicator moves from inside the tray box to its own placement entry
  (same order; the tray box's 4px horizontal padding no longer brackets it).

## Impact

- New: `dotfiles/config/ags/kit/layout.ts`,
  `dotfiles/config/ags/bar/layout.default.ts`,
  `dotfiles/config/ags/bar/registry.ts`,
  `dotfiles/config/ags/tests/ts/layout.test.ts`.
- Edited: `dotfiles/config/ags/kit/{shapes.ts,widget.tsx}`,
  `dotfiles/config/ags/bar/Bar.tsx`,
  `dotfiles/config/ags/bar/widgets/{clock,recording,workspaces,tray,network-descriptor,battery,bluetooth,audio}.tsx`,
  `dotfiles/config/ags/tests/tsconfig.tests.json`,
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml`,
  `src/provisioning/tests/unit/test_compositor_configs_role.py`,
  `src/provisioning/tests/unit/test_verify_role.py`.
- Deleted: `dotfiles/config/ags/bar/widgets/network.tsx` (and its two manifest
  entries).
- No behaviour change on a provisioned host beyond the recording indicator's
  4px placement note above: the same glyphs resolve, the same gestures fire, the
  same surfaces open.
