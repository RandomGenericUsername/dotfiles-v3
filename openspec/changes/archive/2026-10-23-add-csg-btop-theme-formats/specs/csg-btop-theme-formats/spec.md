## ADDED Requirements

### Requirement: Three btop color formats exist in CSG
The `ColorFormat` enum SHALL contain `BTOP_MINIMAL`, `BTOP_BALANCED`, and
`BTOP_FULL` with values `btop-minimal.theme`, `btop-balanced.theme`, and
`btop-full.theme` respectively, and each SHALL have a corresponding
`colors.<value>.j2` template in the default template catalog. Each format SHALL
render to `colors.<value>` through the same path as every other format, with no
special-casing. An unknown `colors.<key>.j2` SHALL still be rejected by the
catalog.

A format's enum member and its template are a single inseparable unit: the
catalog derives from `ColorFormat`, so neither may be added without the other.

#### Scenario: catalog discovers all three btop templates
- **GIVEN** a templates directory containing `colors.btop-minimal.theme.j2`,
  `colors.btop-balanced.theme.j2`, and `colors.btop-full.theme.j2`
- **WHEN** the catalog is derived
- **THEN** it contains three entries with formats `ColorFormat.BTOP_MINIMAL`,
  `ColorFormat.BTOP_BALANCED`, and `ColorFormat.BTOP_FULL`
- **AND** an unknown `colors.bogus.j2` still raises `TemplatesValidationError`

#### Scenario: rendering produces the expected artifact filenames
- **GIVEN** a generation request whose formats include all three btop formats
- **WHEN** the scheme is rendered
- **THEN** `output_dir/colors.btop-minimal.theme`,
  `output_dir/colors.btop-balanced.theme`, and `output_dir/colors.btop-full.theme`
  all exist
- **AND** each file's extension is `.theme`

### Requirement: A rendered btop theme uses valid btop theme syntax
A rendered btop theme SHALL be parseable by btop 1.4.7's theme loader. Every
non-blank, non-comment line SHALL begin at **column 0** — btop treats `#` as a
comment only at offset 0, and leading whitespace before `[` causes the parser to
skip forward and mangle the line.

Every `theme[...]` key SHALL be a member of btop's 48-key set, matched exactly
and case-sensitively. Every value SHALL be a quoted `"#RRGGBB"`, a quoted `"#GG"`
greyscale value, or a quoted `"R G B"` decimal triple. 8-digit/alpha hex SHALL
NOT be emitted.

All colours SHALL come from the shared `ColorScheme` model (`background`,
`foreground`, `cursor`, `colors[0..15]`) and never be invented, so the artifacts
cannot drift from the other consumers.

#### Scenario: every emitted line starts at column 0
- **GIVEN** any rendered btop theme
- **WHEN** every line is inspected
- **THEN** no non-blank line begins with whitespace

#### Scenario: every key is in btop's key set
- **GIVEN** any rendered btop theme
- **WHEN** its `theme[...]` keys are collected
- **THEN** every key is a member of btop 1.4.7's `Default_theme` key set
  (48 keys, exact case-sensitive match)

#### Scenario: every value is a valid colour form
- **GIVEN** any rendered btop theme
- **WHEN** each value is parsed
- **THEN** it matches `#RRGGBB`, `#GG`, or `R G B` with integer components
- **AND** no value is 8 hex digits long

### Requirement: A rendered btop theme defines all 48 keys
Each rendered theme SHALL define all 48 keys rather than relying on btop's
built-in fallbacks, so the artifact is self-describing and cannot silently
inherit a stock-theme color if btop's defaults change. This SHALL include the
process-state keys added in btop 1.4.6: `proc_pause_bg`, `proc_follow_bg`,
`proc_banner_bg`, `proc_banner_fg`, `followed_bg`, `followed_fg`.

All three of `process_start`, `process_mid`, and `process_end` SHALL be defined
together. btop's fallback is guarded on `process_start` alone while
`generateGradients` reads `rgbs["process_end"]` via `operator[]`, so defining
only a subset produces a gradient that fades to black.

#### Scenario: all 48 keys are present
- **GIVEN** any rendered btop theme
- **WHEN** its keys are collected
- **THEN** the key set equals btop 1.4.7's full 48-key set

#### Scenario: the process gradient cannot fade to black
- **GIVEN** any rendered btop theme
- **WHEN** `process_start`, `process_mid`, and `process_end` are read
- **THEN** all three are present and non-empty

### Requirement: Gradients are mapped by what btop renders, not by key name
Each gradient SHALL be assigned colours according to the element btop actually
paints with it, as follows: `temp` (CPU/core/GPU temperature, relative-scaled to
the detected maximum), `cpu` (CPU meter, GPU utilisation, per-core graphs,
encode/decode meters, battery), `cached` (**power draw** in watts and P-state),
`available` (**disk I/O activity**), `used` (memory/disk in use, GPU VRAM),
`free` (memory/disk free, GPU memory utilisation), `download` and `upload`
(network throughput), `process` (process-list thread/memory/CPU usage).

An implementation SHALL NOT assume `cached` means cache or `available` means free
memory.

#### Scenario: the power gradient is treated as power
- **GIVEN** a rendered btop theme
- **WHEN** `cached_start`/`cached_mid`/`cached_end` are assigned
- **THEN** they are chosen as a consumption/power reading, grouped with `used`
- **AND** they are not chosen on the assumption that they paint cache state

#### Scenario: the disk-activity gradient is treated as I/O
- **GIVEN** a rendered btop theme
- **WHEN** `available_start`/`available_mid`/`available_end` are assigned
- **THEN** they are grouped with `free` as a "room remaining" reading

