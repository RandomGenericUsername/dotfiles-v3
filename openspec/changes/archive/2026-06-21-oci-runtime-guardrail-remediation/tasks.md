# Implementation Tasks

> **Execution rules — READ THESE BEFORE STARTING**
>
> This change is structurally different from the prior remediation. Every task names the **exact committed xfail test** that must flip from `xfailed` to `passed`. A task is NOT complete when you think the code is fixed — it is complete when:
>
> 1. The named xfail test passes (its `@pytest.mark.xfail(strict=True)` marker must be removed)
> 2. `make check` is green (ruff + full suite, no new failures)
> 3. No other xfail tests regressed (check the xfail count before/after)
>
> If a task's xfail does not flip, the fix is wrong. Do not mark it `[x]`.
>
> Work in task order (1 → 12). The module root is `src/shared/oci-runtime/`.
> Run `uv run pytest tests/audit/ tests/conformance/ -q` to see the current xfail baseline (26 audit + 7 conformance = 33 xfailed).

## 1. Domain layer: new exception classes (F7, F14)

- [x] 1.1 **Add `OperationTimeoutError(OciError)`** to `src/oci_runtime/domain/exceptions.py` (design D-F14). Class body:
  ```python
  class OperationTimeoutError(OciError):
      def __init__(self, command: list[str], timeout: float, message: str = "Operation timed out"):
          self.command = command
          self.timeout = timeout
          super().__init__(message, command=command)
  ```
  Add `OperationTimeoutError` to `domain/__init__.py`'s exception imports and `__all__`. Add to `oci_runtime/__init__.py`'s exception import block and `__all__`.
- [x] 1.2 **Add `ImageRuntimeError`, `VolumeRuntimeError`, `NetworkRuntimeError`** to `src/oci_runtime/domain/exceptions.py` (design D-F7):
  ```python
  class ImageRuntimeError(ImageError):
      pass
  class VolumeRuntimeError(VolumeError):
      pass
  class NetworkRuntimeError(NetworkError):
      pass
  ```
  Add all three to `domain/__init__.py` and `oci_runtime/__init__.py` exports + `__all__`.
- [x] **Verify 1:** `uv run python -c "from oci_runtime import OperationTimeoutError, ImageRuntimeError, VolumeRuntimeError, NetworkRuntimeError; assert all(issubclass(c, __import__('oci_runtime').OciError) for c in [OperationTimeoutError, ImageRuntimeError, VolumeRuntimeError, NetworkRuntimeError]); print('OK')"` prints `OK`. `make check` green.

## 2. Domain layer: RunConfig invariants (F17)

- [x] 2.1 **Move network_container and detach+tty validation into `RunConfig.__post_init__`** (design D-F17). In `src/oci_runtime/domain/types.py`, add after the cpu_limit check:
  ```python
  if self.network == NetworkMode.CONTAINER and not self.network_container:
      raise ValueError("RunConfig: network=CONTAINER requires network_container to be set")
  if self.detach and (self.tty or self.auto_tty):
      raise ValueError("RunConfig: detach=True is mutually exclusive with tty/auto_tty")
  ```
  Remove the corresponding `ContainerRuntimeError` checks from `CliContainerManager.run()` in `src/oci_runtime/adapters/managers/container.py` (lines ~40-44 and ~69-73).
- [x] **Verify 2:** `uv run pytest tests/unit/domain/test_types.py -q` passes. Add `test_runconfig_network_container_requires_arg` and `test_runconfig_detach_tty_mutually_exclusive` to `test_types.py` asserting `pytest.raises(ValueError)` for both. `make check` green.

## 3. Domain layer: RuntimeCapabilities frozen tuples (F21)

- [x] 3.1 **Change RuntimeCapabilities list fields to tuple** (design D-F21). In `src/oci_runtime/domain/capabilities.py`, change `list[str]` to `tuple[str, ...]` for `list_format_flags`, `default_run_flags`, `default_build_flags`. Change `field(default_factory=list)` to `field(default_factory=tuple)`.
- [x] 3.2 **Update provider construction sites** to pass tuples. In `src/oci_runtime/adapters/provider/docker.py` and `podman.py`, change `["--format", "{{json .}}"]` to `("--format", "{{json .}}")`, etc. for all list-valued capabilities.
- [x] **Verify 3:** `uv run python -c "from oci_runtime.domain.capabilities import RuntimeCapabilities; c = RuntimeCapabilities(); try: c.list_format_flags.append('x'); print('FAIL: mutable'); except AttributeError: print('OK: frozen')"` prints `OK: frozen`. `make check` green.

