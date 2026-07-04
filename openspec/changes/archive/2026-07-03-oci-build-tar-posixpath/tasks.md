## 1. Swap import

- [ ] 1.1 In `src/oci_runtime/domain/build_tar.py`, replace `from pathlib import PosixPath` with `import posixpath`.
- [ ] 1.2 Replace `PosixPath(p.replace("\\", "/"))` with `posixpath.normpath(p.replace("\\", "/"))`.
- [ ] 1.3 Run `uv run pytest -q tests/unit/domain/test_build_tar.py` — green.
- [ ] 1.4 Run `uv run ruff check .` — green.