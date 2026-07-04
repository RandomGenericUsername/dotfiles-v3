## 1. Add build_file_path + files validation

- [ ] 1.1 In `src/oci_runtime/domain/types.py:91-111`, after the existing `context_path + files` check, add: `if self.build_file_path is not None and self.files: raise ValueError("BuildContext: 'files' (in-memory) cannot be combined with 'build_file_path' (filesystem). Drop 'files' or use 'context_path'.")`.
- [ ] 1.2 Add `test_build_context_rejects_files_with_build_file_path` to `tests/unit/domain/test_types.py`: construct `BuildContext(build_file_path=Path("Dockerfile"), files={"app.py": b"..."})`, assert `ValueError`.
- [ ] 1.3 Add `test_build_context_build_file_path_alone_accepted` to same file: construct with only `build_file_path`, assert no error.

## 2. Replace bare asserts in image.py

- [ ] 2.1 In `src/oci_runtime/adapters/managers/image.py:45`, replace `assert context.build_file_content is not None` with `if context.build_file_content is None: raise ImageRuntimeError(message="BuildContext.build_file_content required for stdin (-f -)")`.
- [ ] 2.2 In `src/oci_runtime/adapters/managers/image.py:48`, same pattern: `if context.build_file_content is None: raise ImageRuntimeError(message="BuildContext.build_file_content or build_file_path required")`.
- [ ] 2.3 Add `test_build_with_context_path_raises_on_missing_content` to `tests/unit/adapters/test_cli_image_manager.py`.
- [ ] 2.4 Run `uv run pytest -q tests/unit/domain tests/unit/adapters/test_cli_image_manager.py` — green.
- [ ] 2.5 Run `uv run ruff check .` — green.