## 4. Adapter base: per-manager error classes (F7)

- [x] 4.1 **Add `_generic_error` class variable to `CliBaseManager`** (design D-F7). In `src/oci_runtime/adapters/managers/base.py`:
  ```python
  _generic_error: type[OciError] = ContainerRuntimeError
  ```
  Change the `raise ContainerRuntimeError(...)` in `_check_result` to `raise self._generic_error(...)`.
- [x] 4.2 **Set `_generic_error` in each manager subclass**. In `image.py`: `_generic_error = ImageRuntimeError`. In `volume.py`: `_generic_error = VolumeRuntimeError`. In `network.py`: `_generic_error = NetworkRuntimeError`. `container.py` keeps the inherited `ContainerRuntimeError`.
- [x] **Verify 4:** `uv run pytest tests/audit/test_known_bugs.py::TestF07 -q` — all 3 tests must **flip from xfailed to PASSED**. Remove the 3 `@pytest.mark.xfail` markers from `TestF07` in `tests/audit/test_known_bugs.py`. `make check` green, xfail count drops by 3 (from 33 to 30).

## 5. Manager fixes: prune error propagation (F3)

- [x] 5.1 **Add `_check_result` to all four `prune()` methods** (design D-F3). In `container.py`, `image.py`, `volume.py`, `network.py`, add `self._check_result(result, cmd, operation="prune X", entity="")` before `return self._parser.parse_prune(...)`. Use the entity-appropriate operation string ("prune containers", "prune images", "prune volumes", "prune networks").
- [x] **Verify 5:** `uv run pytest tests/audit/test_known_bugs.py::TestF03 -q` — all 4 tests must **flip from xfailed to PASSED**. Remove the 4 `@pytest.mark.xfail` markers from `TestF03`. `make check` green, xfail count drops by 4 (from 30 to 26).

## 6. Manager fixes: exec stderr, build flags (F1, F4)

- [x] 6.1 **Fix exec_container stderr on success** (design D-F1). In `src/oci_runtime/adapters/managers/container.py` `exec_container`, change:
  ```python
  if result.returncode != 0:
      stderr_str = self._decode_stdout(result.stderr)
      if self._parser.is_not_found_error(stderr_str):
          raise self._not_found_error(container)
  else:
      stderr_str = ""
  ```
  to:
  ```python
  stderr_str = self._decode_stdout(result.stderr)
  if result.returncode != 0 and self._parser.is_not_found_error(stderr_str):
      raise self._not_found_error(container)
  ```
- [x] 6.2 **Add build flags for build_args, labels, pull, network, rm, build_contexts** (design D-F4). In `src/oci_runtime/adapters/managers/image.py` `build()`, after the `--target` block, add the 6 flag blocks from design D-F4.
- [x] **Verify 6:** `uv run pytest tests/audit/test_known_bugs.py::TestF01 tests/audit/test_known_bugs.py::TestF04 -q` — all 4 tests must **flip from xfailed to PASSED**. Remove the 4 `@pytest.mark.xfail` markers. `make check` green, xfail count drops by 4 (from 26 to 22).

## 7. Manager fixes: logs stderr wiring (F2)

- [x] 7.1 **Wire on_stderr in logs(follow=True)** (design D-F2). In `src/oci_runtime/adapters/managers/container.py` `logs()`, change the `self._streaming.stream(cmd, on_stdout=_on_stdout, cancel_token=cancel_token)` call to also pass `on_stderr=_on_stdout` (same callback — stderr chunks go into the same queue as stdout chunks).
- [x] **Verify 7:** `uv run pytest tests/audit/test_known_bugs.py::TestF02 -q` — the test must **flip from xfailed to PASSED**. Remove the `@pytest.mark.xfail` marker. `make check` green, xfail count drops by 1 (from 22 to 21).

## 8. Parser fixes: coerce_size, size parsing, real-CLI conformance (F8, F9, F-CONF-1 through 5)

