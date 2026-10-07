## ADDED Requirements

### Requirement: Every gate in `gates-ci` SHALL have a CI job

The CI workflow SHALL run every gate in `make gates-ci`, which the workflow's own
header names as the authoritative set. A gate that exists in `Makefile`'s
`GATES`, survives the `gates-ci` filter, and has no workflow job SHALL be a
failure — not an omission nobody notices.

`bluetooth-mock-parity` is the measured instance: in `GATES` since
`add-bluetooth-bar-popup`, with no CI job and therefore never run on a push.

#### Scenario: The Bluetooth gate runs in CI
- **WHEN** the workflow runs
- **THEN** a `bluetooth-mock-parity` job executes
  `python3 scripts/bluetooth-mock-parity.py` on a stock runner

#### Scenario: A newly added gate cannot be dropped
- **WHEN** a target is added to `GATES` and no workflow job runs it
- **THEN** `make ci-gates-parity` exits non-zero naming the gate

### Requirement: The two lists SHALL be compared, not maintained by hand

A check SHALL compare the `gates-ci` target set against the workflow's job set
and fail non-zero on any unmatched entry **in either direction**. A comment
asserting that a list cannot be quietly dropped does not enforce anything; the
measured `bluetooth-mock-parity` omission is the proof.

#### Scenario: A gate with no job fails
- **WHEN** a job is removed from the workflow while its gate remains in
  `gates-ci`
- **THEN** the check exits non-zero and names the gate

#### Scenario: A job with no gate fails
- **WHEN** a workflow job is added that runs no `gates-ci` target
- **THEN** the check exits non-zero and names the job

### Requirement: Renames SHALL be declared, never inferred

Where a CI job name differs from its `make` target, the correspondence SHALL be
an explicit table entry carrying a reason, not an assumption the reader is
expected to make. `contracts-check → contracts` and
`capture-hexagonal-gate → capture-hexagonal` are the two that exist today.

A renamed job with no table entry SHALL fail the check. This is the device
`bluetooth-mock-parity.py`'s `CLASS_MAP` already uses: a rename is a claim, so it
is written down and reviewed.

#### Scenario: An undeclared rename fails
- **WHEN** a job is renamed in the workflow and the table is not updated
- **THEN** the check exits non-zero and names both names, so the missing entry is
  obvious rather than looking like a deletion plus an addition

#### Scenario: The declared renames pass
- **WHEN** the check runs against the tree as committed
- **THEN** the two renamed pairs resolve through the table and the check is green

### Requirement: Deliberate exclusions SHALL be declared, not absent

`capture-typecheck` and `bar-typecheck` are excluded from CI because they cannot
run there — no `ags`, no Astal, no GTK4, and their tolerated-third-party buckets
are keyed to the literal `/usr/share/ags/js/` path. That exclusion SHALL be
represented in the check as a declared exemption with a reason, so it is a
decision on the record rather than a gap.

#### Scenario: The exclusion is stated rather than implied
- **WHEN** a reader asks why `bar-typecheck` has no CI job
- **THEN** the answer is a declared, reasoned entry in the check, not the absence
  of a line

### Requirement: The workflow header SHALL NOT claim enforcement it does not implement

The header's claim that the workflow "is the place a future change cannot quietly
drop one" SHALL be replaced by a description of the mechanism that actually
enforces it. Prose asserting a guarantee that no code provides is the defect this
change exists to fix and must not be left behind.

#### Scenario: The header names the real mechanism
- **WHEN** the workflow header is read
- **THEN** it points at `ci-gates-parity` as what keeps the lists aligned, rather
  than asserting that the alignment is self-evident
