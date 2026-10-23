# Tasks: declare-capture-test-dependencies

## 1. Reproduce the gap, on a clean checkout

Cloned the branch to `/tmp/opencode/pristine` and installed `typescript@5.9` at
the root, so the target's `if [ -x node_modules/.bin/tsc ]` guard is satisfied
and the failure it was hiding is reachable.

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
error TS2688: Cannot find type definition file for 'node'.
  The file is in the program because:
    Entry point of type library 'node' specified in compilerOptions
EXIT=2
```

`make capture-test` in that state:

```
ℹ tests 115   ℹ pass 115   ℹ fail 0   ℹ skipped 0
NOTE: typescript not installed, skipping the test-file typecheck.
      (run 'make capture-typecheck' once to install it; the tests above still ran)
```

And the self-skip, in `tests/ts/typecheck-config.test.ts`:

```ts
  if (!tsc) {
    console.log(
      "NOTE: typescript not resolvable, skipping the tsc --listFiles evidence check. " +
        "The three static assertions above still ran.",
    )
    return t.skip("typescript not installed")
  }
```

**114 pass / 1 skip** on a checkout that has a compiler installed — the one
skipped case being the only one that measures the real compiler.

## 2. Prove `@types/node` fixes the tests config without touching the app

`tests/node_modules/` empty, `typescript@5.9` at the root:

```
$ npm install --no-save --no-package-lock --prefix src/gui-tools/capture-tool/tests @types/node@24
added 2 packages in 252ms
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
EXIT=0
```

## 3. Prove the app typecheck is untouched, in all three arrangements

`npx tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json --listFiles`,
counting `@types/node` files in the GJS app program:

| arrangement | `@types/node` files in the app program |
|---|---|
| `tests/node_modules/@types/node` only, `"types": []` | **0** |
| repo-root `node_modules/@types/node`, `"types": []` | **0** |
| repo-root `node_modules/@types/node`, pin **removed** | **66** |

The third row is why the install location is a constraint and not a preference.
Chosen arrangement, on the real tree:

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json --listFiles 2>/dev/null | grep -c '@types'
0
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json 2>&1 | grep 'error TS' | grep -c 'src/gui-tools/capture-tool/'
0
```

## 4. The change

- [x] `Makefile`: new `capture-test-deps` phony target installing
      `typescript@5.9` (repo root) and `@types/node@24`
      (`--prefix src/gui-tools/capture-tool/tests`), both guarded and idempotent.
- [x] `Makefile`: `capture-test` depends on it; the
      `if [ -x node_modules/.bin/tsc ]` guard and its NOTE deleted, so the tsc
      pass is unconditional and its failure fails the gate.
- [x] `typecheck-config.test.ts`: the `t.skip` branch replaced by `assert.ok(tsc, ...)`
      naming the fix. No case removed; no assertion weakened.
- [x] `typecheck-config.test.ts`: the whole-program 0-errors check scoped to
      `domain/`, `ports/`, `types.ts`, and the `>10 files` non-vacuity guard
      replaced by a positive control. Forced by measurement — see §7.
- [x] `tsconfig.tests.json`: rationale block documents where `@types/node` comes
      from and why the location is load-bearing. `compilerOptions` unchanged.
- [x] `tsconfig.capture.json`: comments only — the stale `83` corrected to the
      measured `66`, and the install source named. `"types": []` unchanged.
- [x] `.gitignore`: the `tests/node_modules/` comment rewritten. Path unchanged.
- [x] `gates.yml`: `capture-test` job comment rewritten. No step added or removed.

## 5. From a clean tree

```
$ rm -rf node_modules src/gui-tools/capture-tool/tests/node_modules
$ make capture-test
==> capture-test: installing typescript (npm install --no-save, ignored by git)
==> capture-test: installing @types/node under src/gui-tools/capture-tool/tests/ (gitignored)
==> capture-test: node --test src/gui-tools/capture-tool/tests/ts
ℹ tests 115
ℹ pass 115
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
==> capture-test: tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
    OK: 0 type errors in the domain unit tests
```

Second run (guards satisfied, no network):

```
==> capture-test: node --test src/gui-tools/capture-tool/tests/ts
ℹ pass 115   ℹ fail 0   ℹ skipped 0
==> capture-test: tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
    OK: 0 type errors in the domain unit tests
```

