## ADDED Requirements

### Requirement: `make capture-test` SHALL declare and install its dependencies

`make capture-test` SHALL install everything its own steps need, on demand, before
running them, and SHALL do so in the same shape `make capture-typecheck` already
uses for `typescript`: `npm install --no-save --no-package-lock` into a gitignored
`node_modules`, with no committed `package.json`.

The two declared dependencies are:

- `typescript@5.9` at the **repo root**, resolved by `npx tsc`.
- `@types/node@24` under **`src/gui-tools/capture-tool/tests/`**, installed with
  `--prefix` so it is a separate npm project.

Both installs SHALL be guarded so they are idempotent, SHALL NOT create a
`package.json` or `package-lock.json`, and SHALL fail the gate (non-zero exit)
rather than continue when the install fails.

A gate that cannot run on a clean checkout is not a gate, so nothing here may
depend on what a particular machine happens to have installed.

#### Scenario: A clean checkout runs the gate at full strength

- **GIVEN** a fresh clone with no `node_modules/` at the repo root and none under
  `src/gui-tools/capture-tool/tests/`
- **WHEN** `make capture-test` runs
- **THEN** it installs both packages, reporting each
- **AND** all 115 test cases pass
- **AND** zero fail and zero are skipped
- **AND** the `tsc --noEmit` pass over `tests/tsconfig.tests.json` runs and reports
  `0 type errors in the domain unit tests`

#### Scenario: The installs are idempotent

- **GIVEN** both packages already installed
- **WHEN** `make capture-test` runs again
- **THEN** neither install is repeated
- **AND** the gate's results are identical

#### Scenario: No package manifest is created

- **WHEN** the `@types/node` install runs
- **THEN** the only artifact created is `src/gui-tools/capture-tool/tests/node_modules/`
  and its contents
- **AND** no `package.json` and no `package-lock.json` are written

#### Scenario: A failing install fails the gate

- **GIVEN** `npm install` cannot complete for a declared dependency
- **WHEN** `make capture-test` runs
- **THEN** it exits non-zero
- **AND** the target does not proceed to run the tests as though nothing happened

### Requirement: `@types/node` SHALL be installed only under `tests/`

`@types/node` SHALL be installed under `src/gui-tools/capture-tool/tests/` and
nowhere the app config's ambient-type surface can reach: not at the repo root, not
at the capture-tool root, not in any `typeRoots` the app config declares.

The location is load-bearing and is guarded by two independent mechanisms, both of
which SHALL hold:

1. `tsconfig.capture.json` pins `"compilerOptions.types` to `[]`.
2. `tests/` lies below the app config's own directory, so TypeScript's default
   upward `typeRoots` walk never descends into it.

The app runs under GJS, not Node: no `process`, no `Buffer`, no `require`.
Installing `@types/node` where the app's walk reaches it would put Node globals in
scope for GJS code, one accidentally-reverted pin away.

#### Scenario: The app program admits no Node types

- **GIVEN** `make capture-test` has run, so `@types/node` is at
  `src/gui-tools/capture-tool/tests/node_modules/@types/node`
- **WHEN** `tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json --listFiles`
  runs
- **THEN** zero files matching `@types/node` are in the app program

#### Scenario: The app typecheck stays clean

- **GIVEN** `@types/node` installed under `tests/`
- **WHEN** `make capture-typecheck` runs
- **THEN** it reports `0 errors in src/gui-tools/capture-tool`
- **AND** the 28 tolerated third-party `/usr/share/ags/js` errors are the only
  other errors

#### Scenario: The location is a constraint, not a preference

- **GIVEN** `@types/node` installed at the **repo root** instead, and
  `tsconfig.capture.json`'s `"types": []` deleted
- **WHEN** `tsc --listFiles` runs over the app project
- **THEN** non-zero files from `@types/node` are in the GJS app program, showing
  the second guard is load-bearing in its own right

### Requirement: The gate's typecheck step SHALL NOT be conditional

The `tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json` step
SHALL run unconditionally as part of `make capture-test`, and a non-zero exit from
it SHALL fail the gate.

The step SHALL NOT be guarded by a presence check on `node_modules/.bin/tsc`, and
SHALL NOT print a note in place of running. A gate that reports success without
performing the check it exists to perform is the failure this requirement removes.

#### Scenario: The typecheck pass runs on a clean checkout

- **GIVEN** a fresh clone
- **WHEN** `make capture-test` runs
- **THEN** the tsc pass is executed, not skipped
- **AND** no "skipping the test-file typecheck" note is printed

