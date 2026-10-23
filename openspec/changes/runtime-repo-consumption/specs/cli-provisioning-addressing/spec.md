# cli-provisioning-addressing (delta)

## MODIFIED Requirements

### Requirement: The manifest is the single source of truth for extracted tools

`dotfiles/provisioning/cli-tools.yaml` SHALL be the single source of truth. Every entry, including `dotfiles-runtime`, SHALL carry `name`, `repo` and `tag` matching `^v\d+\.\d+\.\d+$` and SHALL NOT carry `source`.

#### Scenario: every extracted entry is repo + tag

- **WHEN** `dotfiles/provisioning/cli-tools.yaml` is read after the runtime slice
- **THEN** csg, weg, itr and dotfiles-runtime carry `name`, `repo` and `tag`, and no entry carries `source`

#### Scenario: the only local source left is dotfiles-runtime

- **WHEN** `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` is run after the runtime slice
- **THEN** it exits 1 with no matches — the historical last source (`dotfiles-runtime -> src/runtime`) is gone — and `make deploy-coverage` asserts the same scope

#### Scenario: a source-only entry is rejected

- **WHEN** an entry is given `source:` instead of `repo` + `tag`
- **THEN** the provisioning manifest gate fails and names the entry

#### Scenario: the tag format is exact

- **WHEN** an entry's `tag` does not match `^v\d+\.\d+\.\d+$`
- **THEN** the provisioning manifest gate fails

### Requirement: `deploy-coverage` asserts the pin shape and the retired-tree absence

`deploy-coverage` SHALL fail when an entry lacks `repo` or `tag`, when role/verify/manifest pins disagree, when a `path`/`editable` pin or `src/cli-tools` source remains, or when a retired tree exists. It SHALL assert `src/runtime/` is absent and that no manifest entry carries `source`.

#### Scenario: a missing pin key is caught

- **WHEN** an entry loses `repo` or `tag`
- **THEN** `make deploy-coverage` exits non-zero and names the entry

#### Scenario: a stale local source is caught

- **WHEN** any manifest entry still carries `source`, or `src/cli-tools` appears as an asset source
- **THEN** `make deploy-coverage` exits non-zero

#### Scenario: each slice asserts the tree it deleted

- **WHEN** `make deploy-coverage` runs after S1–S6 and the runtime slice
- **THEN** it exits 0 only while each deleted tree — including `src/runtime/` — is absent, so a reappearance fails the gate at the guard that owns it

#### Scenario: the retired trees are absent

- **WHEN** `make deploy-coverage` runs after the runtime slice
- **THEN** it exits 0 and asserts that `src/cli-tools/`, `src/shared/` and `src/runtime/` do not exist
