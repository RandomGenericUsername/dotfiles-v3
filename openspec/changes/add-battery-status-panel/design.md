# Design — battery status panel (foundation + panel UI)

Two workstreams, one change. **A** is the foundation implemented here: icons, a
test harness, pure presentation logic. **B** is the panel UI, scoped below and
implemented by a second agent against the exact signatures in §5.

---

## 1. The split that makes the panel testable

The panel has two kinds of code and they must not be mixed:

| | lives in | testable by |
|---|---|---|
| **Decisions** — what to write, which glyph, which row is selected | `components/battery/presentation.ts` | `make ags-test`, no GTK |
| **Effects** — the D-Bus subscription, the window, the CSS classes | the widget | a live desktop, by hand |

`presentation.ts` imports nothing. No `gi://`, no `ags`, no I/O, no module-level
mutable state. That is not stylistic: it is the precondition for the file being
reachable from `node --test` at all, and it is enforced mechanically by the
tsconfig's **explicit** module list (§4).

The rule the second agent must follow: **if a thing can be answered from a
number alone, it belongs in `presentation.ts`.** If it needs a widget, it does
not. `formatBatteryTime(3600, false)` is a decision; "bind that to the label" is
an effect.

---

## 2. Icons

### 2.1 Geometry is sacred

The three owner-supplied SVGs are third-party art from three different sources
(svgrepo, a battery set, a car-front-end set). The only change made was the
**fill value**: every hardcoded near-black literal became
`{{COLOR_FOREGROUND}}`. Path data, `transform`, `fill-rule`, `clip-rule`, the
`viewBox`, and element order are byte-identical, and that is verified by masking
the fill value in both files and diffing — if geometry had drifted, the diff
would not be empty.

Two notes on the sources:

- **The sources were not uniformly `fill="black"`.** `powersave` has **three**
  `fill="black"` and **one** `fill="#0F0000"` (the battery outline). `#0F0000` is
  a near-black, not a palette token; ITR only substitutes recognised
  `{{PLACEHOLDER}}` values, so it would have stayed near-black and stayed
  invisible. All four were rewritten. Final counts: `powersave` 0 → 4
  placeholders, `balanced` 0 → 2, `performance` 0 → 3.
- **`viewBox="0 0 1024 1024"` is preserved** on all three (docs § 3.2). Note that
  the `powersave` art is not centred in that box — the leaf+outline sit
  left-of-centre — so it will read smaller than its box suggests next to the
  other two. That is the owner's art; cropping or re-centring it is a visible
  change to a third-party glyph and is not this change's call.

### 2.2 Why `power-mode` is NOT a bar group

`src/runtime/src/runtime/domain/icon_contrast.py:22-38` lists `BAR_GROUPS` — the
groups whose group-level `COLOR_FOREGROUND` / `COLOR_JOIN` the runtime may
retarget to the highest-contrast palette token **against the wallpaper's top
band** (~48px, sampled with Pillow, falling back to the palette background).

**`power-mode` is deliberately absent from that list, and adding it would break
the icons.** The reason:

- `power-mode` has **no bar consumer**. Its glyphs are drawn in the battery
  panel's power-mode list, whose rows sit on the **dark glass panel surface** —
  `alpha(@color_00, 0.94)` over a transparent window. That surface is dark by
  construction and does not change with the wallpaper.
- The guard's job is to keep a *bright* icon legible against an arbitrary
  wallpaper. Applied here it would pick the wallpaper's backdrop-losing token.
  On a light wallpaper that means retargeting a bright token against an
  already-dark panel surface — the exact wash-out the guard exists to prevent,
  just on the wrong side.
- Leaving the group out means `COLOR_FOREGROUND` resolves to the plain theme
  `foreground`, which is correct on dark glass. That is the outcome, not an
  accident.

**Contrast `battery`,** which *is* in `BAR_GROUPS`. `battery` renders in the
**status bar**, which is transparent and floats directly over the wallpaper — the
situation the guard was built for. `battery` and `power-mode` are both about the
battery, which is exactly why the distinction has to be written down rather than
assumed.

### 2.3 Why there are no `system-*` duplicates

`docs/Adding an Icon — ITR and Provisioning Pipeline.md` § 14 states a standing
rule: *"Any group consumed on dark glass MUST expose `system-*` copies from day
one."* This change **deviates from it, deliberately**, and the deviation is worth
being explicit about because it is a rule violation.

