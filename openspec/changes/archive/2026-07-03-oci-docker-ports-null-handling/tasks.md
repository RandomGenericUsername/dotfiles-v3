## 1. Fix null-Ports crash

- [ ] 1.1 In `src/oci_runtime/adapters/parser/docker.py:278`, change `raw_ports = item.get("Ports", [])` to `raw_ports = item.get("Ports") or []`.
- [ ] 1.2 Add `test_docker_list_ports_none_emits_empty` to `tests/unit/adapters/test_docker_parser.py`: feed `{"Ports": None}`, assert `container.ports == ()`.
- [ ] 1.3 Run `uv run pytest -q tests/unit/adapters/test_docker_parser.py` — green.
- [ ] 1.4 Run `uv run ruff check src/oci_runtime/adapters/parser/docker.py` — green.