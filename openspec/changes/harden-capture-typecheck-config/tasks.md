## 1. Reproduce the leak, and check the reported blast radius

**The ~96-error collapse is a phantom.** The leak underneath it is real.

### 1a. `@types/node` where the default walk reaches it

```
$ mkdir -p node_modules/@types
$ cp -r tests/node_modules/@types/node node_modules/@types/node     # reachable
$ tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json
```

| arrangement | total `error TS` | in `src/gui-tools/capture-tool/` |
|---|---|---|
| as committed (`tests/node_modules/@types/node`) | 28 | **0** |
| `capture-tool/node_modules/@types/node` | 28 | **0** |
| repo-root `node_modules/@types/node` (v26.6.4) | 28 | **0** |
| repo-root `node_modules/@types/node` (v20.19.43) | 28 | **0** |

```
$ diff <(grep 'error TS' at-root.log) <(grep 'error TS' baseline.log) && echo IDENTICAL
IDENTICAL error sets -> the 96-error collapse is a PHANTOM
```

All 28 are pre-existing `/usr/share/ags/js` third-party errors already tolerated by
the `capture-typecheck` target's `thirdparty` grep. Zero are in app files, in every
arrangement. A JSX probe (`<box orientation={1} />`) typechecks identically both
ways, so gnim's `JSX.Element = GObject.Object` (`dist/jsx/jsx.ts:354`) does not widen.

### 1b. The leak itself, measured directly

```
$ tsc --noEmit -p tsconfig.capture.json --listFiles | grep -c '@types/node'
83
```

A probe referencing `process` in app code, with `@types/node` reachable:

```
zzprobe.ts(1,7): error TS2322: Type 'string | undefined' is not assignable to type 'string'.
```

As committed — the correct answer:

```
zzprobe.ts(1,19): error TS2580: Cannot find name 'process'. Do you need to install type definitions for node?
```

So Node globals do silently enter a GJS program's scope. The defect is real; the
collapse was not.

> **Measurement trap.** `npm install --no-save X` prunes previously `--no-save`
> packages. An intermediate `@types/node@20` install removed `typescript`, and the
> following `npx tsc` printed "This is not the tsc command you are looking for" and
> exited 1 — which `grep -c 'error TS'` reads as **0 errors**. One intermediate
> measurement above was a false green for exactly this reason. Always confirm
> `tsc --version` before trusting a count.

## 2. The fix

**`"types": []` on `tsconfig.capture.json`.** One line:

```jsonc
    // REQUIRED — PINS THE AMBIENT-TYPE SURFACE TO EMPTY, ON PURPOSE.
    "types": []
```

Chosen over the alternatives for reasons set out in design.md §3:

- **vs. explicit `typeRoots`** — weaker. It encodes the fix as a pointer to a
  directory expected to be empty, so installing anything there silently degrades it.
  `"types": []` says "look nowhere" and cannot be degraded.
- **vs. also adding `typeRoots` to the tests config** — unnecessary; that config
  already names `"types": ["node"]` and was verified clean with the package in
  either location.
- **vs. documenting the current `@types/node` location as the invariant** — the
  arrangement is gitignored and unreviewed, and leaves the surface wrong in
  principle.
- **vs. doing nothing** — "nothing broke yet" describes today's package contents,
  not the config. The gate should be trustworthy without an audit.

Nothing is broken by it: the app has no `process`/`Buffer`/`require` references.

## 3. Both configurations typecheck cleanly

```
$ make capture-typecheck
==> capture-typecheck: tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json
    tolerated third-party errors (/usr/share/ags/js): 28
    OK: 0 errors in src/gui-tools/capture-tool

$ tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
    OK: 0 type errors in the domain unit tests
```

And the arrangement-independence the fix buys — both configs, `@types/node` in
each reachable and unreachable position:

```
=== app config, normal layout ===                      0 errors in capture-tool
=== app config, @types/node FORCED reachable at root ===
zzprobe.ts(1,19): error TS2591: Cannot find name 'process'. ... and then add 'node' to the types field in your tsconfig.
                                                     ^ leak CLOSED
=== tests config, node at tests/node_modules ===       EXIT=0
=== tests config, node ONLY at root ===                EXIT=0
```

## 4. Test counts

```
$ make capture-test
ℹ tests 115
ℹ pass 115
ℹ fail 0
ℹ skipped 0
==> capture-test: tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
    OK: 0 type errors in the domain unit tests
```

111 → 115 (the 4 new cases). No existing test modified or weakened.

```
$ pytest tests/ -q        # capture
97 passed
```

## 5. Hexagonal gate

```
$ python3 scripts/capture-hexagonal-gate.py
PASS
check 6: 33 used / 28 styled
```

## 6. Provisioning suite unchanged

```
$ uv run --directory src/provisioning pytest tests/unit -q
4 failed, 661 passed
```

Same four names as before this change:
`test_packages_manifest_has_verified_set`,
`test_arch_packages_cover_exactly_logical_set`,
`test_debian_family_packages_cover_exactly_logical_set`,
`test_settings_parse_gate_tasks_exist_and_are_check_gated`.

## 7. The regression test, and proof it bites

`src/gui-tools/capture-tool/tests/ts/typecheck-config.test.ts`, 4 cases:

1. `compilerOptions.types` is present **and** is `[]` — holds with or without tsc.
2. it omits `node`; `typeRoots` unset.
3. the tests config still names `"node"` — guards the other direction.
4. **real compiler evidence**: `tsc --noEmit --listFiles` over the app project
   asserts **zero** `@types/node` files in the program. Also asserts the program is
   non-trivial, so it cannot pass vacuously.

### Negative test A — the pin removed (genuine HEAD shape)

```
✖ app config pins its ambient-type surface to empty (0.909ms)
  AssertionError: tsconfig.capture.json must declare compilerOptions.types
  explicitly; omitting it makes the app's ambient types depend on directory layout
✖ app config does not name node, and does not widen typeRoots (0.751ms)
✔ tests config still asks for node types by name (0.338ms)
✔ app program contains no @types/node files (real compiler evidence) (3470ms)
ℹ tests 4   ℹ pass 2   ℹ fail 2
```

### Negative test C — pin removed **and** `@types/node` relocated: the leak is caught

```
✖ app config pins its ambient-type surface to empty (1.416ms)
✖ app config does not name node, and does not widen typeRoots (0.082ms)
✔ tests config still asks for node types by name (0.364ms)
✖ app program contains no @types/node files (real compiler evidence) (3561ms)
  AssertionError: @types/node leaked into the GJS app program (83 files). The
  app's ambient-type surface must stay empty regardless of where @types/node is
  installed on disk.
ℹ tests 4   ℹ pass 1   ℹ fail 3
```

### Negative test B — pin **present**, `@types/node` relocated: the arrangement stops mattering

```
✔ app config pins its ambient-type surface to empty (0.870ms)
✔ app config does not name node, and does not widen typeRoots (0.098ms)
✔ tests config still asks for node types by name (0.310ms)
✔ app program contains no @types/node files (real compiler evidence) (3426ms)
ℹ tests 4   ℹ pass 4   ℹ fail 0
```

B is the property actually bought: the fix holds regardless of where `@types/node`
lives.

## 8. Recorded, not fixed

- `src/gui-tools/capture-tool/app.tsx:51` reads `app.get_monitors()` once in
  `main()` with no hotplug handler — monitors plugged after launch get no window.
- `src/gui-tools/hypr-pano/app.tsx:12` has the identical one-shot pattern.

Both are window-lifecycle behaviour, outside a typecheck-config change. See
design.md §5.
