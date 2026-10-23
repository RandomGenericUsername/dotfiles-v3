# ags-extraction-gates (delta)

## ADDED Requirements

### Requirement: The typechecks cover the extracted surface

`ags-typecheck` SHALL fail on type errors across the platform surfaces being extracted (`kit/`, `lib/`, `domains/`, `bar/`), not only `audio/`. A pre-existing error MAY be baselined only with a stated reason, never a silent allowlist.

Source: spine **AD-19**.

#### Scenario: a bad extraction fails the typecheck

- **WHEN** a type error is introduced in a non-audio platform file
- **THEN** `make ags-typecheck` fails naming it

### Requirement: The typechecks run in CI

`bar-typecheck` and `ags-typecheck` SHALL run in CI on a provisioned (self-hosted) runner, so a bad extraction cannot pass CI unnoticed.

Source: spine **AD-19**.

#### Scenario: the workflow runs both typechecks

- **WHEN** the CI workflow runs
- **THEN** it includes `bar-typecheck` and `ags-typecheck` jobs
- **AND** `make ci-gates-parity` passes

### Requirement: The per-app suites run in the root gate

The per-app drift/symbol suites SHALL run from a root gate target, so extracting the shared seams does not lose their drift coverage.

Source: spine **AD-19**.

#### Scenario: a drift is caught from the root gate

- **WHEN** a per-app contract drift is introduced
- **THEN** the root gate target fails
