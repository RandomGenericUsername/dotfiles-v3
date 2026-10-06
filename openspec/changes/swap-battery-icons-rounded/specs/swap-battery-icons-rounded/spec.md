## ADDED Requirements

### Requirement: The status-bar battery templates SHALL carry palette placeholders, never literal colours

Each of the ten `status-bar/battery/battery-{0,25,50,75,100}[-charging]/default/icon.svg`
templates SHALL express every paint value as an ITR placeholder. No template in
that set SHALL contain a literal colour.

Rationale: ITR substitutes only `{{PLACEHOLDER}}` tokens
(`PLACEHOLDER_VALUE_RE = r"\{\{(\w+)\}\}"`,
`icon_templates_renderer/domain/services.py`), and the WCAG contrast guard
rewrites only `PLACEHOLDERS = ("COLOR_FOREGROUND", "COLOR_JOIN")`
(`runtime/domain/icon_contrast.py:42`). A literal such as `black` or `#0F0000`
is byte-preserved by both, so it would ship near-black permanently and could
never be retargeted on a light wallpaper.

The ring, the nub and the charge-level fill SHALL use `{{COLOR_FOREGROUND}}`. The
charging bolt SHALL use `{{COLOR_ACCENT}}`, matching the vocabulary already used
by `status-bar/battery/battery-100-charging/default/icon.svg`.

#### Scenario: No literal colour survives in the battery template set
- **WHEN** the ten battery templates are searched for `#`, for the word `black`, and for any other named colour
- **THEN** the match count is zero for each

#### Scenario: Every placeholder resolves
- **WHEN** each placeholder in the ten templates is resolved through the merge of variant, group and vocabulary `color_mappings` in `icons.yaml` / `defaults.yaml`
- **THEN** every placeholder name has a mapping, and no unresolved placeholder remains

#### Scenario: The charging bolt takes the accent token
- **WHEN** a charging variant is rendered
- **THEN** its bolt resolves `{{COLOR_ACCENT}}` to the group's `color13` while every other shape resolves `{{COLOR_FOREGROUND}}` to `color15`

#### Scenario: The unplugged templates reference only the foreground token
- **WHEN** `battery-{0,25,50,75,100}` are rendered
- **THEN** they reference only `{{COLOR_FOREGROUND}}`, because the `system-battery-*` variants pin only that token

### Requirement: The new artwork SHALL replace the existing templates in place, not sit beside them

The swap SHALL be an in-place replacement of the ten existing template files. No
`rounded` style, no new variants, no new icon groups, and no new variant names
SHALL be introduced, and `icons.yaml`, `icons.json`, `bar_mappings.states` and
`verify_icons_samples` SHALL be byte-identical to `master`.

Rationale: the `system-battery-{0,25,50,75,100}` variants used by the Bluetooth
device rows point at the SAME five unplugged templates. Replacing the templates
updates those rows automatically; a parallel set would leave them rendering the
old artwork beside a new bar icon.

#### Scenario: The Bluetooth rows pick up the new artwork
- **WHEN** `system-battery-{0,25,50,75,100}` are rendered
- **THEN** they resolve to the new rounded artwork, differing from the bar variants only in that `COLOR_FOREGROUND` maps to `foreground` instead of `color15`

#### Scenario: No parallel style is introduced
- **WHEN** the change is reviewed
- **THEN** the diff contains exactly ten modified files, all under `dotfiles/assets/icon-templates/status-bar/battery/`, and `icons.yaml` and `icons.json` are byte-identical to `master`

#### Scenario: The plugged icon is unaffected
- **WHEN** `status-bar/battery/plugged/default/icon.svg` is compared against `master`
- **THEN** it is byte-identical

### Requirement: Only paint values SHALL change; geometry SHALL be byte-faithful to the source

The replacement SHALL preserve every geometric attribute of the source artwork:
the `d` data of every path, `transform`, `stroke-width`, the `rx` on the nub
`<rect>`, `viewBox`, and element order. Only the values of `fill` and `stroke`
SHALL be rewritten.

#### Scenario: Geometry is provably unchanged
- **WHEN** every `fill=`/`stroke=` value in both the source and the installed template is normalised to a single token and the two texts are byte-compared
- **THEN** they are identical for all ten files

#### Scenario: The nub's rounded corners and rotation survive
- **WHEN** the installed nub `<rect>` is inspected
- **THEN** it still carries `rx="50"` and `transform="rotate(90 1006.08 375)"`

### Requirement: Widget behaviour SHALL be unchanged

The battery widget's state machine, its thresholds, and every icon name it
requests SHALL be untouched. Only the artwork behind the names changes.

#### Scenario: Variant names are unchanged
- **WHEN** `bar_mappings.states` is compared against `master`
- **THEN** all eleven state keys map to the same variant names, and those are exactly the names `getBatteryStateKey()` in `bar/widgets/battery.tsx` requests

#### Scenario: The manifest projection stays in step
- **WHEN** the battery variant names in `icons.json` are compared against those in `icons.yaml`
- **THEN** the two sets are equal, with no member on either side only

### Requirement: The source-to-variant mapping SHALL be derived from measured geometry

Each source file SHALL be assigned to its variant by measuring the charge-level
fill against the calibrated cavity (x ∈ [113, 756], width 643), not by trusting
the filename ordering, which wraps and is not the charge ramp.

The derivation SHALL parse each path's `d` data into per-element bounding boxes
and SHALL NOT read `max(x)` over raw file text.

Rationale: the ring path carries far larger x values than the fill and would
swamp a naive reading; Bézier control points overshoot the true edge; and all
five charging fills begin at a notch hook such as `M210.48 573.951` rather than
at `M113`, so a filter on `startswith("M113")` misses every charging icon.

#### Scenario: The full icon calibrates the cavity
- **WHEN** the 100% unplugged icon's fill is measured
- **THEN** it spans exactly x ∈ [113, 756], a width of 643

#### Scenario: The empty icons are identified by the absence of a fill path
- **WHEN** `-8` and `-9` are measured
- **THEN** neither contains a charge-level fill path, and `-8` is the unplugged empty icon while `-9` is the charging empty icon

#### Scenario: Charging parity is established from the artwork
- **WHEN** each file's ring paint and bolt are classified
- **THEN** the odd-numbered files carry a notch-cut filled ring and a bolt, and the even-numbered files carry a stroked ring and no bolt

#### Scenario: A clipped charge-level fill is not misread
- **WHEN** a charging fill's measured width under-reports its level because the diagonal notch clips it
- **THEN** the level is established from the ramp ordering and the subpath/start-point fingerprint shared with the repository's known-level charging templates, and the discrepancy is recorded rather than silently accepted