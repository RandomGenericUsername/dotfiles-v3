## Context

Docker port parsing existed in domain (parse_inspect_ports) but the real parsing logic migrated to adapters/parsers/docker_port_parser.py in v4. Conformance tests still target the domain function.

## Goals / Non-Goals

**Goals:** Add conformance tests for adapter-layer DockerPortParser.
**Non-Goals:** Removing domain-function tests (belt-and-braces).

## Decisions

Mirror `test_docker_port_parsing.py` structure but call `DockerPortParser.parse()` with fixture data. Use same fixture JSON blobs (extracted from real CLI output).

## Risks / Trade-offs

- Low duplication risk — acceptable until domain function is removed.