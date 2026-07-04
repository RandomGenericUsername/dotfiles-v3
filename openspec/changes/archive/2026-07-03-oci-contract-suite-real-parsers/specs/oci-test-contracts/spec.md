## MODIFIED Requirements

### Requirement: Contract suite with real parser instances

A contract suite SHALL be runnable against each real parser implementation. The suite SHALL include all contract cases defined in the contract module.

#### Scenario: Full contract suite passes for Docker parser
- **WHEN** the full contract suite is run against `DockerContainerListParser`
- **THEN** all contract cases pass