The rule exists for a specific mechanism: *one* `itr render` serves both the
transparent bar and dark-glass system surfaces, and the guard rewrites group-level
mappings for bar groups. A `system-*` variant carrying a **variant-level**
`COLOR_FOREGROUND` pin is *structurally* exempt — the guard's allowlist covers
group-level placeholders only (`icon_contrast.py:40-42`). So the `system-*` copy
exists to give a dark-glass consumer a pinned token in a manifest whose group
token the guard may rewrite.

**`power-mode` has no bar consumer, so there is nothing to be exempt from.** Its
group token is never rewritten because its *group* is not guarded. A
`system-power-mode-*.svg` per glyph would be a second render of identical art
that nothing resolves — a duplicate carrying a distinction this group does not
have.

This is recorded in the manifest's own comment block as well, so the reasoning
travels with the file and does not depend on this document being read.

### 2.4 Three glyphs for five profiles

`profileIconVariant` maps five profiles onto three variants. `Powersave++` and
`Performance++` reuse the base profile's glyph.

**Why:** the daemon's `++` tiers are not different modes — they are the same mode
pushed further (a lower ceiling / a higher floor on the same governor). There is
no sixth or seventh meaning to draw. A distinct glyph would claim a distinction
the system does not make, and it would cost two extra template directories and two
extra rendered outputs to do it. The honest rendering is the base glyph plus the
`++` in the row's **text**. A unit test pins this, and another pins that every
profile resolves to a variant the manifest actually declares — because a fourth
return value would be an unresolvable icon path at runtime.

The implementation normalises the suffix (`id.replace(/\+\+$/, "")`) rather than
switching on five literals, so a future `Powersave+++` needs no edit.

### 2.5 Regenerating `icons.json`

