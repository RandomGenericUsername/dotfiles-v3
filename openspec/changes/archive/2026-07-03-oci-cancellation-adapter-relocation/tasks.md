## 1. Create domain/pipe_reader.py

- [ ] 1.1 Create `src/oci_runtime/domain/pipe_reader.py` with `PipeReader` (ABC), `SubprocessPipeReader`, `EventPipeReader` moved from `adapters/managers/pipe_reader.py`.
- [ ] 1.2 In `adapters/managers/pipe_reader.py`, replace class definitions with: `from oci_runtime.domain.pipe_reader import PipeReader, SubprocessPipeReader, EventPipeReader`.
- [ ] 1.3 Run `uv run pytest -q` — green.
- [ ] 1.4 Run `uv run ruff check .` — green.