**And on a simulated CI runner** — clean clone, no `@girs/`, no `env.d.ts`, no
`node_modules/` anywhere — the same target installs both and reports full strength:

```
==> capture-test: installing typescript (npm install --no-save, ignored by git)
==> capture-test: installing @types/node under src/gui-tools/capture-tool/tests/ (gitignored)
ℹ pass 115   ℹ fail 0   ℹ skipped 0
    OK: 0 type errors in the domain unit tests
```

## 6. The other gates

```
$ make capture-typecheck
==> capture-typecheck: tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json
    tolerated third-party errors (/usr/share/ags/js): 28
    OK: 0 errors in src/gui-tools/capture-tool

$ python3 scripts/capture-hexagonal-gate.py
  ok   check 6: classic layout vocabulary unchanged (33 used / 28 styled)
PASS: capture hexagonal gate green

$ uv run --directory src/runtime pytest ../gui-tools/capture-tool/tests -q
97 passed in 0.10s

$ uv run --directory src/provisioning pytest tests/unit -q
720 passed in 460.69s (0:07:40)
```

## 7. The second defect, found by simulating a CI runner

Removing the skip was not enough. With both packages installed, case 4 **runs** —
and on a runner with no generated `@girs/` it fails, on a different assertion:

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json 2>&1 \
    | grep 'error TS' | grep -c 'src/gui-tools/capture-tool/'
344
```

344, versus 0 on this machine. Distribution: 335 `ui/`, 5 `adapters/`, 3
`app.tsx`, 1 `lib/`, and **0** in `domain/`, `ports/`, `types.ts`. All 344 are
unresolved `ags/gtk4`, `gi://GLib?version=2.0` and `./style.css` specifiers —
without the 168 machine-specific `.d.ts` files `ags types` generates from this
host's GTK/Astal, the app cannot resolve its own imports.

So the skip was masking a second problem: case 4 was desktop-only. Installing
TypeScript in CI would have turned 114/1-skip into 115/**1-fail** on 344 spurious
errors — worse than the skip, and a fine excuse to skip again.

Resolution, verified on a simulated runner (clean clone, no `@girs/`, no
`env.d.ts`, no `node_modules/` anywhere):

- 0-errors check scoped to `domain/`, `ports/`, `types.ts` → **0** both with and
  without `@girs/`.
- The `>10 files` non-vacuity guard replaced by a **positive control**: the
  identical `tsc --noEmit --listFiles` + regex over `tsconfig.tests.json`, which
  must find a non-zero number of `@types/node` files. Strictly stronger, and it
  makes the app-side assertion falsifiable.
- The dropped whole-program check is asserted, harder, by `make capture-typecheck`
  (fails on app errors **and** on errors in neither bucket).

Negative controls, on the simulated runner:

```
=== A: @types/node absent (broken install) ===
✖ app program contains no @types/node files (real compiler evidence)
  AssertionError: the tests project must typecheck cleanly — it declares
  "types": ["node"] and make capture-test installs @types/node for it —
  but tsc exited 2
ℹ pass 3   ℹ fail 1   ℹ skipped 0

=== B: pin removed AND @types/node at the repo root ===
✖ app config pins its ambient-type surface to empty
✖ app config does not name node, and does not widen typeRoots
✖ app program contains no @types/node files
  AssertionError: @types/node leaked into the GJS app program (66 files).
ℹ pass 1   ℹ fail 3   ℹ skipped 0

=== C: pin present, @types/node at the repo root (must hold) ===
ℹ pass 4   ℹ fail 0   ℹ skipped 0
```

B is the leak biting on a machine that has no `@girs` at all, and C is the property
`65c3cb35` bought: the surface is empty regardless of layout. Both now run in CI,
where neither ran before.

## 8. CI

`make -n gates-ci` expands to the six non-desktop gates, with `capture-test`'s two
install guards and both of its real steps. `capture-types`, `ags`, `@girs` and
`env.d.ts` appear nowhere in it.

## 9. Not committed

`node_modules/` at the root and under `src/gui-tools/capture-tool/tests/` are
gitignored; `git status --porcelain` lists no untracked `node_modules` in the
final report.