`dotfiles/config/ags/icons.json` is **generated output** and must not be
hand-edited. It is produced by `compositor_configs` as
`(from_yaml) | to_nice_json(indent=2)`. The regeneration here ran exactly that
expression (ansible's own `to_nice_json` filter from the provisioning venv), not
a `json.dumps` approximation — the two differ (separators, and ansible's profile
encoder), and approximating it is how a "regenerated" file silently diverges from
what provisioning writes.

**The regeneration also corrected pre-existing staleness, which the caller should
know about.** The committed `icons.json` was already out of sync with
`icons.yaml` before this change: four `settings-panel` variants
(`wifi-signal-full`, `wifi-signal-good`, `wifi-signal-medium`, `wifi-signal-low`)
were missing the `color_mappings` blocks their templates declare, and the
`info-caution` entry was in hand-written key order rather than sorted order. Both
`icons.yaml` and `icons.json` were last touched in `f161e246`, so this is
drift introduced within a single commit that did not regenerate. Regenerating
fixes it.

This is **inert at runtime**: `lib/icon-registry.ts` reads only `name`, `output`
and `bar_mappings` from the manifest, so no rendered icon changes. It matters
because the file is supposed to be a faithful projection of its source, and a
"generated" file that is not is worse than no file — it is a generated artefact
that silently disagrees with the contract it projects.

The `battery` group was verified **byte-identical** before and after.

### 2.6 The drift itself was a FINDING: no gate asserted `icons.json == to_nice_json(icons.yaml)`

The paragraph above records what the regeneration corrected. What matters more
is **why it went unnoticed**, and that is a hole in the gate set, not bad luck.

The committed `icons.json` had carried `null` for the `color_mappings` of
`wifi-signal-full`, `wifi-signal-good`, `wifi-signal-medium` and
`wifi-signal-low` — blocks their own templates declare in `icons.yaml` — since
`f161e246`, the single commit that touched both files and did not regenerate.
Between them:

- **No test asserts the projection.** `test_compositor_configs_role.py` pins the
  skeleton file *count* and enumerates sources, so it proves the file is
  *registered*; it never opens it. The ansible-execution variant asserts
  `icons.json` was *placed*, not that it was placed with the right contents.
- **No gate regenerates.** `contracts-check` is the event-contract drift gate;
  `capture-hexagonal-gate` is the capture-side structure gate; both mock-parity
  gates check `class=` tokens. None of them touches the icon manifest.
- **`icon-registry.ts` cannot notice.** It reads only `name`, `output` and
  `bar_mappings`, so the `null` was inert at runtime — the *type* of thing that
  gets left behind indefinitely precisely because nothing broke.

So the file was a generated artefact silently disagreeing with the contract it
projects, and the only thing that would ever have surfaced it was a human
noticing. **Decision: add the drift gate**, because the alternative (a note
telling people to regenerate) is a reminder, and reminders are what the status
quo already was.

`scripts/icons-json-drift.py` compares the committed `icons.json` against
`(from_yaml) | to_nice_json(indent=2)` — ansible's **own** filter, imported and
called, not a `json.dumps` reconstruction. The role emits through that filter,
so comparing against an approximation of the generator is exactly how a file
regenerated "the same way" ends up differing from what provisioning writes on the
next run; and the gate **fails** with that stated when ansible is unimportable
rather than falling back to a guess or skipping.

It is wired into `make gates`/`gates-ci` as `icons-json-drift` and into
`.github/workflows/gates.yml` as its own job (it needs `uv`, for the
provisioning venv that carries ansible-core and PyYAML — the same mechanism
`contracts-check` already uses).

**Negative-tested**, by perturbing a copy of `icons.json` back to exactly the
historical drift — `wifi-signal-full`'s `color_mappings` set to `null`:

```
FAIL: dotfiles/config/ags/icons.json has DRIFTED from .../icons.yaml.
--- dotfiles/config/ags/icons.json (committed)
+++ dotfiles/config/ags/icons.json (regenerated from .../icons.yaml)
@@ -649,7 +649,10 @@
-        "color_mappings": null,
+        "color_mappings": {
+          "COLOR_BACKGROUND": "color12",
+          "COLOR_FOREGROUND": "color0"
+        },
EXIT=1
```

A gate that has never been seen to fail is not a gate, so both this gate and the
battery mock-parity gate below are reported with their failing runs as well as
their passing ones.

---

## 3. Where the test harness lives, and why there

```
dotfiles/config/ags/tests/
├── tsconfig.tests.json          # typechecks the TESTS
└── ts/
    ├── resolve-hooks.mjs        # extensionless-relative-import hook
    ├── resolve-hooks.test.ts    # the hook's own self-test
    ├── fixtures/
    │   └── extensions-fixture.ts
    └── battery-presentation.test.ts
```

**Why inside `dotfiles/config/ags/`** and not somewhere neutral like a
top-level `tests/`: the tests import the modules under test by relative path, and
a test tree that sits outside the tree it tests is a second place to update when
a file moves. Mirroring the capture tool's `capture-tool/tests/ts/` shape keeps
one layout for both harnesses in the repo.

**Why `tests/` is safe inside the deployed tree.** `compositor_configs` places
files **per-file** from `compositor_configs_skeleton_files`; nothing in
`dotfiles/config/ags/tests/` is registered, so nothing there deploys. That is the
same property that makes `gui_tools`' per-file placement safe, and it is asserted
by check 5 of the hexagonal gate for the capture side. The explicit
`config_dirs` ensure is likewise untouched.

**Why the module list in the tsconfig is explicit rather than a glob.** This is
the load-bearing decision, and it is what makes the suite runnable in CI:

| glob | would pull in | compiles? |
|---|---|---|
| `components/**/*.ts` | `components/wifi/state.ts` (imports `ags`) | ✗ |
| `services/**/*.ts` | `wifi-service.ts`, `nm-client.ts`, `speedtest-service.ts`, `bluetooth-service.ts`, `mpris-service.ts` (all `gi://*`) | ✗ |

A glob would drag GTK into the program and the suite would need the desktop
stack — which is exactly what keeps `capture-typecheck` out of CI. The explicit
list means **adding a module to it is the moment its author states in the repo
that it is pure.** The list *is* the purity contract. (`services/mpris-core.ts`
is listed because it is the one genuinely pure module there today.)

### 3.1 Dependency declaration

`ags-test-deps` copies `capture-test-deps`' shape exactly:

- `npm install --no-save --no-package-lock typescript@5.9` at the repo root,
  guarded on `node_modules/.bin/tsc` so a present package skips the network;
- `npm install --no-save --no-package-lock --prefix dotfiles/config/ags/tests
  @types/node@24`, guarded on the directory.

Two placement facts, both learned the hard way elsewhere in this repo:

- **`--prefix` is load-bearing.** `npm install --no-save X` at the repo root
  *removes* previously `--no-save`'d packages. Without a separate prefix project,
  installing `@types/node` would prune `typescript` — which is how a previous
  measurement in this repo's history turned into a false green.
- **`@types/node` must be a SIBLING of `tsconfig.tests.json`, not a child.**
  tsc's default `typeRoots` walk starts at the config's own directory and walks
  **up**. `tests/node_modules/@types` is found; `tests/ts/node_modules/@types` is
  one level too deep and yields `TS2688: Cannot find type definition file for
  'node'`. (This was the first failure of this workstream's own build.) It also
  must not sit at the repo root or at `dotfiles/config/ags/`, or a future app
  tsconfig's upward walk would find it and silently widen the app's ambient
  surface — the hazard `.gitignore`'s existing note on the capture tool's copy
  already documents for that side.

### 3.2 No silent skips

`ags-test` **fails** — never skips — when `node`, `npx`, `node_modules/.bin/tsc`
or the installed `@types/node` is missing, checked explicitly after
`ags-test-deps`. A test gate that skips when its toolchain is missing is
indistinguishable in CI output from one that passes, and that is how a suite
silently stops running. This is also why `ags-test` is **not** filtered out of
`gates-ci`, unlike `capture-typecheck`: it needs Node and tsc and nothing else.

### 3.3 The resolve hook is tested

`resolve-hooks.mjs` teaches `node --test` the one thing `ags bundle` already does
— append `.ts` to a relative specifier that misses — so app-side sources keep
idiomatic extensionless imports and the workaround lives in test-only
infrastructure. Test-only infrastructure nothing exercises is infrastructure
that stops working silently after an unrelated refactor, with the failure
pointing at the battery panel instead of at the hook.

So `resolve-hooks.test.ts` imports a real fixture **without** a suffix and
asserts it resolves. Two assertions, both load-bearing: if the hook regresses,
the test file fails to *load*, which is the loudest possible signal.

---

## 4. The pure presentation logic

Signatures are fixed — a second agent codes the panel against them, so they are
not to be renamed or reshaped.

```ts
export type PowerProfileId =
  | "Powersave++" | "Powersave" | "Balanced" | "Performance" | "Performance++"

export const POWER_PROFILE_ORDER: readonly PowerProfileId[]
export interface BatteryTimePresentation { primary: string; sub: string }
export function formatBatteryTime(seconds: number, charging: boolean): BatteryTimePresentation
export function formatDuration(seconds: number): string | null
export function profileIconVariant(id: PowerProfileId): string
export function isActiveProfile(current: string, candidate: PowerProfileId): boolean
```

Plus, on the caller's request scope, two percentage helpers for the nav header
(§5).

### 4.1 Why the profile list is an explicit ordered array

`POWER_PROFILE_ORDER` is a hand-written `Object.freeze`d tuple, **not** derived
from `Object.keys` of anything:

- **Row order is a product decision** (cheapest first, hottest last), not a
  property of the profile names. `Object.keys` yields whatever order the daemon's
  D-Bus/NMI payload serialised, and that order is not a contract — it can change
  between daemon versions and silently reshuffle the menu.
- **The list is stable even when a profile is unavailable** on the running
  machine, so rows do not jump.
- `Object.freeze` + `as const` means the panel reading it at module scope cannot
  mutate it, and `PowerProfileId` is *derived* from the tuple rather than
  restated. A hand-written union beside a hand-written list is two declarations
  that drift: adding a profile to the list and forgetting the union compiles fine
  and breaks the consumer's `switch`. Deriving it makes the omission a compile
  error.

A unit test asserts `Object.isFrozen` and the cheap-to-hot ordering, so "this is
a deliberate order" is a checked property rather than a comment.

### 4.2 Why `formatDuration` returns `string | null`

Because the daemon reports no time at all in real situations (capacity unknown,
estimation unsupported) and **"0m remaining" is a lie**: it says *no time left*,
which is a different and much more alarming claim than *no estimate*. Returning
`null` hands the decision back to the caller, which shows the state word instead.

The finiteness guard is separate and deliberate: `NaN <= 0` is `false`, so
without `Number.isFinite` a `NaN` estimate flows into `Math.floor` and renders
`"NaNh NaNm"`.

Sub-hour renders as minutes (`59 → "0m"`), not `"0h"`; hours-only when the
minutes are zero (`3600 → "1h"`, because a trailing `"0m"` implies a precision
the value does not have).

### 4.3 Why the charging and discharging words differ

The `sub` word is what makes the number mean something. `2h 14m remaining` while
plugged in is actively misleading — a charge **target** is not a countdown. So
`charging → "full in"` and `discharging → "remaining"`.

The **casing** difference is also load-bearing and is pinned by a test: a
lowercase word *tags a number*, a capitalised word *is* the number's
replacement. If those ever converge, the panel has lost its only cue that the
number is missing.

### 4.4 The >24h bound

**Bound: 24h (86 400 s), inclusive.** Anything strictly above it is treated as
"the daemon is estimating badly" and degrades to the same no-number fallback as
`seconds <= 0`.

Why 24h specifically:

- it is the **largest value a reader can still interpret at a glance**;
- it is the **largest plausible real remaining/charging time** for a laptop
  battery, so it does not clamp anything the user would believe;
- it is a **round number**, so `24h` is not mistaken for a precise measurement.

Why *drop the number* rather than clamp to 24h: clamping **displays a
fabricated precise value**, which is precisely the thing the branch exists to
avoid. A visibly absent number degrades gracefully; a confidently wrong one does
not.

Why inclusive: 24h is itself the largest interpretable value, so it is shown.

The state word plus the percentage carries the information in the fallback case.

---

## 5. What the panel consumes (workstream B contract)

Fixed, and **not** to be renamed or reshaped:

```ts
export const POWER_PROFILE_ORDER: readonly PowerProfileId[]
export function formatBatteryTime(seconds: number, charging: boolean): BatteryTimePresentation
export function formatDuration(seconds: number): string | null
export function profileIconVariant(id: PowerProfileId): string
export function isActiveProfile(current: string, candidate: PowerProfileId): boolean
```

Extras, available if the panel needs them:

| export | for |
|---|---|
| `MAX_RENDERED_SECONDS` | the 24h bound, so the widget never re-derives it |
| `clampPercentage(p: number \| null \| undefined): number \| null` | rounds and clamps to 0..100; `null` for no reading |
| `formatPercentage(p: number \| null \| undefined): string \| null` | `"83%"`, or `null` for "no reading" |
| `formatBatteryStatusLine(s: number, charging: boolean): string` | the ONE-line form for a caller with a single line (`"2h 14m remaining"`, `"full in 2h 14m"`, `"Discharging"`), derived from `formatBatteryTime`. Added during review: the bar tooltip had been choosing the state word and the word ORDER itself, which is the same fact rendered twice — the way a tooltip ends up saying "charging" where the panel says "Charging", or printing "0m remaining" for a missing estimate |

**Percentage: exposed, and deliberately two functions rather than one.** The panel
prints a percentage in **two** places (nav header and profile rows), and a
percentage rendered two ways is a rounding drift waiting to happen. These round
and clamp once for both callers. `clampPercentage` reports a missing reading as
`null` so a daemon with no capacity cannot render `NaN%` — the same "degrade to a
word, never to a fabricated number" rule as §4.2.

Icon resolution stays with the existing seam: `registry.resolve("power-mode",
profileIconVariant(id))`.

---

## 6. Workstream B — panel UI

Scoped so the change reads as one coherent piece. **Implemented**; the status
below is the as-built record, updated from the original proposal by the
reviewing agent that verified it.

- [x] Battery status panel widget + the two popup windows
      (`components/battery/{state,battery-icon,BatteryPopup,BatteryContent}`).
- [x] `style.css` rules for the panel, reusing `.settings-net` (+ `.sel`) for
      the rows. The former `.power-profile-item` / `.power-profile-item.active`
      rules are **deleted, not relocated** — they styled the `<popover>` this
      change removes, so keeping them would be dead CSS that still reads as if
      the popover existed.
- [x] `app.tsx` window registration (catcher first, popup above it — the same
      ordering rule the Wi-Fi popup uses) and `bar/widgets/battery.tsx`
      integration: LEFT opens the panel, RIGHT launches `power-options-gtk`.
- [x] Registered the five widget files + `services/power-service.ts` in
      `compositor_configs_skeleton_files` and pinned the count at **71** in
      `src/provisioning/tests/unit/test_compositor_configs_role.py`, in both the
      enumeration and the ansible-execution variant. The exact-count pin stays
      exact: placement is per-file, so an unregistered file deploys nothing, and
      converting the assertion to `>=` or a subset check would convert that
      silence into a pass.
- [x] `components/battery/battery-icon.ts` added to
      `dotfiles/config/ags/tests/tsconfig.tests.json`'s explicit `include` list
      **by name** — that edit is the statement that the module is pure.
- [x] Mock parity for the panel: `battery-popup-mockup.html` +
      `scripts/battery-mock-parity.py` (§7).

**Do not** add `power-mode` to `BAR_GROUPS` (§2.2) or create `system-*`
variants (§2.3).

---

## 7. The battery panel's own mock-parity gate

`scripts/wifi-mock-parity.py` proves the Wi-Fi mock against the Wi-Fi code, and
it cannot say anything about the battery panel: the two share `style.css` and
the `settings-*` vocabulary, but the panel's claims live in files that gate does
not map. So the panel gets its **own** harness, modeled line-for-line on the Wi-Fi
one (same ANCHORS / STATE_TSX / ALLOWLIST / CLASS_MAP / KNOWN_GAPS tables, same
CSS resolution, same report shape, same exit codes) rather than another anchor
in the existing one — extending that harness would either widen its STATE_TSX to
files it has no business knowing, or leave the panel ungated.

`battery-popup-mockup.html` carries six anchored states: discharging with an
estimate, charging (a charge target, not a countdown), the no-estimate
fallback, the daemon-absent state, a `++` tier selected, and the bar indicator
with the anchoring rule spelled out.

Three additions over the Wi-Fi harness, each forced by something the Wi-Fi mock
does not have:

- **PSEUDO_STATES** — the mock's `dim` modifier is
  `.battery-profile:disabled` in the shipped CSS, gated by
  `sensitive={powerReady}`. Resolved by requiring the exact selector text, so a
  renamed rule still fails.
- **PROMISES** — some mock classes are backed by a *call*, not a selector. The
  load-bearing one is `++`: the mock promises the tier rows reuse the base
  profile's glyph and carry `++` as tinted text, and the gate asserts the
  `profileIconVariant` regex **and** the separate `battery-profile-tier` label
  literal are both still there. A PROMISES entry is a LIST, because one token
  can carry more than one promise — and the branches are additive rather than
  exclusive, since an exclusive CLASS_MAP branch swallows the literal check and
  the gate stays green against exactly the regression the promise exists to
  catch. That was measured, not reasoned about: the exclusive version passed
  against a `presentation.ts` whose `++` stripping had been deleted.
- **Compound selectors** (`.settings-net.battery-profile`), lifted from
  `speedtest-mock-parity.py`, so a mapping can name both the row chrome and this
  panel's tighter metrics and be held to both.

**Negative-tested** in three ways, each on a perturbed copy: an extra mock class
with no CSS rule (FAIL, exit 1), the `++`-stripping regex removed (FAIL, exit 1),
and `.battery-profile:disabled` deleted from `style.css` (FAIL, exit 1). Passing
output: 6 states, 110 tokens checked, 19 scaffolding skipped, 0 known gaps.

**KNOWN_GAPS is empty, and that is the claim the negative runs support.** A
parity gate that passes because nothing matched is worse than no gate.

---

## 8. What was verified statically, and what needs a human

This change was reviewed on a **single monitor with no input injection** (no
`ydotool`/`wtype`/`xdotool`), where `ags bundle` transpiles but does not
typecheck and the popup is `visible={false}` until something opens it.

Validated statically, mechanically:

- every pure decision through `make ags-test` (37 assertions, 0 type errors);
- the mock/code parity of every class the panel draws, via the new gate;
- the anchoring code is textually the same construction as
  `bar/widgets/network.tsx` (motion controller that records x and claims no
  clicks) and the same clamp as `WifiPopup.tsx:42-48` — **not** that it lands
  in the right place on screen;
- the generated `icons.json` equals what the role would write (§2.6).

Needs a human, with the bar open: the actual click paths, the panel's anchor
position, and whether the panel stacks above its catcher. A **pixel comparison
is unsound for this panel** and is deliberately not quoted as evidence: it is
translucent over live desktop content, and a previous effort measured the same
panel at 0.644 before a change and 0.054 after — a 12x "difference" that was
entirely the wallpaper.