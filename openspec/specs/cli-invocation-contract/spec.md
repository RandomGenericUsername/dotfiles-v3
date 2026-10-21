# cli-invocation-contract Specification

## Purpose
Defines the single runtime-to-CLI protocol artifact: versioned data plus a conformance kit owned by the `contracts` repo, executed by every consumer and every CLI instead of duplicated literal tests.

## Requirements

### Requirement: The contract is versioned data in the `contracts` repo

The `contracts` repo SHALL ship distribution `cli-invocation-contract` and import package `cli_invocation_contract`, with `invocation-contract.json` holding one entry per CLI. Each entry SHALL carry argv template, required env keys, required artifact names or suffixes, exit-code semantics and default timeout. The loader SHALL be stdlib-only.

#### Scenario: one record per CLI with every field

- **WHEN** the S0a gate loads the contract
- **THEN** `sorted(c) == ['csg', 'itr', 'weg']` and every entry contains `argv`, `env`, `artifacts`, `exit_codes` and `timeout`

#### Scenario: the contract tag is the package version

- **WHEN** `CONTRACT_VERSION` is printed through the installed package
- **THEN** it reports `0.1.0`, matching the `contracts` tag `v0.1.0`

#### Scenario: the data matches the observed invocation

- **WHEN** the contract record for each CLI is compared with S1's observed argv, env keys, artifact names and exit semantics
- **THEN** the values are equal; the record is not re-derived from the v0.1.0 implementation

### Requirement: The testkit exposes exactly two assertions

`cli_invocation_contract.testkit` SHALL expose one assertion that a consumer's recorded invocation matches the record and one assertion that a CLI accepts the recorded invocation and writes the required artifacts. The CLI runner SHALL be injected. Tests SHALL NOT shell out to a real CLI.

#### Scenario: a matching consumer invocation passes

- **WHEN** the consumer assertion is given the runtime's recorded argv and env for csg, weg or itr
- **THEN** it passes and reports no difference from the record

#### Scenario: a drifted invocation fails

- **WHEN** the consumer assertion is given an argv missing a required `--format`, or an env map missing a required key
- **THEN** it fails and names the missing element

#### Scenario: the conformance assertion runs against a fake CLI

- **WHEN** the conformance assertion is given an injected runner backed by a fake CLI that writes the required artifacts
- **THEN** it passes; a fake that omits an artifact fails

### Requirement: Every consumer and CLI proves conformance through the kit

The runtime adapters and the three CLI repos SHALL assert their invocation behavior through the kit. The runtime and all three CLIs SHALL pin the same `contracts` tag. `cli-output` SHALL remain presentation-only and SHALL neither host nor import the contract.

#### Scenario: the runtime uses the kit, not local literals

- **WHEN** the runtime adapter tests are inspected after S0b
- **THEN** `src/runtime/tests/unit/test_cli_invocation_contract.py` (added by the slice) loads the record and calls `assert_consumer_invocation` with each adapter's constructed argv/env, and the three duplicated literal tests named in S1 §6.1 — `test_csg_generate_env_override_writes_to_output_dir`, `test_weg_generate_env_override_writes_to_output_dir`, `test_itr_render_env_override_writes_to_output_dir` — no longer exist

#### Scenario: the old literals are gone

- **WHEN** `rg -n 'def test_(csg_generate_env_override_writes_to_output_dir|weg_generate_env_override_writes_to_output_dir|itr_render_env_override_writes_to_output_dir)' src/runtime/tests` is run after S0b
- **THEN** it exits 1 with no matches, while `uv run --directory src/runtime pytest tests/unit/test_cli_invocation_contract.py -q` exits 0

#### Scenario: a CLI proves it accepts its own record

- **WHEN** a CLI repo's gates run
- **THEN** its suite includes the conformance assertion from the pinned kit

#### Scenario: cli-output stays presentation-only

- **WHEN** the `cli-output` checkout is searched for `cli_invocation_contract` or `invocation-contract.json`
- **THEN** no match exists

### Requirement: The version handshake reports the contract version

Each CLI SHALL support `--version` and print `<package-version> contract <contract-version>`, where the contract version is read from `cli_invocation_contract.CONTRACT_VERSION`. It SHALL NOT be read from `cli-output`.

#### Scenario: all three CLIs report the same contract token

- **WHEN** `itr --version`, `weg --version` and `csg --version` are run
- **THEN** each line ends with `contract 0.1.0` while the first token is that package's own version

#### Scenario: the token tracks a contract bump

- **WHEN** a consumer moves to a later `contracts` tag
- **THEN** its `--version` contract token changes without any edit to its `cli-output` dependency
