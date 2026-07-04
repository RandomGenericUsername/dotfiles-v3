## MODIFIED Requirements

### Requirement: Contract tests with real parser instances

Contract test cases SHALL be instantiated with each real parser class (Docker, Podman, Lima) in a conformance-style test. The test SHALL create a `ContainerListContract(...)` for each parser and assert the contract passes.

#### Scenario: All parsers satisfy container list contract
- **WHEN** `ContainerListContract` is instantiated with `DockerContainerListParser`, `PodmanContainerListParser`, and `LimaContainerListParser`
- **THEN** each contract instance passes (no assertion errors)