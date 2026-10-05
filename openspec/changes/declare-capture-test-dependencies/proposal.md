## Why

`src/gui-tools/capture-tool/tests/tsconfig.tests.json` declares `"types": ["node"]`,
and **nothing in the repo installed `@types/node`**. So the `tsc --noEmit` pass that
`make capture-test` runs over the test files could not succeed on any checkout:

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
error TS2688: Cannot find type definition file for 'node'.
  The file is in the program because:
    Entry point of type library 'node' specified in compilerOptions
```

Two agents in this series called TS2688 "pre-existing and unrelated" and moved on.
It is neither. It is a real gap in `capture-test`'s declared dependencies, with two
consequences:

1. **The gate's typecheck step was unrunnable.** `make capture-test` guards its
   tsc pass with `if [ -x node_modules/.bin/tsc ]`, so on a clean checkout it
   printed a NOTE and exited 0 — green, having typechecked nothing. The gate has
   never once run its own typecheck on a fresh clone.
2. **A test inside the gate self-skipped to hide it.** `tests/ts/typecheck-config.test.ts`
   case 4 printed `NOTE: typescript not resolvable, skipping the tsc --listFiles
   evidence check` and called `t.skip("typescript not installed")`. A clean
   checkout reported **114 pass / 1 skip** — and the one skipped case is the only
   one in the file that measures the real compiler rather than re-deriving the
   author's intent. A quiet skip, inside a gate, on the assertion that would have
   caught the gap. That is the exact failure mode this series has been closing.

CI had institutionalised it. `.github/workflows/gates.yml`'s `capture-test` job
installed nothing, and its comment explained that this was deliberate: installing
TypeScript "would also surface the pre-existing missing-@types/node failure
(TS2688) ... a real finding, but a separate fix from 'make CI run'." The separate
fix is this change.

## What Changes

- **`make capture-test` declares its dependencies.** A new `capture-test-deps`
  target installs `typescript@5.9` at the repo root and `@types/node@24` into
  `src/gui-tools/capture-tool/tests/`, both on demand, both idempotent, both in
  the same `npm install --no-save --no-package-lock` shape `capture-typecheck`
  already uses for typescript. Install-on-demand rather than a committed
  `package.json` — see design.md §2.
- **The tsc pass is unconditional.** The `if [ -x ... ]` guard and its NOTE are
  gone. The step runs, and `make capture-test` exits non-zero if it fails.
- **The self-skip is removed.** Case 4 now fails, naming the fix, if `tsc` is
  unresolvable. No skip path remains in the suite.
- **Case 4 stops being desktop-only.** Installing TypeScript in CI was not enough:
  case 4 also asserted the whole app program has zero type errors, which needs the
  generated `@girs/` closure (344 spurious errors without it). It now asserts zero
  errors over the app's desktop-free layer and adds a positive control so the
  ambient-type assertion is falsifiable. Details in design.md §4a.
- **CI runs the gate at full strength.** The `capture-test` job's comment is
  rewritten to state that the target installs what it declares; the job runs the
  same 115 assertions and the same tsc pass a developer does.

Net: a clean checkout goes from **114 pass / 1 skip / no typecheck** to
**115 pass / 0 fail / 0 skip / typechecked**.

## Non-goals

- **Not installing `@types/node` at the repo root or at the capture-tool root.**
  The install location is load-bearing, not preference — see design.md §3. The
  app config pins `"types": []` (`65c3cb35`); the location is the *second*,
  independent guard, so deleting the pin alone cannot leak Node globals into GJS
  code.
- **Not changing what the app config asserts.** `tsconfig.capture.json` keeps
  `"types": []` and no `typeRoots`. Its comment is corrected on two numbers
  (83 → 66 leaked files, measured at this revision) and on where `@types/node` is
  installed from; the pin itself is untouched.
- **Not touching the 28 tolerated `/usr/share/ags/js` third-party errors.**
- **Not adding `node_modules` to version control**, anywhere.
- **Not folding the two tsconfigs together.** They have genuinely different
  requirements, as `tsconfig.tests.json`'s own header argues.

## Impact

- `Makefile` — new `capture-test-deps` target; `capture-test` depends on it and
  its tsc step becomes unconditional.
- `src/gui-tools/capture-tool/tests/ts/typecheck-config.test.ts` — the skip branch
  becomes a hard failure; the weak non-vacuity guard becomes a positive control;
  the whole-program 0-errors check is scoped to the desktop-free layer. Comments
  updated. No case added or removed, so the count stays 115.
- `src/gui-tools/capture-tool/tests/tsconfig.tests.json` — rationale block
  documents where `@types/node` comes from.
- `src/gui-tools/capture-tool/tsconfig.capture.json` — comments only.
- `.gitignore` — the `tests/node_modules/` comment is rewritten; the path is
  unchanged.
- `.github/workflows/gates.yml` — `capture-test` job comment only. No step added
  or removed; `make capture-test` is what installs.
- `openspec/changes/harden-capture-typecheck-config/specs/` — the requirement
  that allowed a skip is annotated as superseded, with a pointer to this change.
  The requirement to assert zero `@types/node` files via the real compiler is
  unchanged and still in force.
- No runtime behaviour change. `capture-test` goes 114/1-skip → 115/0, and CI now
  runs the same 115 the developer does.

**One assertion is scoped rather than removed**, and it is worth stating plainly.
Case 4 also asserted that the *whole* app program has zero type errors. That needs
the generated `@girs/` closure, so it can only hold on a provisioned desktop —
344 unresolved-`ags/`-specifier errors on a clean runner, all in `ui/`,
`adapters/`, `app.tsx` and `lib/`, and **0** in `domain/`, `ports/`, `types.ts`.
The skip was masking this second problem too: had CI simply installed TypeScript,
the job would have gone red on 344 spurious errors, which is a worse outcome and a
plausible excuse to skip again. Case 4 now asserts zero errors over the
desktop-free layer, and replaces the weak "program has more than 10 files" guard
with a **positive control** — the identical `tsc --listFiles` measurement over the
tests config, which MUST find `@types/node`. The dropped check is not lost:
`make capture-typecheck` asserts it, and asserts it more strictly. See
design.md §4a.
