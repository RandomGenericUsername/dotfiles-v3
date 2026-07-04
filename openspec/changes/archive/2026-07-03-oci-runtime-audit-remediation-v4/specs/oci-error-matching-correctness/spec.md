## ADDED Requirements

### Requirement: matches_any_pattern is case-insensitive on both text and patterns

`domain/error_matching.matches_any_pattern(text, patterns)` lowercases **both** the input text and each pattern before matching: `re.escape(p.lower())` against `text.lower()`. A pattern containing uppercase letters MUST match the corresponding uppercase text. This makes the not-found and auth-error predicates safe for mixed-case patterns (the most security-sensitive predicates in the module).

#### Scenario: Uppercase pattern matches uppercase text
- **WHEN** `matches_any_pattern("No Such Image: foo", ("No such image",))` is called
- **THEN** it returns `True`

#### Scenario: Mixed-case pattern matches lowercased text
- **WHEN** `matches_any_pattern("Error: Pull Access Denied for foo", ("Pull Access Denied",))` is called
- **THEN** it returns `True`

#### Scenario: Lowercase patterns still match (no regression)
- **WHEN** `matches_any_pattern("No such image: foo", ("no such image",))` is called
- **THEN** it returns `True`

#### Scenario: Non-matching pattern returns False
- **WHEN** `matches_any_pattern("network unreachable", ("no such image",))` is called
- **THEN** it returns `False`

### Requirement: Docker and Podman not-found patterns are at parity

The `_not_found_patterns` tuple for each entity type (container, image, volume, network) SHALL be identical across the Docker and Podman parsers. Podman container parser SHALL include `"no such object"` alongside `"no such container"`, matching the Docker container parser. This guarantees entity-typed errors (`ContainerNotFoundError` etc.) surface correctly under both runtimes, including rootless/remote Podman paths that emit `"no such object"`.

#### Scenario: Podman container not-found via "no such object"
- **WHEN** `PodmanContainerParser().is_not_found_error("Error: no such object: abc123")` is called
- **THEN** it returns `True`

#### Scenario: Docker and Podman container pattern sets are equal
- **WHEN** the `_not_found_patterns` of `DockerContainerParser` and `PodmanContainerParser` are compared
- **THEN** they are equal as sets

#### Scenario: Podman image not-found pattern parity
- **WHEN** the `_not_found_patterns` of `DockerImageParser` and `PodmanImageParser` are compared
- **THEN** they are equal as sets
