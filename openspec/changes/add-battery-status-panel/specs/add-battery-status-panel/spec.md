## ADDED Requirements

### Requirement: Power-mode glyphs SHALL be palette-aware templates

A `power-mode` icon group SHALL exist in the ITR manifest
(`dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`) with exactly
three variants — `powersave`, `balanced`, `performance` — each backed by a
template at `dotfiles/assets/icon-templates/power-mode/<name>/default/icon.svg`.

Every hardcoded near-black fill in those templates SHALL be the ITR placeholder
`{{COLOR_FOREGROUND}}`, and the group SHALL map it to the palette's `foreground`.
Geometry (path data, `transform`, `fill-rule`, `clip-rule`, `viewBox`, element
order) SHALL be byte-identical to the source art.

Rationale: the panel sits on a dark-glass surface
(`alpha(@color_00, 0.94)` over a transparent window). ITR substitutes only
recognised `{{PLACEHOLDER}}` values, so a literal `fill="black"` — or a literal
`#0F0000`, which is a near-black rather than a palette token — stays literal and
renders invisibly.

#### Scenario: No literal fill colour survives
- **WHEN** each `power-mode` template is read
- **THEN** it contains no `fill="black"` and no `fill="#0F0000"`
- **AND** it contains `{{COLOR_FOREGROUND}}` once per source fill (`powersave` 4,
  `balanced` 2, `performance` 3)
- **AND** the root element's `fill="none"` is preserved

#### Scenario: Geometry is unchanged from the source
- **WHEN** the source and the template are both read with every fill VALUE masked
- **THEN** the two are byte-identical

#### Scenario: Every variant resolves to a real template
- **WHEN** `itr list` runs against the group
- **THEN** every variant's `template` path exists relative to the icon-template
  root, every `name` is unique, and every `output` filename is unique

### Requirement: The `power-mode` group SHALL NOT be a bar group, and SHALL NOT have `system-*` copies

`power-mode` SHALL be absent from `BAR_GROUPS`
(`src/runtime/src/runtime/domain/icon_contrast.py`), and the group SHALL declare
no `system-*` duplicate variants.

Rationale, recorded here because it is the one decision in this change that is
easy to get backwards:

- The icon-contrast guard retargets `BAR_GROUPS` to the highest-contrast palette
  token against the **wallpaper's top band**. `power-mode` glyphs are consumed
  only by the battery panel's power-mode list, whose rows sit on the **dark glass
  panel surface**, which never changes with the wallpaper. Adding the group to
  `BAR_GROUPS` would therefore let a light wallpaper push the token bright
  against an already-dark surface — the guard's own wash-out, inverted.
  Leaving it out leaves `{{COLOR_FOREGROUND}}` resolving to the theme foreground,
  which is correct on dark glass.
- `battery` **is** in `BAR_GROUPS` precisely because it renders in the transparent
  status bar and floats over the wallpaper. The two groups are both about the
  battery, which is why the distinction is written down rather than assumed.
