# Design: harden-capture-typecheck-config

## §1 The mechanism, measured

With no `types` and no `typeRoots`, TypeScript's default `typeRoots` is every
`node_modules/@types` directory from the config's directory **upwards**. It
auto-includes all of it.

The two configs that matter are separate projects:

| config | runs | needs Node types? | declares |
|---|---|---|---|
| `tsconfig.capture.json` | the GJS app | **no** | nothing (the defect) |
| `tests/tsconfig.tests.json` | `node --test` domain unit tests | **yes** (`node:test`) | `"types": ["node"]` |

The tests config is already correct and **robust in both layouts** — verified by
moving `@types/node` between `tests/node_modules/@types/` and the repo root, and
typechecking clean (exit 0) in each. `"types": ["node"]` names what it wants, and
the default walk finds it wherever it is. So §3 below changes nothing there.

The app config had no such statement, so its surface was decided by the walk.

### The leak is real

`@types/node` placed where the walk reaches it joins the app program in full:

```
$ tsc --noEmit -p tsconfig.capture.json --listFiles | grep -c '@types/node'
83
```

83 of its files, and a probe proves the globals land in GJS scope (`process.env`
types as `string | undefined` instead of erroring as unknown).

### The blast radius is a phantom

The reported "~96 errors in files nobody touched" does not reproduce. Across four
arrangements the error count never moves off 28 total / **0** in
`src/gui-tools/capture-tool/`:

| arrangement | total | in capture-tool |
|---|---|---|
| as committed (`tests/node_modules/@types/node`) | 28 | 0 |
| `capture-tool/node_modules/@types/node` | 28 | 0 |
| repo-root `node_modules/@types/node` (v26.6.4) | 28 | 0 |
| repo-root `node_modules/@types/node` (v20.19.43) | 28 | 0 |

The error sets are byte-identical; all 28 are pre-existing `/usr/share/ags/js`
errors already tolerated by the `capture-typecheck` target's `thirdparty` grep.

A JSX probe was also checked directly, since "gnim JSX element types widen" was the
specific claim:

```tsx
import type Gtk from "gi://Gtk?version=4.0"
export const f = () => <box orientation={1} />
```

Clean in both directions. gnim declares `JSX.Element = GObject.Object` directly
(`dist/jsx/jsx.ts:354`), not structurally, so `@types/node` has nothing to widen.
`skipLibCheck: true` also suppresses any of the 83 files' own internal errors.

**Conclusion: the leak is real and worth closing; the collapse was not real.** The
defect is "typecheck correctness contingent on a gitignored directory", not "the
gate is on fire".

> A measurement trap worth recording: `npm install --no-save X` **prunes** previously
> `--no-save`-installed packages. During this investigation an `npm install
> @types/node@20` silently removed `typescript`, and the subsequent `npx tsc` printed
> "This is not the tsc command you are looking for" and exited **1** — which a naive
> `grep -c 'error TS'` reads as **0 errors**. One of the intermediate measurements
> above was a false green for exactly this reason. Install both in a single command,
> and always confirm the compiler identity (`tsc --version`) before trusting a count.

## §2 What "the phantom" means for scope

The mechanism was worth establishing, and it established a real but *smaller*
finding than described. Two consequences:

1. The fix is **cheap and correct on its own merits** — `"types": []` is one line
   and states an intent that was previously implicit. Still worth landing.
2. The urgency framing ("the typecheck collapses") is **withdrawn**. Nothing here is
   a fire, and the config comment says so explicitly so a future reader does not
   re-derive the panic or "reproduce" it a fourth time.

## §3 The options

### Option A — `"types": []` on the app config (**chosen**)

States the intent directly: the GJS app has no ambient Node types. Independent of
disk layout by construction, not by accident.

- Breaks: nothing. The app has zero references to `process`/`Buffer`/`require`
  (verified by typechecking clean both with and without `@types/node` reachable).
- Cost: if a genuine global type is ever needed, someone must name it in `types`
  and justify it — a deliberate step rather than an ambient accident.

### Option B — explicit `typeRoots` on the app config

Point `typeRoots` at a directory with no `@types` packages. Also layout-independent,
but it *encodes the fix as a directory pointer* rather than as an intent. It is
strictly weaker than A: it says "look here (and find nothing)" rather than "look
nowhere". If anything is ever installed into that directory the pin silently
degrades, and the config's own comment would have to explain an empty path.

### Option C — add `typeRoots` to the tests config too

Unnecessary. The tests config already names `"types": ["node"]` and was verified
clean with the package in **either** location. Adding a `typeRoots` would only
narrow where the tests may find it.

### Option D — move `@types/node` deliberately and document the invariant

