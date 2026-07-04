## Context

The conformance suite silently skips when fixtures are missing. An integrity test ensures fixtures are always present.

## Goals / Non-Goals

**Goals:** Fail-loud on missing fixtures.
**Non-Goals:** Removing the skipifs in test_parser_conformance.py (they stay as belt-and-braces for the per-test fixture-gating, but the integrity test is the real guard).

## Decisions

Enumerate all required fixtures (docker and podman variants of: container_list, container_list_ports, container_inspect, image_list, image_inspect, image_prune, network_inspect, volume_inspect, volume_list, build_output, pull). Assert each exists.

## Risks / Trade-offs

- None. The test can only fail or pass.