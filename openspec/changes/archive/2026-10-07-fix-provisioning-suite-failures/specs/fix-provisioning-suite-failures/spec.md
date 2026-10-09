## ADDED Requirements

### Requirement: The suite's result SHALL depend on the repository, not the machine

A test in the provisioning suite SHALL pass or fail for reasons that are true of
the repository. A test that depends on the ambient state of the machine it runs
on — a real pty, an X display, runtime icons already rendered under a particular
state-home — SHALL either be given what it needs by its own fixture, or skip
itself explicitly with a stated reason.

The measured problem: the suite does not finish green on a provisioned desktop,
and the failure count has been carried as "known, pre-existing" without being
written down.

#### Scenario: A test needing infrastructure supplies it itself
- **WHEN** a test asserts on the verify role's treatment of runtime icons
- **THEN** the test seeds the icons it needs in its own temporary state-home
  rather than reading whatever the developer's machine happens to have

#### Scenario: An unavoidable dependency is an explicit skip
- **WHEN** a test genuinely cannot run without infrastructure a stock runner lacks
- **THEN** it skips with a reason visible in the output and a marker documenting
  why, so the skip count is explained rather than silent

### Requirement: Every failure SHALL be classified before it is fixed

Each failing test SHALL be assigned exactly one bucket — a real defect (fix the
code), environment-dependent (make hermetic or skip explicitly), or a wrong test
(fix the test) — and the bucket SHALL be recorded with a one-line reason.

The buckets select different fixes and must not be treated uniformly: "make the
suite green" is how a real defect gets skipped alongside environmental noise.

#### Scenario: A failing assertion about shipped behaviour is a finding
- **WHEN** a test fails because the code does not do what the test asserts
- **THEN** that is reported as a defect and fixed in the code, not resolved by
  adjusting the test

#### Scenario: "Flaky" is not a classification
- **WHEN** a failure is recorded
- **THEN** the missing infrastructure is named precisely, or the bucket is one of
  the other two

### Requirement: No test SHALL be silenced by deletion or weakening

No test SHALL be deleted, and no assertion SHALL be weakened, to make the suite
pass. A test that cannot run everywhere is skipped with a stated reason; a test
that is genuinely obsolete is removed with the reasoning recorded, not quietly.

#### Scenario: The test diff is read
- **WHEN** the change is reviewed
- **THEN** the test-file diff is inspected specifically for deletions and
  weakened assertions, and the result is stated either way

#### Scenario: A hermetic fix still detects its defect
- **WHEN** a test is made hermetic
- **THEN** breaking the thing it asserts makes it fail again, proving it still
  checks something

### Requirement: The counts SHALL be written down

The pass / fail / skip counts SHALL be recorded in the change's `design.md`,
together with every skip and its reason, so that "N failed" is never again an
unexplained number a future change has to re-derive.

#### Scenario: A future reader finds the number
- **WHEN** someone touches provisioning and wants to know the baseline
- **THEN** the counts and the skip reasons are in `design.md`, dated and measured

#### Scenario: The result is stable
- **WHEN** the suite is run twice
- **THEN** both runs report the same result — a determinism change that is itself
  non-deterministic is not done
