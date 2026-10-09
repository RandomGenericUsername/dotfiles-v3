## ADDED Requirements

### Requirement: No template SHALL be embedded inside a Jinja string literal

The Ansible tree under `src/provisioning/ansible/` SHALL NOT nest a `{{ }}`
template inside a Jinja string literal. Where a value must be interpolated into
a regex or another expression, the parts SHALL be joined with the Jinja
concatenation operator `~` (or another inline expression), never by placing a
template inside the literal.

This is the construct `ansible-core 2.23` disables by default, and it currently
emits on every `verify` run:

```
[WARNING]: Jinja constant strings should not contain embedded templates.
This feature will be disabled by default in ansible-core 2.23.
```

#### Scenario: A regex is assembled by concatenation
- **WHEN** an assertion builds a pattern from a literal and a variable
- **THEN** it joins them with `~`, for example
  `'save_config_on_exit\s*=\s*' ~ verify_btop_save_config_on_exit`, and contains
  no `{{ }}` inside the quoted literal

#### Scenario: The two btop assertions are equivalent after the change
- **WHEN** the `color_theme` and `save_config_on_exit` assertions are rewritten
- **THEN** they assert the same thing about the same rendered `btop.conf` — the
  regex each evaluates to is unchanged, quote class included

### Requirement: The lint SHALL scan expression contexts, not every string

The gate SHALL flag a nested template only inside a value that **is** a Jinja
expression — `assert.that` (including list items), `when`, `changed_when`,
`failed_when`, `until`. A top-level `{{ }}` in any other string SHALL NOT be
flagged.

This boundary is the difference between a gate and noise: the tree contains
`'…{{ … }}…'` inside `fail_msg` text at `packages.yaml:26-27`,
`verify:607-608` and `cli_tools:177`, where the quotes are literal characters
and the template is correctly top-level. Flagging those would train the reader
to ignore the gate.

#### Scenario: A top-level template is not a finding
- **WHEN** a `fail_msg` contains a quoted region with a top-level `{{ }}`
- **THEN** the lint does not flag it

#### Scenario: A folded block scalar is still caught
- **WHEN** the `that:` value is a `>-` block spanning multiple lines
- **THEN** the lint reports it, because it parses the YAML value rather than
  scanning lines — both real sites are folded blocks

### Requirement: The gate SHALL be able to fail

The lint SHALL be demonstrated failing on the defect and passing after the fix,
and SHALL exit non-zero naming the file, line and offending literal when it
finds one. A gate that cannot be shown to fail is not a gate.

#### Scenario: The defect is caught in the tree
- **WHEN** the lint runs against the tree **before** the fix
- **THEN** it exits non-zero and names `roles/verify/tasks/main.yml` at both
  offending sites

#### Scenario: The tree is clean after the fix
- **WHEN** the lint runs after the fix
- **THEN** it exits 0

#### Scenario: A planted defect is caught
- **WHEN** a nested template is added to an expression-context value anywhere in
  the tree
- **THEN** the lint exits non-zero and names it

### Requirement: The dry-run integration suite SHALL NOT be relied on for this class

The guard SHALL NOT be built on `tests/integration/test_ansible_dryrun.py`. Both
offending tasks are `when: not ansible_check_mode`, so `ansible-playbook --check`
skips them and the warning is unreachable from that suite.

A comment SHALL record this at the dry-run test, because it is the first guard a
reviewer will reach for.

#### Scenario: The reason is recorded where it will be looked for
- **WHEN** a maintainer reads the dry-run test to understand why the warning was
  not caught
- **THEN** the test states that the affected tasks are skipped under `--check`
  and points at the lint

### Requirement: This change SHALL NOT claim warnings are clean

`INJECT_FACTS_AS_VARS` is a separate, expected deprecation warning on
`ansible-core >= 2.21`, already documented as non-fatal. This change SHALL NOT
assert an empty warning set for `verify`, and SHALL NOT suppress or allowlist
that warning.

#### Scenario: The known-good warning still appears
- **WHEN** `verify` runs after this change
- **THEN** the embedded-template warning is gone, and any unrelated warning is
  neither removed nor hidden by it
