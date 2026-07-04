## 1. Add adapter-level conformance tests

- [ ] 1.1 Create `tests/conformance/parsers/test_docker_port_parser_adapter.py` mirroring `test_docker_port_parsing.py` but calling `DockerPortParser.parse()`.
- [ ] 1.2 Run `uv run pytest -q tests/conformance/parsers/` — green.