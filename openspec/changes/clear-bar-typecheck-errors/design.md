# Design: clear-bar-typecheck-errors

## §1 The mechanism, measured

Reproduction is one command, and it is the gate itself:

```bash
npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json
```

At HEAD (`3b283830`) this reports **48 errors in our own tree** plus 29 tolerated
third-party ones under `/usr/share/ags/js`. Grouped by file:

| file | n | category |
|---|---|---|
| `app.tsx` | 11 | **B** |
| `audio/AudioPopup.tsx` | 5 | D |
| `bar/widgets/battery.tsx` | 5 | **C** |
| `tests/ts/battery-presentation.test.ts` | 3 | **A** |
| `tests/ts/battery-icon.test.ts` | 3 | **A** |
| `services/wifi-service.ts` | 3 | E |
| `components/battery/BatteryContent.tsx` | 3 | C/D |
| `tests/ts/resolve-hooks.test.ts` | 2 | **A** |
| `components/wifi/WifiContent.tsx` | 2 | D |
| `components/sliders/VolumeSlider.tsx` | 2 | **C** |
| `bar/widgets/workspaces.tsx` | 2 | **C** |
| `bar/widgets/tray.tsx` | 2 | D |
| `services/nm-client.ts` | 1 | E |
| `services/mpris-service.ts` | 1 | E |
| `lib/status-notifier.ts` | 1 | E |
| `bar/widgets/recording.tsx` | 1 | D |
| `audio/state.ts` | 1 | D |

By code: `TS2345` ×15, `TS2769` ×9, `TS2322` ×8, `TS2307` ×6, `TS2571` ×3,
`TS5097` ×2, `TS18047` ×2, `TS2786` ×1, `TS2739` ×1, `TS2339` ×1.

### Correction to the reported count

The defect was reported as "35 pre-existing errors". It is **48** at HEAD. The
report predates the `master` merge; master added the battery panel, whose files
carry 13 of the 48 (`bar/widgets/battery.tsx`, `components/battery/*`, and the
two battery test files). The figure is recorded so nobody re-derives it.

---

## §2 The categories, and which are single-cause

### A — the bar config sweeps in `tests/` (8 errors)

`tsconfig.bar.json` includes `"**/*.ts"`, which pulls in
`dotfiles/config/ags/tests/ts/*.test.ts`. Those files need `@types/node`
(`node:test`, `node:assert/strict` → 6 × `TS2307`) and
`allowImportingTsExtensions` (2 × `TS5097`), neither of which belongs in an app
config.

They are **already correctly gated** by `make ags-test`, which typechecks them
against `tests/tsconfig.tests.json` — a config that deliberately declares
`"types": ["node"]` and `allowImportingTsExtensions`, and deliberately does
**not** widen to `gi://*` or `ags/*` so the suite stays runnable without the
desktop stack.

So these 8 are not pre-existing errors at all. They are the bar config
over-reaching into a directory another config owns. **Fix: exclude `tests/`.**

This is the same class as `harden-capture-typecheck-config`: the config's
coverage was not a property of what it is supposed to check.

### B — `app.add_window` element type (11 errors, one file)

Every one of the 11 is the same shape:

```
app.tsx(66,22): error TS2345: Argument of type 'Object' is not assignable to parameter of type 'Window'.
```

`app.tsx:64-86` registers twelve windows:

```ts
app.add_window(Bar(monitor))
app.add_window(SettingsCatcher(primary))
...
```

Each `Foo(primary)` is a JSX element, which gnim types as `Object`; AGS's
`add_window` is typed to take a `Gtk.Window`. The runtime is fine — these *are*
`Gtk.Window` instances; only the static type is wrong.

**Fix: one typed helper** (or a single cast at each call, but eleven casts is the
same fix written eleven times). One root cause, one edit, 11 errors gone.

### C — `createBinding` property casing (≈11 errors)

```
bar/widgets/battery.tsx(38,19): error TS2769: No overload matches this call.
  Argument of type '"is-present"' is not assignable to parameter of type
  '"notify" | ... | "get_device_type_icon"'.
```

`createBinding` is declared:

```ts
export function createBinding<T extends GObject.Object, P extends keyof T>(
    object: T,
    property: PropKey<P>,
): Accessor<T[P]>
```

so the property must be a literal `keyof T`. The generated GIR types declare
**snake_case and camelCase** accessors — `get is_present()`, `get isPresent()` —
but **not** the kebab-case GObject property name `is-present` that the code
passes. `keyof Device` therefore rejects it.

Measured, the runtime normalises anyway (`gnim/dist/jsx/state.ts:563`):

```ts
const prop = kebabify(key) as keyof typeof object
// ...
const getter = `get_${prop.replaceAll("-", "_")}` as keyof typeof object
```

So `createBinding(device, "isPresent")` is `kebabify`-equivalent to
`"is-present"`, and the declared getter is `get_is_present` either way. The
camelCase spelling is **behaviour-identical and type-correct**.

**Fix: use the declared casing at the call sites.** No wrapper, no suppression —
the code was simply using a name the types do not offer and the runtime did not
need.

> Verify per call site that the camelCase name is genuinely the same property.
> `kebabify` lowercases and splits on case boundaries and dashes, so
> `isPresent` → `is-present`, `timeToFull` → `time-to-full`,
> `focusedWorkspace` → `focused-workspace`. All three round-trip. A name that
> does *not* round-trip would be a real bug and is not assumed away.

### D — gnim JSX prop / `Accessor` typing (≈12 errors) — MEASURED, NOT A HYPOTHESIS