- The standing rule in `docs/Adding an Icon — ITR and Provisioning Pipeline.md`
  §14 ("any group consumed on dark glass MUST expose `system-*` copies from day
  one") exists because one render serves both the transparent bar and dark glass,
  and a variant-level `COLOR_FOREGROUND` pin is *structurally* exempt from a
  guard that rewrites only **group-level** placeholders. `power-mode` has no bar
  consumer, so there is nothing to be exempt from; a `system-*` copy would be a
  second render of identical art that nothing resolves.

#### Scenario: The group is absent from the guard allowlist
- **WHEN** `BAR_GROUPS` in `src/runtime/src/runtime/domain/icon_contrast.py` is read
- **THEN** `"power-mode"` does not appear in it

#### Scenario: The guard leaves the mapping alone
- **WHEN** the contrast guard runs against a light wallpaper
- **THEN** it emits no override for the `power-mode` group, and the rendered
  glyph resolves `COLOR_FOREGROUND` to the plain theme `foreground`

#### Scenario: No duplicate outputs exist
- **WHEN** the `power-mode` group's variants are listed
- **THEN** no variant name begins with `system-` and no output filename repeats
  the same template

#### Scenario: The reasoning travels with the file
- **WHEN** the `power-mode` block of `icons.yaml` is read
- **THEN** its comment states why the group is not a bar group and why there are
  no `system-*` copies

### Requirement: The AGS icon manifest SHALL be generated from the manifest, never hand-edited

`dotfiles/config/ags/icons.json` SHALL be produced from `icons.yaml` by the
compositor configuration role's generator expression
(`(from_yaml) | to_nice_json(indent=2)`), and adding an icon group SHALL consist of
editing `icons.yaml` only.

#### Scenario: The new group appears in the generated manifest
- **WHEN** `icons.json` is regenerated from `icons.yaml`
- **THEN** a `power-mode` group exists carrying the same
  `color_mappings` and the same three `name`/`template`/`output` triples

#### Scenario: An unrelated group is unchanged
- **WHEN** `icons.json` is regenerated after adding `power-mode`
- **THEN** the `battery` group is byte-identical to its previous content

#### Scenario: The bar widget's contrast treatment is untouched
- **WHEN** the hexagonal structure gate runs
- **THEN** check 6 still reports 33 used / 28 styled CSS class tokens

### Requirement: The AGS config SHALL have a unit-test harness for its pure modules

A `make ags-test` target SHALL run `node --test` over TypeScript unit tests for
the ags config's pure modules, followed by `tsc --noEmit` over a dedicated tests
config, and SHALL be part of `gates` and `gates-ci` with a matching job in
`.github/workflows/gates.yml`.

The harness SHALL declare its dependencies rather than inherit them, and SHALL
fail — never skip — when its toolchain is unresolvable.

Rationale: `make capture-test` covers the capture tool's domain and nothing
covered `dotfiles/config/ags/`'s own logic. Without this gate, every pure
decision in the config is reachable only by rendering a live GTK panel.

#### Scenario: The gate is part of the CI set
- **WHEN** `make gates-ci` is inspected
- **THEN** `ags-test` is among the targets it runs
- **AND** `.github/workflows/gates.yml` contains a job that runs `make ags-test`

#### Scenario: The gate needs no desktop stack
- **WHEN** `make ags-test` runs on a machine with no `ags`, no Astal and no GTK4
- **THEN** the test run and the `tsc` pass both succeed

#### Scenario: Dependencies are declared, not inherited
- **WHEN** the gate needs a toolchain package that is not installed
- **THEN** it installs it with `npm install --no-save --no-package-lock` into a
  gitignored `node_modules`, committing no `package.json` and no lockfile

#### Scenario: The install cannot prune another gate's dependencies
- **WHEN** `ags-test` installs its own dependencies
- **THEN** it does so with `--prefix` into a separate npm project, so the
  repository-root install that `capture-test` shares is left intact

#### Scenario: A present dependency skips the network
- **WHEN** the gate runs on a machine where its toolchain is already installed
- **THEN** it does not perform a network round-trip

#### Scenario: A missing toolchain is a failure, not a skip
- **WHEN** `node`, `npx`, `tsc` or `@types/node` is unresolvable
- **THEN** `make ags-test` exits non-zero and reports which one is missing

#### Scenario: The new gate does not disturb the existing one
- **WHEN** `make capture-test` runs
- **THEN** it reports 144 passed, 0 failed, 0 skipped, unchanged

#### Scenario: Nothing unresolvable is silently ignored
- **WHEN** `make ags-test` completes successfully
- **THEN** every test in the suite is reported as passed, with zero skipped

### Requirement: The tests config SHALL name its modules explicitly rather than glob

The ags config's tests typecheck config SHALL list the modules under test
**explicitly**, not by directory glob, and SHALL NOT widen to `gi://*` or `ags/*`.

Rationale: `components/**/*.ts` would pull in `components/wifi/state.ts` (imports
`ags`) and `services/**/*.ts` would pull in five services importing `gi://*`.
A glob would drag GTK into the program and make the suite require the desktop
stack — which is what keeps `capture-typecheck` out of CI. The explicit list
means adding a module is the moment its author states that it is pure: the list
IS the purity contract.

#### Scenario: GTK is unreachable from the suite
- **WHEN** `tsc --noEmit` runs over the tests config
- **THEN** no module in its program imports `gi://` or `ags`

#### Scenario: A pure module is admitted by name
- **WHEN** a new pure module is added to the ags config
- **THEN** it is added to the config's `include` list by name, together with its
  tests

### Requirement: Battery presentation decisions SHALL live in a pure module

`dotfiles/config/ags/components/battery/presentation.ts` SHALL hold every battery
decision that does not need a live widget, and SHALL import no GTK, Gio, Gdk or
`ags` binding, perform no I/O, and hold no mutable module-level state.

It SHALL export exactly:

```ts
export type PowerProfileId =
  | "Powersave++" | "Powersave" | "Balanced" | "Performance" | "Performance++"

export const POWER_PROFILE_ORDER: readonly PowerProfileId[]

export interface BatteryTimePresentation {
  /** The large line, e.g. "2h 14m" */
  primary: string
  /** The line under it, e.g. "remaining" or "Charging" */
  sub: string
}

export function formatBatteryTime(seconds: number, charging: boolean): BatteryTimePresentation
export function formatDuration(seconds: number): string | null
export function profileIconVariant(id: PowerProfileId): string
export function isActiveProfile(current: string, candidate: PowerProfileId): boolean
```

plus the panel-facing percentage helpers and the rendered-duration bound.

#### Scenario: The module is pure
- **WHEN** `presentation.ts` is read
- **THEN** it contains no `gi://` import, no `ags` import, no file or process
  access, and no mutable module-level state

#### Scenario: The module is reachable from the test runner
- **WHEN** `make ags-test` runs
- **THEN** its decisions are exercised without GTK, Astal or a display

#### Scenario: The module deploys
- **WHEN** the compositor configuration role places its skeleton files
- **THEN** `dotfiles/config/ags/components/battery/presentation.ts` is among them,
  because placement is per-file and an unregistered source never deploys

### Requirement: An absent or implausible battery time SHALL render a state word, never a number

`formatBatteryTime` SHALL render the two lines as follows:

| input | charging | result |
|---|---|---|
| any usable `seconds` | `false` | `{ primary: "<duration>", sub: "remaining" }` |
| any usable `seconds` | `true` | `{ primary: "<duration>", sub: "full in" }` |
| `seconds <= 0`, or non-finite | `false` | `{ primary: "", sub: "Discharging" }` |
| `seconds <= 0`, or non-finite | `true` | `{ primary: "", sub: "Charging" }` |
| `seconds > 86400` | either | the same state-word fallback as above |

and `formatDuration` SHALL return `null` for `0`, for negatives, and for
non-finite input.

Rationale: "0m remaining" is a **lie** — it claims *no time left*, which is a
different and much more alarming claim than *no estimate*. The fallback keeps the
information and drops the number. The charging and discharging words differ
because a charge *target* is not a countdown. Their casing differs too: a
lowercase word tags a number, a capitalised word replaces one, so casing is the
panel's only cue that the number is missing.

#### Scenario: Discharging
- **WHEN** `formatBatteryTime(8040, false)` is called
- **THEN** it returns `{ primary: "2h 14m", sub: "remaining" }`

#### Scenario: Charging
- **WHEN** `formatBatteryTime(8040, true)` is called
- **THEN** it returns `{ primary: "2h 14m", sub: "full in" }`

#### Scenario: No estimate while discharging
- **WHEN** `formatBatteryTime(0, false)` or `formatBatteryTime(-1, false)` is called
- **THEN** it returns `{ primary: "", sub: "Discharging" }`, and never a primary of
  `"0m"`

#### Scenario: No estimate while charging
- **WHEN** `formatBatteryTime(0, true)` is called
- **THEN** it returns `{ primary: "", sub: "Charging" }`

#### Scenario: A non-finite estimate does not leak NaN
- **WHEN** `formatBatteryTime(NaN, false)` is called
- **THEN** it returns `{ primary: "", sub: "Discharging" }`, and the rendered text
  contains no `"NaN"`

#### Scenario: A sub-minute duration reads as minutes
- **WHEN** `formatDuration(59)` is called
- **THEN** it returns `"0m"`, not `"0h"`

#### Scenario: Whole hours drop the minute part
- **WHEN** `formatDuration(3600)` is called
- **THEN** it returns `"1h"`, not `"1h 0m"`

#### Scenario: formatDuration's null case
- **WHEN** `formatDuration` is called with `0`, a negative value, `NaN` or
  `Infinity`
- **THEN** it returns `null`

### Requirement: An implausible duration SHALL NOT be rendered as an ordinary number

`formatBatteryTime` SHALL treat any duration strictly greater than **24 hours
(86 400 s)** as an absent estimate, and render the state-word fallback rather than
the number. The bound is inclusive: exactly 24h is rendered.

Rationale: a value like "27h 3m" displayed as if it were ordinary reads as a bug
and destroys trust in the panel's other numbers. 24h is chosen because it is the
largest value a reader can interpret at a glance, the largest plausible real
remaining/charging time for a laptop battery, and a round number that will not be
mistaken for a measurement. Clamping to 24h instead of dropping the number was
rejected because it **displays a fabricated precise value** — the very thing the
branch exists to avoid. A visibly absent number degrades gracefully; a confidently
wrong one does not.

#### Scenario: Exactly 24h is rendered
- **WHEN** `formatBatteryTime(86400, false)` is called
- **THEN** it returns `{ primary: "24h", sub: "remaining" }`

#### Scenario: Above 24h the number is dropped
- **WHEN** `formatBatteryTime` is called with `86401`, `27 * 3600 + 180` or
  `400 * 3600`, charging or discharging
- **THEN** it returns the state-word fallback with an empty `primary`, and never
  `"27h 3m"`

#### Scenario: The bound is a single named constant
- **WHEN** the module is read
- **THEN** the 24h bound is exported as `MAX_RENDERED_SECONDS` rather than
  re-derived by any caller

### Requirement: Profile selection SHALL be explicit, ordered and frozen

`POWER_PROFILE_ORDER` SHALL be a hand-written, `Object.freeze`d tuple in
cheapest-to-hottest order, and `PowerProfileId` SHALL be derived from it rather
than restated alongside it.

Rationale: the row order is a **product decision**, not a property of the profile
names. `Object.keys` over the daemon's payload yields whatever order the daemon
happened to serialise, which is not a contract — it can change between daemon
versions and silently reshuffle the menu — and it makes rows disappear when a
profile is unavailable on the running machine. Deriving the type from the tuple
makes the two declarations unable to drift: adding a profile to the list and
forgetting a hand-written union would otherwise compile fine and break the
consumer's `switch`.

#### Scenario: The order is the declared one
- **WHEN** `POWER_PROFILE_ORDER` is read
- **THEN** it equals `["Powersave++", "Powersave", "Balanced", "Performance",
  "Performance++"]`

#### Scenario: The list is frozen and ordered
- **WHEN** the tests run
- **THEN** `Object.isFrozen(POWER_PROFILE_ORDER)` holds, and every cheaper
  profile's rank is lower than every hotter profile's

#### Scenario: The union is derived, not restated
- **WHEN** the module is read
- **THEN** `PowerProfileId` is defined as `(typeof POWER_PROFILE_ORDER)[number]`,
  so it cannot name a profile the list omits

### Requirement: A `++` power profile SHALL reuse the base profile's icon variant

`profileIconVariant` SHALL return the base profile's variant for both `++` tiers:
`Powersave++` → `powersave` and `Performance++` → `performance`.

Rationale: the daemon's `++` tiers are **not different modes**. They are the same
mode pushed further — a lower ceiling / a higher floor on the same governor.
There is no sixth or seventh meaning to draw, and a distinct glyph would claim a
distinction the system does not make, at the cost of two extra template
directories and two extra rendered outputs. The honest rendering is the base
glyph plus the `++` in the row's text. This is also why the manifest declares
exactly three variants.

#### Scenario: Base profiles map to their own glyph
- **WHEN** `profileIconVariant` is called with `Powersave`, `Balanced` or
  `Performance`
- **THEN** it returns `powersave`, `balanced` or `performance` respectively

#### Scenario: Both `++` tiers reuse the base variant
- **WHEN** `profileIconVariant("Powersave++")` and `profileIconVariant("Performance++")`
  are called
- **THEN** each returns exactly the base profile's variant

#### Scenario: Every profile resolves to a declared variant
- **WHEN** every id in `POWER_PROFILE_ORDER` is passed through `profileIconVariant`
- **THEN** every result is one of the three variants `icons.yaml` declares, so no
  profile can resolve to an unresolvable icon path

### Requirement: The active-profile match SHALL be case-insensitive and SHALL never fall back to a row

`isActiveProfile(current, candidate)` SHALL return `true` only when `current`
matches `candidate` ignoring case and surrounding whitespace, and SHALL return
`false` for every candidate when `current` is empty, blank, or unrecognised.

Rationale: the daemon's identifier and the label shown to the user differ in case
in practice, and a mismatch here is invisible-but-wrong — the row simply never
lights up, which reads as "the panel does not know what mode I am in" rather than
as a bug. A blank or unknown `current` matching nothing is the honest rendering;
highlighting the first row as a fallback would tell the user they are in
`Powersave++` when the daemon said something the panel did not recognise.

#### Scenario: Exact match
- **WHEN** `isActiveProfile(id, id)` is called for each id in `POWER_PROFILE_ORDER`
- **THEN** it returns `true`

#### Scenario: Case difference still matches
- **WHEN** `isActiveProfile("performance", "Performance")` or
  `isActiveProfile("PERFORMANCE", "Performance")` is called
- **THEN** it returns `true`

#### Scenario: Whitespace is tolerated
- **WHEN** `isActiveProfile("  Balanced  ", "Balanced")` is called
- **THEN** it returns `true`

#### Scenario: A prefix is not a match
- **WHEN** `isActiveProfile("Performance", "Performance++")` is called
- **THEN** it returns `false`, so the base profile cannot light up the `++` row

#### Scenario: An unknown current highlights nothing
- **WHEN** `isActiveProfile` is called with `current` of `""`, `"   "`,
  `"Turbo"` or any other unrecognised value, for every candidate
- **THEN** it returns `false` for every candidate, and no row is highlighted

#### Scenario: At most one row is ever highlighted
- **WHEN** the ordered list is filtered by `isActiveProfile` for any recognised
  `current`
- **THEN** exactly one row survives

### Requirement: A missing battery percentage SHALL be absent, not fabricated

`clampPercentage` SHALL round and clamp into `0..100` and SHALL return `null` for
`null`, `undefined`, and non-finite input. `formatPercentage` SHALL render
`"<n>%"` or `null` accordingly.

Rationale: the panel prints a percentage in two places — the nav header and the
profile rows — and a percentage rendered two ways is a rounding drift waiting to
happen, so the rounding and clamping happen once, in pure code. A daemon with no
capacity must not render `NaN%` or `-1%`; the caller shows a fallback word
instead, applying the same "degrade to a word, never to a fabricated number" rule
the time formatting uses.

#### Scenario: A reading is rounded and clamped
- **WHEN** `clampPercentage(83.4)`, `clampPercentage(83.5)`, `clampPercentage(-1)`
  and `clampPercentage(140)` are called
- **THEN** they return `83`, `84`, `0` and `100` respectively

#### Scenario: No reading is null, never NaN
- **WHEN** `clampPercentage` or `formatPercentage` is called with `null`,
  `undefined`, `NaN` or an infinity
- **THEN** it returns `null`, and no rendered text contains `NaN` or a negative
  percentage

#### Scenario: A reading renders with its sign
- **WHEN** `formatPercentage(83)` is called
- **THEN** it returns `"83%"`