#### Scenario: A type error in the test files fails the gate

- **GIVEN** a type error introduced in a file under `tests/ts/`
- **WHEN** `make capture-test` runs
- **THEN** the gate exits non-zero, naming the error

### Requirement: No test in the `capture-test` suite SHALL skip itself for a
### declared dependency

`tests/ts/typecheck-config.test.ts` SHALL NOT skip, and SHALL NOT print a note in
place of asserting, when `tsc` is unresolvable. It SHALL fail, with a message
naming the fix.

A quiet skip inside a gate on the assertion that measures the real compiler is
indistinguishable from that gate not existing. Because the compiler is a declared
dependency of the gate, its absence inside the gate is a failure with a cause, not
an unsupported environment.

The compiler-evidence case SHALL keep measuring zero `@types/node` files in the
app program with `tsc --noEmit --listFiles`, and SHALL keep asserting the accepted
exit status. It SHALL additionally run the **identical** measurement over the
tests config and require that it DOES find `@types/node` files — a positive
control, so the app-side assertion cannot pass vacuously. An absent package and a
correct exclusion are otherwise indistinguishable.

The case SHALL also assert that the app's **desktop-free** layer — `domain/`,
`ports/`, `types.ts` — typechecks with zero errors under `tsconfig.capture.json`.
It SHALL NOT assert the full app program, which requires the generated `@girs/`
closure and therefore cannot hold on a runner without the desktop stack. The full
app typecheck is `make capture-typecheck`'s assertion, and that gate checks the
same property strictly harder.

#### Scenario: The app check cannot pass vacuously

- **GIVEN** `tsconfig.capture.json` as committed
- **WHEN** the compiler-evidence case runs
- **THEN** it asserts zero `@types/node` files in the app program
- **AND** it asserts the identical measurement over the tests config finds a
  non-zero number of them
- **AND** a program of any size therefore cannot satisfy the case on its own

#### Scenario: A broken @types/node install is caught precisely

- **GIVEN** `tsc` resolvable but `@types/node` not installed
- **WHEN** the compiler-evidence case runs
- **THEN** it fails, reporting that the tests project exited non-zero because it
  declares `"types": ["node"]`
- **AND** it does not report a false pass for the app side

#### Scenario: The full app program is not asserted here

- **GIVEN** a runner with no generated `@girs/`
- **WHEN** the suite runs
- **THEN** all cases pass
- **AND** the app-side assertion is measured over the desktop-free layer and the
  ambient-type surface, not over `ui/`, `adapters/` or `app.tsx`

#### Scenario: An unresolvable compiler fails the suite

- **GIVEN** no `node_modules/.bin/tsc` at the repo root or the capture-tool root
- **WHEN** the `capture-test` suite runs
- **THEN** the compiler-evidence case FAILS
- **AND** its message names `make capture-test` / `capture-test-deps` as the fix
- **AND** the suite reports zero skipped tests

#### Scenario: The suite's size and coverage are unchanged

- **WHEN** `make capture-test` runs
- **THEN** the suite reports 115 cases
- **AND** 115 pass, 0 fail, 0 skipped
- **AND** every case that ran before this change still runs

#### Scenario: The evidence case still bites

- **GIVEN** `tsconfig.capture.json` with its `"types"` key deleted **and**
  `@types/node` installed at a location the default walk reaches
- **WHEN** the suite runs
- **THEN** the compiler-evidence case fails, reporting that `@types/node` leaked
  into the app program and how many files

### Requirement: CI SHALL run `capture-test` at full strength

`.github/workflows/gates.yml`'s `capture-test` job SHALL run the same 115
assertions and the same `tsc` pass a developer runs. It SHALL NOT state or rely on
a reduced-strength mode of the gate.

The job SHALL NOT claim that installing the gate's declared dependencies would
surface an unrelated pre-existing failure. Any dependency the gate declares is
installed by the gate; a clean runner is a runner that has just performed its
first-run install, not a runner running fewer checks.

#### Scenario: A clean CI runner reports 115/0

- **GIVEN** a fresh `actions/checkout` of the branch on `ubuntu-latest`, with Node
  pinned to 24
- **WHEN** the `capture-test` job runs `make capture-test`
- **THEN** it reports 115 pass, 0 fail, 0 skipped
- **AND** the tsc pass runs and reports zero type errors in the domain unit tests

#### Scenario: The CI gate set stays free of desktop-only steps

- **WHEN** `make -n gates-ci` is expanded
- **THEN** it contains no `capture-types`, `ags types`, `@girs` or `env.d.ts` step