- [x] 8.1 **Fix `_coerce_size` return type** (design D-F8). In `src/oci_runtime/adapters/parser/base.py`, change `return size or 0` to `return int(size or 0)`.
- [x] 8.2 **Fix `parse_size_to_bytes`** (design D-F9). In `src/oci_runtime/adapters/_utils.py`, change `re.search` to `re.fullmatch`. Add `'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4, 'TIB': 1024**4` to the units dict.
- [x] 8.3 **Fix DockerContainerParser string Names** (design D-F-CONF-1). In `src/oci_runtime/adapters/parser/docker.py` `parse_list`, before the `isinstance(names, list)` check, add `if isinstance(names, str): names = [names]`.
- [x] 8.4 **Fix PodmanContainerParser null Ports** (design D-F-CONF-2). In `src/oci_runtime/adapters/parser/podman.py` `_parse_ports_from_list`, change `for p in item.get("Ports", []):` to `for p in (item.get("Ports") or []):`.
- [x] 8.5 **Fix all inspect parsers for null Labels** (design D-F-CONF-3/4). In every `parse_inspect` method across `docker.py` and `podman.py`, change `labels=item.get("Labels", {})` to `labels=item.get("Labels") or {}`. Also do the same for `item.get("Config", {}).get("Labels", {})` patterns — change to `item.get("Config", {}).get("Labels") or {}`.
- [x] 8.6 **Fix PodmanImageParser bare-hex pull ids** (design D-F-CONF-5). In `src/oci_runtime/adapters/parser/podman.py` `parse_id_from_pull`, before returning a bare line as the id, check: `if re.match(r'^[a-f0-9]{12,64}$', line): return f"sha256:{line}"`.
- [x] 8.7 **Remove redundant local import in `_coerce_size`** (design D-F38). In `src/oci_runtime/adapters/parser/base.py`, remove the `from oci_runtime.adapters._utils import parse_size_to_bytes` inside `_coerce_size` (line 10) — it's already imported at module level (line 4).
- [x] **Verify 8:** `uv run pytest tests/audit/test_known_bugs.py::TestF08 tests/audit/test_known_bugs.py::TestF09 tests/conformance/ -q` — TestF08 (1 test) + TestF09 (4 tests) must flip. All 7 conformance xfails must flip. Remove all 12 `@pytest.mark.xfail` markers. `make check` green, xfail count drops by 12 (from 21 to 9).

## 9. Transport fixes: resolved binary, timeout exception (F11, F14)

- [x] 9.1 **Fix `get_runtime_binary` to return resolved path** (design D-F11). In `src/oci_runtime/adapters/transport/cli.py`, change `return self.binary` to `return self._which_cache`.
- [x] 9.2 **Fix `_which_cache` type annotation** (design D-F39). Change `self._which_cache: str | None | None` to `self._which_cache: str | None | object = _NOT_PROBED` (or define a `_NotProbed` sentinel class).
- [x] 9.3 **Remove no-op try/except** (design D-F40). In `cli.py`, remove `except subprocess.TimeoutExpired: raise` (lines 46-47) — just let it propagate.
- [x] 9.4 **Replace `subprocess.TimeoutExpired` with `OperationTimeoutError` in stream()** (design D-F14). In `src/oci_runtime/adapters/transport/streaming.py`, change `raise subprocess.TimeoutExpired(...)` to:
  ```python
  raise OperationTimeoutError(command=command, timeout=timeout)
  ```
  Import `OperationTimeoutError` from `domain.exceptions`.
- [x] 9.5 **Replace `subprocess.TimeoutExpired` with `OperationTimeoutError` in run_pty()** (design D-F14). In `src/oci_runtime/adapters/managers/pty.py`, change `raise subprocess.TimeoutExpired(command, timeout)` to `raise OperationTimeoutError(command=command, timeout=timeout)`.
- [x] **Verify 9:** `uv run pytest tests/audit/test_known_bugs.py::TestF11 tests/audit/test_known_bugs.py::TestF14 -q` — both tests must **flip from xfailed to PASSED**. Remove the 2 `@pytest.mark.xfail` markers. `make check` green, xfail count drops by 2 (from 9 to 7).

## 10. Architecture fixes (F10, F15, F16, F19, F20)

- [x] 10.1 **Fix `exists()` to stop catching ParsingError** (design D-F10). In all four managers (`container.py`, `image.py`, `volume.py`, `network.py`), change `except (XNotFoundError, ParsingError): return False` to `except XNotFoundError: return False`. Remove `ParsingError` from imports if it becomes unused.
- [x] 10.2 **Add `cancellation_factory` to `RuntimeFactoryConfig`** (design D-F15). In `src/oci_runtime/factory.py`, add `cancellation_factory: Callable[[], CancellationToken] | None = None`. In `_resolve_config`, add default: `from oci_runtime.adapters._cancellation import ThreadCancellationToken; replacements["cancellation_factory"] = lambda: ThreadCancellationToken()`. Thread it through `BaseCliRuntimeProvider.create_managers` to `CliContainerManager`.
- [x] 10.3 **Cache `shutil.which` in `CliStreamingTransport`** (design D-F16). Add the same `_NOT_PROBED` sentinel + `_which_cache` pattern from `CliTransport` to `CliStreamingTransport`. Replace the uncached `shutil.which(self.binary)` check in `stream()` with the cached `_ensure_binary()` method.
- [x] 10.4 **Remove `RuntimeCapabilities` re-export from `ports/__init__.py`** (design D-F19). Remove the import and the `__all__` entry.
- [x] 10.5 **Change `CliBaseManager._not_found_error` default to `OciError`** (design D-F20). Change `_not_found_error: type[OciError] = ContainerRuntimeError` to `_not_found_error: type[OciError] = OciError`.
- [x] **Verify 10:** `uv run pytest tests/architecture/ -q` — layering linter must still pass (50 tests). `make check` green. No xfail count change (these are not xfailed bugs).

