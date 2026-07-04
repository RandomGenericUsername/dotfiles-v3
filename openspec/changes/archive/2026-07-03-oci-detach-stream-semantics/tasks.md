## 1. Rewrite detach

- [ ] 1.1 In `src/oci_runtime/adapters/managers/container.py`, rewrite `detach` to: build cmd, `subprocess.run(cmd, capture_output=True, text=True)`, parse container id from stdout, return `ContainerId`.
- [ ] 1.2 Update `test_container_detach` to expect `ContainerId` return, not `RuntimeError`.
- [ ] 1.3 Run `uv run pytest -q tests/unit/adapters/test_cli_container_manager.py` — green.