**The "downstream of C" hypothesis held only for the errors it named, and did
NOT hold for the category.** After C was fixed and the tree re-measured
(tasks 5), the residue was **15**, not the ~18 the staging guessed, and the
D/E split was **9 D / 6 E**:

| file | n | what |
|---|---|---|
| `audio/AudioPopup.tsx` | 5 | 1 × `Accessor<string>` into a `string` prop; 4 × `createBinding(stream: unknown, …)` |
| `components/wifi/WifiContent.tsx` | 2 | `SignalIcon` returns `null`, and gnim's `JSX.Element` has no null member |
| `audio/state.ts` | 1 | `allNodes: Accessor<unknown[]>` but the binding is `Node[] \| null` |
| `bar/widgets/recording.tsx` | 1 | reactive `tooltipText` whose value is legitimately `null` |
| `services/wifi-service.ts` | 3 | E |
| `services/nm-client.ts` | 1 | E |
| `services/mpris-service.ts` | 1 | E |
| `lib/status-notifier.ts` | 1 | E |

What actually dissolved with C:

- Every error the hypothesis cited **inside a C file** — `battery.tsx(62,7)`,
  `BatteryContent.tsx(72,21)`, `workspaces.tsx(16,49)` — was the collapsed
  `createBinding` return type, and all three vanished when C did.
- `tray.tsx(68,22)` was **not D at all**: it was the same kebab literal, and
  `tray.tsx` belonged in C. Its downstream error went with it.

What did not:

- The nine D errors above live in files that had **no C error to begin with**.
  They were never downstream of anything; the hypothesis was true of the
  union-collapse signature and false as a general claim about the category.
  This is recorded because the staging was built on the stronger version.


### E — genuine null/unknown safety (6 errors)

```
services/nm-client.ts(103,19): error TS18047: 'connection' is possibly 'null'.
services/mpris-service.ts(400,19): error TS18047: 'connection' is possibly 'null'.
services/wifi-service.ts(581,15): error TS2571: Object is of type 'unknown'.
services/wifi-service.ts(649,19): error TS2571: Object is of type 'unknown'.
services/wifi-service.ts(786,15): error TS2571: Object is of type 'unknown'.
lib/status-notifier.ts(82,11): error TS2739: ... missing ... parameter_type, parameterType, state, ...
```

These are not noise. `connection` is a `Gio.DBusConnection | null` that the code
dereferences after a null check the compiler cannot see through; the
`recursiveUnpack()[0] as string[]` casts are asserted rather than checked. They
are fixed as defects — a guard, a narrowed local, or an explicit assertion with a
comment saying why it is safe — never with `as any` to silence the gate.

---

## §3 The options

### Option A — tolerate permanently, with an owner and a count (rejected)

Keep the `NOTE:` block, and treat the count as a ratchet.

Rejected because it is what we have now, and it has already failed: the list grew
from 35 to 48 across one merge and nothing objected. A tolerance list without an
expiry is a slow-motion `KNOWN_GAPS` with no task column.

### Option B — clear the tree, then make the gate strict (**chosen**)

Fix A/B/C, re-measure, fix the residue, then delete the tolerance so
`bar-typecheck` fails on any error in `dotfiles/config/ags/`.

This is the posture `capture-typecheck` already has, and it is the reason that
gate is useful: *"Zero tolerance for `src/gui-tools/capture-tool/`"*.

### Option C — fix only A/B/C and leave the rest tolerated (rejected)

Tempting, since A/B/C are ~30 of 48 for three edits. Rejected because it leaves
the gate's pass/fail line still meaningless for the bar tree, which is the defect
being fixed. A gate that reports 18 errors and exits 0 trains you to ignore it.

---

## §4 Why staged, and what "re-measure" means

The stage boundary is not cosmetic. Category D is the one place where the count
is expected to move on its own, and the size of the remaining work is unknown
until C is fixed. Committing to a D scope now would be inventing one.

Each stage ends with:

```bash
npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json \
  | grep -E "^dotfiles/config/ags/" | tee /tmp/bar-errors.txt
```

and the delta against §1's table is recorded in the task, in the style
`harden-capture-typecheck-config` used when it corrected its own reported blast
radius.

## §5 Out of scope (recorded, not fixed)

- **The 29 tolerated `/usr/share/ags/js` errors.** Third-party, tolerated by
  location, exactly as `capture-typecheck` does. Not ours.
- **`gi://AstalApps`, `gi://AstalBluetooth`, `gi://AstalMpris`,
  `gi://AstalPowerProfiles` unresolved.** Four typelibs are not installed on this
  machine, so `/usr/share/ags/js/lib/overrides.ts` cannot type its own imports.
  These surface as *tolerated* third-party `TS2307`s. Investigated and found
  **not** to be the cause of any of our 48 — `overrides.ts` patches prototypes at
  runtime, it does not augment the property types our errors depend on. Recorded
  so the next reader does not chase it.
- **`TS5097` / `allowImportingTsExtensions` for the tests.** Correct where it is
  (`tests/tsconfig.tests.json`); this change stops the app config from
  inheriting it, and changes nothing about the tests.
- **Widening `bar-typecheck` to the whole repo.** It covers
  `dotfiles/config/ags`. The capture tool, the gui-tools, and the runtime are
  other configs' business.

## §6 Scope boundaries

This change touches **no runtime behaviour**. Every fix is a type-level
correction — a config's `exclude`, a helper's signature, a property's spelling
(proven behaviour-identical by `kebabify`), or a guard that makes an existing
assumption checkable. The one place a fix *could* change behaviour is category E,
where a guard may reveal a path that was previously dereferencing a null; those
are handled as defects, individually, with the reviewer's attention.
