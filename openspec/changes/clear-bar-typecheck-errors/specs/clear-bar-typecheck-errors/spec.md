## ADDED Requirements

### Requirement: The bar config SHALL NOT typecheck the pure-module tests

`dotfiles/config/ags/tsconfig.bar.json` SHALL exclude `tests/`. Those files need
`@types/node` and `allowImportingTsExtensions`, which belong to an app config's
ambient surface as much as Node globals belong in a GJS program — and they are
already gated by `make ags-test` against `tests/tsconfig.tests.json`, a config
that declares exactly those two and deliberately widens to neither `gi://*` nor
`ags/*`.

This is the same defect `harden-capture-typecheck-config` fixed in the capture
config: coverage that is not a property of what the config is supposed to check.

#### Scenario: The app config does not report test-file errors
- **WHEN** `npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json` runs
- **THEN** it reports no errors in `dotfiles/config/ags/tests/`

#### Scenario: The tests keep the types they need
- **WHEN** the bar config stops covering `tests/`
- **THEN** `make ags-test` still resolves `node:test` and `node:assert/strict`,
  and still accepts the `.ts` import suffix

#### Scenario: Excluding the tests is not how the tests were fixed
- **WHEN** the bar config's `exclude` is inspected
- **THEN** `tests/` is named AND `tests/tsconfig.tests.json` still declares
  `"types": ["node"]` and `allowImportingTsExtensions` — the tests were not
  silenced, they were un-double-covered

### Requirement: The bar tree SHALL typecheck with zero errors in its own files

`dotfiles/config/ags/` SHALL compile with zero TypeScript errors. Every error in
the tree at the time of this change SHALL be resolved at its cause.

Three causes are known and measured (design §1) and account for the majority:
the config over-reaching into `tests/`, the JSX-element type at
`app.add_window`, and `createBinding` property names that the generated GIR types
do not expose in the spelling the code used.

#### Scenario: A clean tree
- **WHEN** `npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json` runs
- **THEN** no error line begins with `dotfiles/config/ags/`

#### Scenario: Third-party errors are still tolerated, by location
- **WHEN** the compiler reports errors under `/usr/share/ags/js`
- **THEN** the gate tolerates them by path, exactly as `capture-typecheck` does,
  and does not count them against the bar tree

### Requirement: Type errors SHALL be fixed at the cause, never suppressed

No fix introduced by this change SHALL silence the compiler rather than satisfy
it. Specifically: no `as any`, no `@ts-ignore`, no `@ts-expect-error`, and no
widening of a config to hide a genuine mismatch.

A cast is permitted only where it states a runtime truth the compiler cannot see
— for example the JSX element at `app.add_window`, which *is* a `Gtk.Window` —
and SHALL be justified in a comment at that site.

#### Scenario: A rename is proven equivalent before it is made
- **WHEN** a `createBinding` property literal is changed from kebab-case to the
  declared camelCase
- **THEN** the change is justified by `kebabify()` round-tripping (measured in
  gnim's implementation), AND the affected surface is exercised live, because
  the rename is a claim about runtime behaviour and not only about types

#### Scenario: A safety error is treated as a defect
- **WHEN** the remaining errors are `'connection' is possibly 'null'` or
  `Object is of type 'unknown'`
- **THEN** they are fixed by narrowing or by an assertion that says why it is
  safe — not by asserting non-null with `!` and moving on

### Requirement: bar-typecheck SHALL fail on any error in its own tree

Once the tree is clean, the `bar-typecheck` target SHALL NOT tolerate errors in
`dotfiles/config/ags/`. The tolerance block and the Bluetooth-owned file list
SHALL be removed, not widened. Its pass/fail line SHALL mean "the bar tree
typechecks", not "the Bluetooth files are clean".

This matches the posture `capture-typecheck` already holds — *"Zero tolerance for
`src/gui-tools/capture-tool/`"* — and it is the point of the change: a gate that
reports errors and exits 0 trains its reader to ignore it.

#### Scenario: A new error anywhere in the bar tree fails the gate
- **WHEN** a type error is introduced in any file under `dotfiles/config/ags/`,
  including one no previous change has touched
- **THEN** `make bar-typecheck` exits non-zero and names the file and line

#### Scenario: The Bluetooth-owned list is gone
- **WHEN** the target is inspected
- **THEN** there is no per-file whitelist and no `NOTE:` tolerance block; the
  only tolerated bucket is the third-party path

### Requirement: The gate's strictness SHALL be proven to bite

A gate that cannot fail is not a gate — the failure mode this repository has hit
repeatedly ("implemented but invisible": a dead agent, a dead confirm button, a
dead chevron, a counter that passed on token presence).

The strictness SHALL be demonstrated by planting a type error, observing the
non-zero exit, and removing it — in a Bluetooth-owned file **and** in a file no
previous change had touched.

#### Scenario: A planted error is caught tree-wide
- **WHEN** `const BREAK_PROOF: number = "not a number"` is added to a non-Bluetooth
  bar file
- **THEN** `make bar-typecheck` exits non-zero and names that file and line

#### Scenario: The gate is green on a clean tree
- **WHEN** no error is present
- **THEN** `make bar-typecheck` exits 0 and reports no owned errors
