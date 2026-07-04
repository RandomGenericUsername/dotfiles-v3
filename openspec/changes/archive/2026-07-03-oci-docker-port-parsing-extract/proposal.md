## Why

`tests/conformance/parsers/test_docker_port_parsing.py` tests `parse_inspect_ports` (domain function), but the docker port-parsing in v4 was extracted to adapters. The domain function is a thin proxy; the real parsing is in `adapters/parsers/docker_port_parser.py`. Conformance tests for the adapter-layer port parser are missing.

## What Changes

- Add conformance tests in `tests/conformance/parsers/` for the adapter-level `DockerPortParser.parse()` using real CLI fixture data.
- Mirror the structure of `test_docker_port_parsing.py` but exercise the adapter class.

## Capabilities

### Modified Capabilities

- `oci-docker-list-port-parsing`: conformance tests SHALL validate the adapter-level `DockerPortParser` against real CLI fixtures.

## Impact

- **Code**: none.
- **Tests**: new `tests/conformance/parsers/test_docker_port_parser_adapter.py`.