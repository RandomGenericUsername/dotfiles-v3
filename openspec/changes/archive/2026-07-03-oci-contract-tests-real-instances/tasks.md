## 1. Add real-parser contract tests

- [ ] 1.1 Create `tests/conformance/test_contract_real_parsers.py` with `test_container_list_contract_docker`, `test_container_list_contract_podman`, `test_container_list_contract_lima`. Mark `@pytest.mark.slow`.
- [ ] 1.2 Run `uv run pytest -q tests/conformance/test_contract_real_parsers.py` — green.