### Requirement: The three variants form a monotonic difficulty dial
`csg-minimal`, `csg-balanced`, and `csg-full` SHALL differ only in which
gradients are forced to a semantic cool→warm ramp; all other assignments SHALL be
identical across the three.

- `csg-minimal` — no gradient is forced semantic; every gradient is a slice of
  the palette's luminance ramp.
- `csg-balanced` — `temp` and `cached` SHALL additionally be semantic.
- `csg-full` — `temp`, `cached`, and `cpu` SHALL additionally be semantic.

A semantic gradient SHALL increase monotonically in perceived heat from
`_start` to `_end`, so that a higher reading is never cooler than a lower one.

#### Scenario: minimal is fully ramp-derived
- **GIVEN** rendered `colors.btop-minimal.theme` and `colors.btop-balanced.theme`
- **WHEN** all gradients are compared
- **THEN** they are identical except `temp_*` and `cached_*`
- **AND** in the minimal variant every gradient stop is drawn from the palette's
  luminance ramp

#### Scenario: balanced differs from full only by cpu
- **GIVEN** rendered `colors.btop-balanced.theme` and `colors.btop-full.theme`
- **WHEN** all gradients are compared
- **THEN** they are identical except `cpu_*`

#### Scenario: the dial is monotonic
- **GIVEN** the three rendered themes
- **WHEN** the set of semantic gradients is compared
- **THEN** it is a superset chain: none ⊆ {temp, cached} ⊆ {temp, cached, cpu}

#### Scenario: a semantic gradient never cools as the reading rises
- **GIVEN** a gradient marked semantic in any variant
- **WHEN** its `_start`, `_mid`, and `_end` stops are compared in CIELAB
- **THEN** each successive stop is not cooler than the previous

### Requirement: Semantically forced gradients are relative-safe
A gradient forced to a semantic cool→warm ramp SHALL remain meaningful when the
palette changes. `temp` SHALL be treated as relative (btop scales it against the
detected temperature maximum, not an absolute scale), so "warmer" means "closer
to this machine's ceiling" and the reading survives a wallpaper change.

#### Scenario: temp meaning is relative, not absolute
- **GIVEN** themes rendered from two different source images
- **WHEN** the `temp_*` semantic stops are compared
- **THEN** each still increases monotonically in perceived heat from `_start`
  to `_end`

### Requirement: Throughput gradients use btop's two-stop idiom
`download_*` and `upload_*` measure throughput, for which a three-stop luminance
ramp has no meaningful direction. These SHALL omit their `_mid` key by emitting
an empty value (`theme[<x>_mid]=""`), which btop interprets as a two-stop
gradient.

#### Scenario: throughput gradients are two-stop
- **GIVEN** any rendered btop theme
- **WHEN** `download_mid` and `upload_mid` are read
- **THEN** they are empty strings
- **AND** `download_start`, `download_end`, `upload_start`, and `upload_end` are
  all present and non-empty

### Requirement: Box outlines are visually neutral
`cpu_box`, `mem_box`, `net_box`, `proc_box`, and `div_line` SHALL all resolve to
one shared dim colour drawn from the palette, so box chrome does not compete with
the data gradients.

#### Scenario: outlines share one colour
- **GIVEN** any rendered btop theme
- **WHEN** `cpu_box`, `mem_box`, `net_box`, `proc_box`, and `div_line` are read
- **THEN** `cpu_box`, `mem_box`, `net_box`, and `proc_box` are all equal
- **AND** all five are drawn from the palette's ramp

### Requirement: Theme application is verifiable without human inspection
It SHALL be possible to prove, from a command's exit code alone, that btop both
**loaded** and **applied** a generated theme. The proof SHALL NOT rely on a person
observing a running btop.

Two assertions SHALL be available:

- **Load assertion.** With btop's log level set to `DEBUG`, the run log SHALL
  contain a `Loading theme file:` entry naming the generated theme file
  (`src/btop_theme.cpp:397`). When the configured `color_theme` does not resolve
  to a discovered theme, btop silently falls back to `Default_theme` and emits no
  such entry.
- **Application assertion.** Running btop on a real pseudo-terminal and capturing
  the rendered frame SHALL yield 24-bit colour sequences attributable to the
  generated theme, and SHALL NOT yield any of btop's built-in `Default_theme`
  colours.

A verification that cannot fail SHALL NOT be accepted as evidence: the harness
SHALL include a negative control that fails when the theme is absent, and SHALL
treat any internal error as a failure rather than a pass.

#### Scenario: a generated theme is proved applied
- **GIVEN** the three rendered themes
- **WHEN** the application harness runs against each
- **THEN** each produces a `Loading theme file:` entry naming that theme
- **AND** each frame is dominated by that theme's colours with zero
  `Default_theme` colours present
- **AND** the command exits 0

#### Scenario: an unresolvable theme is detected
- **GIVEN** a `color_theme` naming a theme file that is not present
- **WHEN** the application harness runs
- **THEN** the load assertion fails because no `Loading theme file:` entry exists
- **AND** the frame contains `Default_theme` colours
- **AND** the command exits non-zero

#### Scenario: an absent btop binary skips visibly
- **GIVEN** a machine without the `btop` binary
- **WHEN** the application harness runs
- **THEN** it skips with a stated reason and exits 0
- **AND** the skip is visible in its output rather than being silently green

#### Scenario: a harness error is not a pass
- **GIVEN** any internal error while asserting theme application
- **WHEN** the harness completes
- **THEN** it reports a failure and exits non-zero
