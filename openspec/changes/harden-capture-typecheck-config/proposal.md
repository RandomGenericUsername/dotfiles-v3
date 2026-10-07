## Why

`src/gui-tools/capture-tool/tsconfig.capture.json` declared neither `"types"` nor
`"typeRoots"`. With both absent, TypeScript's default `typeRoots` walk takes every
`node_modules/@types` from the config's own directory upwards and auto-includes all
of it. The app's ambient-type surface was therefore **not a property of the app** —
it was a property of where a directory happened to sit on disk.

The app is GJS, not Node: no `process`, no `Buffer`, no `require`. It should have an
empty ambient-type surface, and it has one today only by accident. `@types/node`
lives at `tests/node_modules/`, which the upward walk never descends into. That is
luck, not design, and a `git mv` away from luck.

### Correction to the reported mechanism

The defect was reported as "move `@types/node` anywhere the root walk reaches and the
app typecheck collapses — roughly 96 errors in files nobody touched". **That
blast radius did not reproduce, and the collapse is a phantom.** Measured both ways
at HEAD:

| arrangement | total `error TS` | in `src/gui-tools/capture-tool/` |
|---|---|---|
| as committed (`tests/node_modules/@types/node`) | 28 | **0** |
| `capture-tool/node_modules/@types/node` | 28 | **0** |
| repo-root `node_modules/@types/node` | 28 | **0** |
| repo-root `@types/node@20.19.43` | 28 | **0** |

The three error sets are byte-identical; all 28 are pre-existing `/usr/share/ags/js`
third-party errors the `capture-typecheck` target already tolerates by path. A
JSX probe (`<box orientation={1} />` under the app's own `jsxImportSource`) also
typechecks identically in both directions, so gnim's `JSX.Element` does **not** widen.

**The leak itself is real and was measured directly**, it just is not yet
catastrophic. With `@types/node` reachable, `tsc --listFiles` reports **83**
`@types/node` files in the GJS app's program, and a probe referencing `process`
resolves cleanly where it should not:

```
# @types/node reachable, HEAD config:
src/gui-tools/capture-tool/zzprobe.ts(1,7): error TS2322:
  Type 'string | undefined' is not assignable to type 'string'.   <- process.env typed
# as committed:
src/gui-tools/capture-tool/zzprobe.ts(1,19): error TS2580:
  Cannot find name 'process'. Do you need to install type definitions for node?
```

So the defect is *Node globals silently entering a GJS program's scope*, not *96
errors*. It is still worth fixing on its own terms — it makes the typecheck's
correctness contingent on a gitignored directory that nobody reviews — but the
urgency is "correctness by luck", not "the gate is on fire". Fixing it is cheap;
the phantom is recorded so nobody re-investigates it.

## What Changes

- **`"types": []` on `tsconfig.capture.json`.** The app's ambient-type surface is
  pinned to empty explicitly, so it no longer depends on where `@types/node` lives.
  A non-empty surface is still possible, but only by someone naming a type and
  re-justifying it in review — which is the point.
- **A regression test** (`tests/ts/typecheck-config.test.ts`, 4 cases) pinning the
  pin, plus real compiler evidence via `tsc --noEmit --listFiles` asserting zero
  `@types/node` files in the app program.
- **`tsconfig.tests.json` is unchanged.** It already names `"types": ["node"]`
  explicitly, so it keeps working in both layouts — verified in both directions.

## Non-goals

- **Not removing `@types/node`,** and not changing where it lives. The tests need
  it and its current home works.
- **Not adding `typeRoots` to the app config.** A `typeRoots` pointing at a shared
  `node_modules` would reintroduce the same layout dependence that `"types": []`
  exists to remove. The test asserts it stays unset.
- **Not folding the two configs together.** They have genuinely different
  requirements, as `tsconfig.tests.json`'s own header already argues. Folding them
  would mean either weakening the app's surface or handing `node:test` to GJS.
- **Not touching the 28 tolerated third-party errors** in `/usr/share/ags/js`. Out
  of scope; the gate already classifies them.

## Impact

- `src/gui-tools/capture-tool/tsconfig.capture.json` — one line plus its rationale.
- `src/gui-tools/capture-tool/tests/ts/typecheck-config.test.ts` — new, 4 cases.
- **`make capture-test` goes 111 → 115.** No existing test was modified or weakened.
- No runtime behaviour change; this is typecheck configuration only.
