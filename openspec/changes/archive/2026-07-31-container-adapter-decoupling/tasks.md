> Note: Tasks 1–2 and most of 3–4 were completed by the sibling change
> `cli-flag-scope-refinement` (commit `9ee6595`). Only the interface contract
> tests remain unimplemented.

## 1. WEG — Add `_CONTAINER_ENV` and pass via RunConfig

- [x] 1.1 Add `_CONTAINER_ENV` module-level constant to `adapters/container_processor.py`
- [x] 1.2 Add `environment=_CONTAINER_ENV` parameter to the `RunConfig(...)` call
- [x] 1.3 Remove `--config` and `--effects` from `_build_weg_command`
- [x] 1.4 Remove unused `output_name`

## 2. CSG — Fix protocol and extend `_CONTAINER_ENV`, drop `--runtime` from argv

- [x] 2.1 Add `environment: dict[str, str] | None = None` parameter to `ContainerRuntimePort.run()`
- [x] 2.2 Add `"COLORSCHEME__RUNTIME__MODE": "local"` to `_CONTAINER_ENV`
- [x] 2.3 Remove `"--runtime"` and `"local"` from `inner_command` in `process_generate`
- [x] 2.4 Remove `"--runtime"` and `"local"` from `inner_command` in `process_show`

## 3. WEG — Update existing tests for new argv shape

- [x] 3.1 Update `tests/unit/adapters/test_container_processor.py`:
  - `test_process_effect_success`: assert exact command shape (no `--config`/`--effects`)
  - `test_uses_oci_command_runner`: same pattern
  - `test_passes_expected_environment`: assert `run_config.environment == _CONTAINER_ENV`
- [x] 3.2 Run WEG test suite — all pass

### 3.3 Interface contract test

- [x] Add `test_build_weg_command_argv_is_accepted_by_cli`: validate adapter argv against live CLI parser (WEG, parameterized for effect/composite/preset)

## 4. CSG — Update existing tests for new argv shape

- [x] 4.1 Update `tests/unit/adapters/test_container_processor.py`:
  - `test_inner_command_contains_runtime_local`: assert `--runtime` is NOT in command
  - `test_show_inner_command_has_runtime_local`: same pattern
  - `test_passes_expected_environment`: includes `COLORSCHEME__RUNTIME__MODE` key
- [x] 4.2 Run CSG test suite — all pass

### 4.3 Interface contract test

- [x] Add `test_inner_command_argv_is_accepted_by_cli`: validate adapter argv against live CLI parser (CSG)

## 5. Verify final state

- [x] 5.1 WEG test suite passes
- [x] 5.2 CSG test suite passes
- [x] 5.3 `weg batch all` succeeds
- [x] 5.4 `csg generate --runtime container` works
