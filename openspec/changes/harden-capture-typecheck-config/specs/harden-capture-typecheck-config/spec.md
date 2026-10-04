## ADDED Requirements

### Requirement: The capture app config SHALL pin its ambient-type surface explicitly

`tsconfig.capture.json` SHALL declare `compilerOptions.types` explicitly, and that
list SHALL be empty.

The capture app runs under GJS, not Node: it has no `process`, no `Buffer` and no
`require`. Its ambient-type surface must therefore be empty by intent, not by
accident.

Rationale: with neither `types` nor `typeRoots` declared, TypeScript's default
`typeRoots` walk takes every `node_modules/@types` from the config's directory
upwards and auto-includes all of it, so the app's ambient types become a function of
directory layout. Measured directly, relocating `@types/node` to a location the walk
reaches puts **83** of its files into the GJS app's program.

#### Scenario: The surface is pinned to empty

- **WHEN** `tsconfig.capture.json` is read
- **THEN** `compilerOptions.types` is present and is the empty array `[]`

#### Scenario: Relocating @types/node cannot change the app's ambient types

- **GIVEN** `tsconfig.capture.json` as committed
- **WHEN** `@types/node` is present at `tests/node_modules/@types/node`, at
  `capture-tool/node_modules/@types/node`, or at the repo root, and
  `tsc --noEmit -p tsconfig.capture.json` is run in each arrangement
- **THEN** the app program's ambient-type surface is empty in all three, and the
  app typecheck result is identical across all three

#### Scenario: A Node global is not in scope in app code

- **WHEN** a file under `src/gui-tools/capture-tool/` references `process`
- **THEN** the app typecheck reports it as an unknown name

### Requirement: The app config SHALL NOT reopen the ambient-type walk via typeRoots

`tsconfig.capture.json` SHALL NOT declare `compilerOptions.typeRoots`.

An explicit `typeRoots` would be a weaker form of the same fix: it would encode the
intent as a pointer to a directory expected to be empty, so installing anything
there would silently degrade the pin. `"types": []` states the intent directly and
cannot be degraded by an unrelated directory's contents.

#### Scenario: typeRoots stays unset

- **WHEN** `tsconfig.capture.json` is read
- **THEN** `compilerOptions` has no `typeRoots` key

#### Scenario: node is not named in the app's types

- **WHEN** `tsconfig.capture.json` is read
- **THEN** `compilerOptions.types` does not contain `"node"`

### Requirement: The domain unit tests SHALL keep the Node types they need

The app config pinning its own surface SHALL NOT be achieved by removing Node types
from the tests. `tsconfig.tests.json` SHALL continue to declare
`"types": ["node"]`, because the domain unit tests run under `node --test` and
import `node:test` and `node:assert`.

`tsconfig.tests.json` names the types it wants, so it SHALL continue to typecheck
clean regardless of where `@types/node` is installed — verified in both the
`tests/node_modules/@types/` and repo-root positions.

#### Scenario: Tests still resolve node:test

- **WHEN** `tests/tsconfig.tests.json` is read
- **THEN** `compilerOptions.types` contains `"node"`

#### Scenario: Tests typecheck with the package in either location

- **GIVEN** `@types/node` installed at `tests/node_modules/@types/node`
- **WHEN** `tsc --noEmit -p tests/tsconfig.tests.json` runs
- **THEN** it exits 0 with zero errors
- **AND GIVEN** `@types/node` installed at the repo root instead
- **WHEN** `tsc --noEmit -p tests/tsconfig.tests.json` runs
- **THEN** it exits 0 with zero errors

### Requirement: The ambient-type surface SHALL be guarded by a regression test

A regression test SHALL assert the app config's ambient-type surface, so that
re-widening it fails a gate rather than passing review.

The test SHALL include static assertions that hold whether or not TypeScript is
installed — that `compilerOptions.types` is present and empty, that it omits `node`,
that `typeRoots` is unset, and that the tests config still names `node`.

The test SHALL ALSO include an assertion measured by the real compiler: running
`tsc --noEmit --listFiles` over the app project and asserting that **zero** files
from `@types/node` are in the program. This measures what the config actually
admitted rather than re-deriving `typeRoots` resolution.

Where TypeScript is not resolvable, that compiler-evidence case SHALL skip with a
console note, matching the `capture-test` target's existing behaviour, and the
static assertions SHALL still run.

#### Scenario: The guard fails when the pin is removed

- **GIVEN** `tsconfig.capture.json` with its `types` key deleted
- **WHEN** the regression test runs
- **THEN** it fails, naming that `compilerOptions.types` must be declared explicitly

#### Scenario: The guard fails when the surface actually widens

- **GIVEN** `tsconfig.capture.json` with no `types` key
- **AND** `@types/node` installed at a location the default walk reaches
- **WHEN** the regression test runs
- **THEN** the compiler-evidence case fails, reporting that `@types/node` leaked
  into the app program and how many files

#### Scenario: The guard passes when the fix is in place regardless of layout

- **GIVEN** `tsconfig.capture.json` as committed with `"types": []`
- **AND** `@types/node` installed at any location the default walk reaches
- **WHEN** the regression test runs
- **THEN** all cases pass

#### Scenario: The compiler-evidence case cannot pass vacuously

- **WHEN** the compiler-evidence case runs
- **THEN** it also asserts that `tsc --listFiles` returned a non-trivial program, so
  an empty result cannot satisfy it