Treats the current arrangement as the design. Rejected: the arrangement is
gitignored, nobody reviews it, and the invariant ("do not install `@types` anything
the walk reaches") is invisible at the point where it would be violated. It also
leaves the app's surface wrong-in-principle rather than right.

### Option E — do nothing, since the blast radius was a phantom

Rejected. "Nothing broke yet" is a statement about today's `@types/node` contents,
not about the config. The gate's job is to be trustworthy without an audit.

## §4 The regression test

`tests/ts/typecheck-config.test.ts`, 4 cases. Three static assertions that hold
whether or not TypeScript is installed, and one that measures the real compiler.

| # | asserts | bites when |
|---|---|---|
| 1 | `compilerOptions.types` exists **and** is `[]` | the pin is deleted or made non-empty |
| 2 | `types` omits `node`; `typeRoots` unset | node is named, or the walk is reopened |
| 3 | tests config keeps `"types": ["node"]` | the fix was made by deleting node types from the world |
| 4 | `tsc --listFiles` reports **zero** `@types/node` files in the app program | the surface widens for any reason the static checks missed |

Case 4 is the real evidence: it asks the compiler what the config actually admitted,
rather than re-deriving `typeRoots` resolution in JS — which would reimplement the
very walk whose behaviour is in question. It replicates the Makefile's tolerance for
the 28 third-party errors (asserting zero errors *under `capture-tool/`* and that
`tsc` exited 0 or 2) rather than inventing a stricter rule, and it `t.skip`s with a
console note when TypeScript is absent, matching `capture-test`'s existing behaviour.

The configs are JSONC (a `"//"` rationale key plus inline comments), so the test
carries a string-aware comment stripper — a naive regex strip would eat the file at
the `"//"` key.

**Negative-tested.** With the pin removed and `@types/node` moved to the repo root,
3 of 4 fail, including case 4 naming the exact leak:

```
✖ app config pins its ambient-type surface to empty
✖ app config does not name node, and does not widen typeRoots
✔ tests config still asks for node types by name
✖ app program contains no @types/node files (real compiler evidence)
  AssertionError: @types/node leaked into the GJS app program (83 files).
```

With the pin **present** and `@types/node` relocated, all 4 pass — which is the
property being bought: the arrangement stopped mattering.

## §5 Out of scope (recorded, not fixed)

Two observations surfaced while reading these files. Neither is a typecheck concern,
neither was touched, and both are recorded so they are not lost:

1. **`app.tsx` reads `get_monitors()` once, at setup, with no hotplug handler.**
   `src/gui-tools/capture-tool/app.tsx:51` — `for (const monitor of
   app.get_monitors())` runs inside `main()`. Plugging in or removing a monitor
   after launch adds or drops no window. GTK/GdkMonitor carries a
   `monitor-added`/`monitor-removed` signal pair that this does not connect.
2. **`hypr-pano` has the identical pattern.**
   `src/gui-tools/hypr-pano/app.tsx:12` is the same one-shot
   `for (const monitor of app.get_monitors())` with no hotplug subscription. If one
   is fixed, the other should be, or they will diverge.

Both are behavioural changes to window lifecycle, well outside "pin a
typecheck config", and both deserve their own change with their own design.

## §6 Scope boundaries

| path | touched | why |
|---|---|---|
| `tsconfig.capture.json` | **yes** (`types: []` + rationale) | the pin |
| `tests/tsconfig.tests.json` | no | already correct and layout-robust in both directions, verified |
| `@types/node` location | no | untracked, gitignored, and now irrelevant to the app |
| `/usr/share/ags/js` third-party errors | no | pre-existing, already tolerated by the gate |
| runtime code, CSS, window appearance | no | none |
| the four committed fixes (shared UI state, spin pin, window identity, verify-coverage) | no | untouched |

## §7 Verification

- `make capture-typecheck` → 0 errors in `src/gui-tools/capture-tool`.
- `tsc --noEmit -p tests/tsconfig.tests.json` → 0 errors.
- `make capture-test` → 115 pass / 0 fail (111 + 4 new), tests config typecheck clean.
- Both configs typechecked with `@types/node` in **both** reachable and unreachable
  positions, to show the arrangement no longer decides the outcome.
- `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at 33 used / 28 styled.
- Capture `pytest tests/` → 97; provisioning suite unchanged.

## §8 Risk

Very low and well bounded. One config line, which changes nothing about how the app
runs or bundles. The residual risk is over-tightening: if some future app code
legitimately needs a global type, the typecheck fails and the author adds it to
`types` by name with a justification — a review-visible cost of a few characters,
against a config whose correctness currently depends on an unreviewed gitignored
directory.
