## MODIFIED Requirements

### Requirement: Docker port parser conformance

Conformance tests SHALL validate the adapter-level `DockerPortParser.parse()` method against real CLI fixture data. The tests SHALL cover port-protocol pairs, range expansion, and edge cases (no ports, all ports, IPv6 binding).

#### Scenario: Adapter parser matches domain parser output
- **WHEN** `DockerPortParser.parse()` is called with the same fixture JSON as `parse_inspect_ports`
- **THEN** the output matches (same port/protocol dict structure)