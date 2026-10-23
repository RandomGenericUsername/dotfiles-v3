# cli-invocation-contract (delta)

## MODIFIED Requirements

### Requirement: Every consumer and CLI proves conformance through the kit

The runtime adapters and the three CLI repos SHALL assert their invocation behavior through the kit. The runtime and all three CLIs SHALL pin the same `contracts` tag. `cli-output` SHALL remain presentation-only and SHALL neither host nor import the contract.

#### Scenario: the runtime uses the kit, not local literals

- **WHEN** the runtime repo's tests are inspected
- **THEN** `tests/unit/test_cli_invocation_contract.py` loads the record and calls `assert_consumer_invocation` with each adapter's constructed argv/env, and the three duplicated literal tests no longer exist

#### Scenario: the old literals are gone

- **WHEN** `rg -n 'def test_(csg_generate_env_override_writes_to_output_dir|weg_generate_env_override_writes_to_output_dir|itr_render_env_override_writes_to_output_dir)' tests` runs in `dotfiles-runtime`
- **THEN** it exits 1 with no matches, while `uv run pytest tests/unit/test_cli_invocation_contract.py -q` exits 0

#### Scenario: a CLI proves it accepts its own record

- **WHEN** a CLI repo's gates run
- **THEN** its suite includes the conformance assertion from the pinned kit

#### Scenario: cli-output stays presentation-only

- **WHEN** the `cli-output` checkout is searched for `cli_invocation_contract` or `invocation-contract.json`
- **THEN** no match exists