## 11. Test-quality fixes (F30, F34)

- [x] 11.1 **Fix B5 wiring tests to assert injected instances** (design D-F30). In `tests/unit/wiring/test_factory_wiring.py::TestFactoryCustomInjection`:
  - `test_custom_tty_detector_factory_is_used`: change `assert engine.capabilities is not None` to `assert engine.containers._tty_detector is custom_tty`
  - `test_custom_output_stream_factory_is_used`: change `assert engine.capabilities is not None` to `assert engine.containers._output_stream is custom_stream` (create a `custom_stream = io.BytesIO()` and pass it via the factory)
- [x] 11.2 **Fix `test_build_empty_output` to assert ImageError** (design D-F34). In `tests/unit/boundary/test_empty_outputs.py::test_build_empty_output`, change `result = mgr.build(...)` / `assert result == "sha256:"` to `with pytest.raises(ImageError): mgr.build(...)`. Import `ImageError`. Also add the corresponding `build()` check in `image.py`: after `parse_build_output`, if the result is `"sha256:"` or empty, raise `ImageError` (analogous to `pull()`'s A5 fix).
- [x] 11.3 **Fix `_MockParser` state type in `test_cli_container_manager.py`** (design F36). Change `state="running"` to `state=ContainerState.RUNNING` in the `_MockParser.parse_inspect` and `parse_list` methods.
- [x] **Verify 11:** `uv run pytest tests/unit/wiring/test_factory_wiring.py tests/unit/boundary/test_empty_outputs.py tests/unit/adapters/test_cli_container_manager.py -q` passes. `make check` green.

## 12. Code smells and cleanup (F38-F42)

- [x] 12.1 **Rename `_decode_stdout` to `_decode_bytes`** (design D-F41). In `src/oci_runtime/adapters/managers/base.py`, rename the method. Update all call sites in `container.py`, `image.py`, `volume.py`, `network.py` that use `self._decode_stdout(...)`.
- [x] 12.2 **Add tar path sanitization note** (design D-F42). In `src/oci_runtime/adapters/_tar.py`, add a docstring note to `create_build_tar` that `files` dict keys are used verbatim as tar entry names — callers must not include `..` or absolute paths from untrusted input.
- [x] **Verify 12:** `make check` green. ruff clean.

## 13. Final verification

- [x] 13.1 **Verify all audit xfails are flipped**. Run `uv run pytest tests/audit/ -q`. Expected: **0 xfailed, 19 passed** (all 19 audit bug reproductions are now passing tests with xfail markers removed). If any are still xfailed, the corresponding fix is incomplete — do not proceed.
- [x] 13.2 **Verify all conformance xfails are flipped**. Run `uv run pytest tests/conformance/ -q`. Expected: **0 xfailed, 32 passed, 1 skipped**. If any are still xfailed, the corresponding parser fix is incomplete.
- [x] 13.3 **Verify no xfail regressions**. Run `uv run pytest tests/ -q`. The total xfail count must be **0** (was 26+7=33 at baseline). Every prior xfail must now be a passing test.
- [x] 13.4 **Verify layering linter**. Run `uv run pytest tests/architecture/ -q`. Expected: 50 passed. No layering violations introduced.
- [x] 13.5 **Full gate**. Run `make check`. Must be green: ruff clean + all tests pass + 0 xfailed.
- [x] 13.6 **Bump version**. Change `version = "0.2.0"` to `version = "0.3.0"` in `pyproject.toml` (breaking changes: F7 entity-typed errors, F14 OperationTimeoutError, F11 resolved binary path).
- [x] 13.7 **Update ARCHITECTURE.md**. Add `OperationTimeoutError` to the exception hierarchy diagram. Note the F7 entity-typed runtime errors. Note the F21 tuple fields. Add a Remediation Log row for this change.
