# runtime-event-contract (delta)

## ADDED Requirements

### Requirement: The runtime consumes the generated contract bindings

The Python runtime SHALL obtain its wire tables, bus name, topic allowlist, and per-topic validation schemas from the generated contract bindings, not from hand-embedded literals. The generated bindings SHALL be vendored into this repo at a pinned `contracts` commit.

Source: spine **AD-6** (contract is the single source; bindings generated).

#### Scenario: no hand-embedded wire literal remains

- **WHEN** the runtime adapters are searched for a hand-embedded `org.dotfiles.Events1` table or a per-topic schema
- **THEN** none remain outside the vendored generated bindings

#### Scenario: the vendored copy matches the contract repo

- **WHEN** the cross-repo drift gate runs
- **THEN** the vendored bindings are byte-identical to `contracts/generated/` at the pinned commit
- **AND** a hand-edited vendored copy fails the gate

### Requirement: The dead contract literal is removed

The superseded `speedtest.finished` topic literal SHALL NOT remain in any consumer.

Source: spine **AD-6**; contracts REQ-005.

#### Scenario: the dead topic is gone

- **WHEN** the tree is searched for `speedtest.finished`
- **THEN** no occurrence remains
