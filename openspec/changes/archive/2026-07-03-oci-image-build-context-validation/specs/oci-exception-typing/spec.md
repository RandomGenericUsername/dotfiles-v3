## MODIFIED Requirements

### Requirement: No bare assert on production invariants in adapter code

`adapters/managers/image.py` SHALL NOT use `assert` for production invariants. Where a precondition must be checked (e.g. `build_file_content is not None`), the code SHALL raise `ImageRuntimeError` with a diagnostic message naming the violated invariant.

#### Scenario: build_file_content None raises ImageRuntimeError not AttributeError
- **WHEN** `image.build` is called with a `BuildContext` whose `build_file_content` is `None` (e.g. via `dataclasses.replace` bypassing `__post_init__`)
- **THEN** `ImageRuntimeError` is raised (not `AttributeError` from `.encode("utf-8")` under `python -O`)