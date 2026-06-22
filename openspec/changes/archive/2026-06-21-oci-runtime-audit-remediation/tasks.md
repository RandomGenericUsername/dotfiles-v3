# Implementation Tasks

> **Execution rules for the implementer**
> - Work strictly in task order (1 → 14). Do not skip ahead.
> - Each task lists exact file(s), line(s), and the change to make. Do not improvise outside the task description.
> - After each task group, run the **Verify** command. Do not proceed until it passes.
> - Do not edit files outside the paths listed in a task.
> - All evidence prototypes backing these tasks live in `/tmp/opencode/oci-audit-prototypes/` (referenced as `proto_<id>.py`).
> - The module root is `src/shared/oci-runtime/` (all relative paths below are from there).

## 1. Domain layer corrections (B1, B2)

^- [x] 1.1 **Move `RuntimeCapabilities` to `domain/capabilities.py`** (design D-B2). Create `src/oci_runtime/domain/capabilities.py` with the exact content of `src/oci_runtime/ports/capabilities.py` (the frozen dataclass). Delete `src/oci_runtime/ports/capabilities.py`. Update `src/oci_runtime/domain/__init__.py`: add `from oci_runtime.domain.capabilities import RuntimeCapabilities` and add `"RuntimeCapabilities"` to `__all__`. Evidence: `proto_b2_b6_caps_generic.py` confirms the source imports only stdlib.
^- [x] 1.2 **Move `ParsingError` to `domain/exceptions.py`** (design D-B1). Add to `src/oci_runtime/domain/exceptions.py` (after the `OciError` class, before the sibling subclasses) the class:
  ```python
  class ParsingError(OciError):
      """Raised when CLI output cannot be parsed."""
      def __init__(self, raw: str, message: str = "Failed to parse output"):
          self.raw = raw
          super().__init__(message)
  ```
  Add `from oci_runtime.domain.exceptions import ParsingError` to `src/oci_runtime/ports/parsers.py` and keep `"ParsingError"` in `ports/parsers.py`'s `__all__` (re-export for backward compat). Remove the class *definition* body from `ports/parsers.py` (keep only the import + `__all__` entry). Add `"ParsingError"` to `domain/__init__.py`'s exception import block and `__all__`. Evidence: `proto_b1_parsing_error_move.py` confirms cycle-free.
^- [x] 1.3 **Update all `RuntimeCapabilities` import sites** (design D-B2). Find every `from oci_runtime.ports.capabilities import RuntimeCapabilities` and change to `from oci_runtime.domain.capabilities import RuntimeCapabilities`. Files to update (verified by grep): `src/oci_runtime/ports/engine.py`, `src/oci_runtime/ports/provider.py`, `src/oci_runtime/adapters/provider/_base.py`, `src/oci_runtime/adapters/managers/base.py`, `src/oci_runtime/adapters/managers/container.py`, `src/oci_runtime/adapters/managers/image.py`, `src/oci_runtime/adapters/managers/volume.py`, `src/oci_runtime/adapters/managers/network.py`, `src/oci_runtime/adapters/engine/cli.py`, `src/oci_runtime/factory.py`. Do NOT change `ports/__init__.py` (it does not re-export capabilities).
^- [x] **Verify 1:** `cd src/shared/oci-runtime && uv run ruff check src/ && uv run python -c "from oci_runtime.domain import RuntimeCapabilities, ParsingError; from oci_runtime.ports.parsers import ParsingError as P2; assert ParsingError is P2"` — both must succeed.

## 2. Domain type validation (A4, C)

^- [x] 2.1 **Forbid `BuildContext` context_path + files** (design D-A4, spec `oci-build-context-validation`). In `src/oci_runtime/domain/types.py` `BuildContext.__post_init__`, after the existing `build_file_content`/`build_file_path` checks, add:
  ```python
  if self.context_path is not None and self.files:
      raise ValueError(
          "BuildContext: 'files' (in-memory) cannot be combined with 'context_path' "
          "(filesystem). docker build takes context from either stdin (tar) or a PATH, "
          "not both. Drop 'context_path' to send files via stdin tar, or drop 'files' "
          "to use the filesystem context at context_path."
      )
  ```
  Evidence: `proto_a4_build_context.py` (option X).
^- [x] 2.2 **Tighten `RunConfig` cpu_limit regex** (design D-C). In `src/oci_runtime/domain/types.py`, change `_CPU_LIMIT_RE = re.compile(r"^\d+\.?\d*$")` to `_CPU_LIMIT_RE = re.compile(r"^\d+(\.\d+)?$")` (rejects `"1."`).
^- [x] **Verify 2:** `uv run pytest tests/unit/domain/test_types.py -q` passes; then `uv run python -c "from oci_runtime.domain.types import BuildContext; from pathlib import Path;
try:
    BuildContext(build_file_content='FROM alpine', context_path=Path('/x'), files={'a':b'x'}); print('FAIL')
except ValueError as e: print('OK', 'context_path' in str(e) and 'files' in str(e))"` prints `OK True`.

## 3. Parser bug fixes (A1, A3, A9)

^- [x] 3.1 **Fix `_parse_json_list` empty-array handling** (design D-A1, spec `oci-list-semantics`). In `src/oci_runtime/adapters/parser/base.py` `_parse_json_list`, replace the body of the `try: data = json.loads(raw)` success branch so an empty list returns `[]` instead of raising. New body:
  ```python
  try:
      data = json.loads(raw)
  except json.JSONDecodeError:
      pass
  else:
      if isinstance(data, list):
          return data          # empty list -> [] (valid)
      return [data]
  ```
  Keep the NDJSON fallback (the `lines = raw.strip().split("\n")` block) unchanged, including its final `raise ParsingError(...)`. Do NOT touch `_parse_json_item`. Evidence: `proto_a1_empty_list.py`.
^- [x] 3.2 **Fix `parse_prune` to count `deleted: sha256:` lines** (design D-A3, spec `oci-prune-parsing`). In `src/oci_runtime/adapters/parser/base.py` `parse_prune`, change `id_pattern = re.compile(r"^[a-f0-9]{12,64}$", re.MULTILINE)` to `id_pattern = re.compile(r"^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$", re.MULTILINE)`. Wrap the `parse_size_to_bytes(space_match.group(1))` call in `try/except ValueError: reclaimed_bytes = 0` so an unparseable reclaimed value yields 0 instead of raising. Evidence: `proto_a3_prune_all.py`.
^- [x] 3.3 **Add `coerce_size` and `safe_int` helpers to `BaseCliParser`** (design D-A9). In `src/oci_runtime/adapters/parser/base.py`, add two module-level (or staticmethod) helpers:
  ```python
  def _coerce_size(size) -> int:
      from oci_runtime.adapters._utils import parse_size_to_bytes
      if isinstance(size, str):
          try: return int(size)
          except ValueError:
              try: return parse_size_to_bytes(size)
              except ValueError as e: raise ParsingError(raw=str(size), message=f"Cannot parse size: {size!r}") from e
      return size or 0

  def _safe_int(v):
      try: return int(v)
      except (TypeError, ValueError): return None
  ```
  Evidence: `proto_a9_podman_parser.py`.
^- [x] 3.4 **Use `coerce_size` in both image parsers** (design D-A9). In `src/oci_runtime/adapters/parser/docker.py` `DockerImageParser.parse_list`, replace the inline `isinstance(size, str)` try/except blocks (lines ~84-103) with `size = _coerce_size(size)` then `if not size: size = _coerce_size(item.get("VirtualSize", 0))` (keep the VirtualSize fallback, but using the helper). In `src/oci_runtime/adapters/parser/podman.py` `PodmanImageParser.parse_list`, add `size = _coerce_size(item.get("Size", 0))` and pass `size=size` to `ImageInfo(...)`. Import `_coerce_size` from `base` in both files.
^- [x] 3.5 **Use `safe_int` in `PodmanContainerParser._parse_ports_from_list`** (design D-A9). In `src/oci_runtime/adapters/parser/podman.py`, replace `int(container_port) if container_port is not None else 0` and `int(host_port) if host_port is not None else None` with guarded calls: if `_safe_int(container_port)` is `None`, skip that port entry (`continue`); else use the int. Import `_safe_int` from `base`. Evidence: `proto_a9_podman_parser.py`.
^- [x] **Verify 3:** `uv run pytest tests/unit/adapters/test_parser_base.py tests/unit/adapters/test_docker_parser.py tests/unit/adapters/test_podman_parser.py -q` passes; then run the A1/A3/A9 prototypes: `PYTHONPATH=src:. uv run python /tmp/opencode/oci-audit-prototypes/proto_a1_empty_list.py /tmp/opencode/oci-audit-prototypes/proto_a3_prune_all.py /tmp/opencode/oci-audit-prototypes/proto_a9_podman_parser.py` — all OK.

## 4. Transport and PTY fixes (A6, A7)

^- [x] 4.1 **Cache `shutil.which` in `CliTransport`** (design D-A7). In `src/oci_runtime/adapters/transport/cli.py` `CliTransport.__init__`, add `self._which_cache: str | None | None = None` and a module-level sentinel `_NOT_PROBED = object()`, initializing `self._which_cache = _NOT_PROBED`. Rewrite `_ensure_binary`:
  ```python
  def _ensure_binary(self) -> None:
      if self._which_cache is _NOT_PROBED:
          self._which_cache = shutil.which(self.binary)
      if self._which_cache is None:
          raise RuntimeNotAvailableError(self.binary)
  ```
  Evidence: `proto_a6_a7_pty_probe.py`.
^- [x] 4.2 **Add `timeout` to `run_pty`** (design D-A6, spec `oci-pty-timeout`). In `src/oci_runtime/adapters/managers/pty.py`, change the signature to `def run_pty(command, output_stream=None, timeout=None) -> subprocess.CompletedProcess:`. Inside the `while True` loop, before `select.select`, compute `remaining = None`; if `timeout is not None: remaining = max(0.0, timeout - (time.monotonic() - start))` (add `import time` and `start = time.monotonic()` before the loop). If `remaining == 0`: `proc.kill(); proc.wait(); raise subprocess.TimeoutExpired(command, timeout)`. Pass `min(0.1, remaining) if remaining is not None else 0.1` as the select timeout. Keep all other behavior (drain, cleanup) unchanged. Evidence: `proto_a6_a7_pty_probe.py`.
^- [x] **Verify 4:** `uv run pytest tests/unit/adapters/test_cli_transport.py tests/unit/adapters/test_cli_pty.py -q` passes; then `PYTHONPATH=src:. uv run python /tmp/opencode/oci-audit-prototypes/proto_a6_a7_pty_probe.py` — all OK.

## 5. Manager fixes (A2, A5, A7-cont, C)

^- [x] 5.1 **Fix `exec_container` failure model** (design D-A2, spec `oci-exec-semantics`). In `src/oci_runtime/adapters/managers/container.py` `exec_container`, replace the `self._check_result(result, cmd, operation="exec in container", entity=container)` call with a not-found-only check:
  ```python
  if result.returncode != 0:
      stderr_str = self._decode_stdout(result.stderr)
      if self._parser.is_not_found_error(stderr_str):
          raise self._not_found_error(container)
  return ExecResult(returncode=result.returncode, stdout=self._decode_stdout(result.stdout), stderr=stderr_str)
  ```
  (Define `stderr_str` before the if, or compute it once.) Do NOT call `_check_result`. Evidence: `proto_a2_exec.py`.
^- [x] 5.2 **Fix `pull` silent empty return** (design D-A5, spec `oci-pull-contract`). In `src/oci_runtime/adapters/managers/image.py` `pull`, after `ident = self._parser.parse_id_from_pull(...)`, add:
  ```python
  if not ident:
      raise ImageError(message="Could not parse image id from pull output", stderr=self._decode_stdout(result.stdout))
  ```
  Add `ImageError` to the imports from `domain.exceptions` (it currently imports only `ImageNotFoundError`). Evidence: `proto_a5_pull.py`.
^- [x] 5.3 **Remove dead guards in `CliContainerManager.run`** (design D-C). In `src/oci_runtime/adapters/managers/container.py`, remove the `if config.network:` wrapper (line ~69) keeping only its inner body (the `if config.network == NetworkMode.CONTAINER: ... elif config.network != NetworkMode.BRIDGE: ...` block). Remove the `if config.restart_policy:` wrapper (line ~79) keeping only `if config.restart_policy != RestartPolicy.NO: cmd.extend(["--restart", str(config.restart_policy)])`. The `StrEnum` members are always truthy so the outer guards were dead/misleading.
^- [x] 5.4 **Fix `logs(follow=True)` exception scope** (design D-C). In `src/oci_runtime/adapters/managers/container.py` `_run`, change `except BaseException as e:` to `except Exception as e:` so `KeyboardInterrupt`/`SystemExit` propagate.
^- [x] 5.5 **Fix `CliBaseManager` generic bound and `type[...]`** (design D-B6, D-C). In `src/oci_runtime/adapters/managers/base.py`: change `P = TypeVar("P")` to `P = TypeVar("P", bound=ContainerParser | ImageParser | VolumeParser | NetworkParser)` (import the four parser ABCs from `oci_runtime.ports.parsers`). Change `not_found: Type[OciError] | None = None` to `not_found: type[OciError] | None = None`. Remove the now-unused `Type` import. Evidence: `proto_b2_b6_caps_generic.py`.
^- [x] **Verify 5:** `uv run pytest tests/unit/adapters/test_cli_container_manager.py tests/unit/adapters/test_cli_image_manager.py tests/unit/wiring/test_manager_commands.py -q` passes; then `PYTHONPATH=src:. uv run python /tmp/opencode/oci-audit-prototypes/proto_a2_exec.py /tmp/opencode/oci-audit-prototypes/proto_a5_pull.py` — all OK.

## 6. Factory and provider DI (B5, C)

^- [x] 6.1 **Add `tty_detector_factory` and `output_stream_factory` to `RuntimeFactoryConfig`** (design D-B5). In `src/oci_runtime/factory.py`, add two fields to the `RuntimeFactoryConfig` dataclass:
  ```python
  tty_detector_factory: Callable[[], "TtyDetector"] | None = None
  output_stream_factory: Callable[[], "OutputStream"] | None = None
  ```
  Import `TtyDetector` from `oci_runtime.ports.tty` and `OutputStream` from `oci_runtime.ports.output_stream`. In `_resolve_config`, add defaults: `if cfg.tty_detector_factory is None: replacements["tty_detector_factory"] = lambda: StdoutTtyDetector()` (import inside the function to avoid adapter import at module load), and the same for `output_stream_factory` → `lambda: StdoutBufferStream()`.
^- [x] 6.2 **Thread the factories through `RuntimeProvider.create_managers`** (design D-B5). In `src/oci_runtime/ports/provider.py`, extend the `create_managers` abstract signature with two keyword-only params: `*, tty_detector_factory: Callable[[], TtyDetector], output_stream_factory: Callable[[], OutputStream]` (import the ports). In `src/oci_runtime/adapters/provider/_base.py` `create_managers`, accept the two new kwargs and replace `StdoutTtyDetector()` with `tty_detector_factory()` and `StdoutBufferStream()` with `output_stream_factory()`. In `src/oci_runtime/factory.py` `RuntimeFactory.create`, pass `tty_detector_factory=self._cfg.tty_detector_factory, output_stream_factory=self._cfg.output_stream_factory` to `provider.create_managers(...)`.
^- [x] 6.3 **Cache the `discovery` property** (design D-C). In `src/oci_runtime/factory.py` `RuntimeFactory.__init__`, add `self._discovery: RuntimeDiscovery | None = None`. Change the `discovery` property to:
  ```python
  @property
  def discovery(self) -> RuntimeDiscovery:
      if self._discovery is None:
          self._discovery = self._cfg.discovery_factory(self._cfg.transport_factory)
      return self._discovery
  ```
^- [x] **Verify 6:** `uv run pytest tests/unit/adapters/test_factory.py tests/unit/adapters/test_providers.py tests/unit/wiring/test_factory_wiring.py tests/unit/adapters/test_discovery.py -q` passes. Note: `test_providers.py::test_create_managers_returns_managers` calls `provider.create_managers(transport, streaming, caps)` positionally — update that call site (and any other direct `create_managers` calls in tests) to pass the two new kwargs; see task 9.3.

## 7. Public API (B3)

^- [x] 7.1 **Expand `oci_runtime/__init__.py`** (design D-B3, spec `oci-public-api`). Rewrite `src/oci_runtime/__init__.py` to re-export the full set listed in design D-B3. Structure:
  ```python
  from oci_runtime.domain.enums import ContainerState, NetworkMode, RestartPolicy, RuntimeKind, VolumeMountType
  from oci_runtime.domain.exceptions import (
      ContainerError, ContainerNotFoundError, ContainerRuntimeError, ImageError,
      ImageNotFoundError, NetworkError, NetworkNotFoundError, OciError,
      ParsingError, RuntimeNotAvailableError, VolumeError, VolumeNotFoundError,
  )
  from oci_runtime.domain.types import (
      BuildContext, CancellationToken, ContainerInfo, ExecResult, ImageInfo,
      NetworkInfo, PortMapping, PruneResult, RawExecResult, RunConfig,
      RuntimePreference, VolumeInfo, VolumeMount,
  )
  from oci_runtime.domain.capabilities import RuntimeCapabilities
  from oci_runtime.ports.engine import ContainerEngine
  from oci_runtime.ports.managers import ContainerManager, ImageManager, NetworkManager, VolumeManager
  from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
  from oci_runtime.ports.transport import Transport
  from oci_runtime.ports.streaming import StreamingTransport
  from oci_runtime.ports.tty import TtyDetector
  from oci_runtime.ports.output_stream import OutputStream
  from oci_runtime.ports.discovery import RuntimeDiscovery
  from oci_runtime.ports.provider import RuntimeProvider
  from oci_runtime.factory import RuntimeFactory, RuntimeFactoryConfig
  ```
  Define `__all__` as the sorted list of every name above. Do NOT export any adapter class.
^- [x] **Verify 7:** `uv run python -c "import oci_runtime; assert all(hasattr(oci_runtime, n) for n in oci_runtime.__all__); assert 'CliTransport' not in oci_runtime.__all__; from oci_runtime import RuntimeKind, OciError, ParsingError, PruneResult, ContainerEngine, Transport; print('OK')"` prints `OK`.

## 8. Test mock contract fix (D1, D2, D3)

^- [x] 8.1 **Fix `tests/helpers/mock_parsers.py`** (design D-D1, spec `oci-test-contracts`). Change all four `parse_prune` methods to `return PruneResult()` (import `PruneResult` from `oci_runtime.domain.types`). Remove the `-> dict[str, int]` annotation; use `-> PruneResult`.
^- [x] 8.2 **Fix the 4 local `_MockParser` classes** (design D-D1). In `tests/unit/adapters/test_cli_container_manager.py`, `tests/unit/adapters/test_cli_image_manager.py`, `tests/integration/container/test_tty_dispatch.py`, `tests/unit/wiring/test_factory_wiring.py` (the `FakeContainerParser`/`FakeImageParser`): change each `parse_prune` to `return PruneResult()` and update the `-> dict[str, int]` annotation to `-> PruneResult`.
^- [x] 8.3 **Fix the 5 `result == {...}` assertions** (design D-D1). In `tests/unit/wiring/test_manager_commands.py` (4 occurrences: `test_prune_command` for image/container/volume/network) and `tests/integration/functional/test_workflows.py` (`test_container_prune_returns_real_data`): change `assert result == {"deleted": 0, "reclaimed_bytes": 0}` to `assert result == PruneResult()` (import `PruneResult`).
^- [x] 8.4 **Fix port-test fake signatures** (design D-D2). In `tests/unit/ports/test_managers.py`: change `_Parser.parse_prune` return annotation to `-> PruneResult` and body to `return PruneResult()` (import it). In `_make_transport`'s `T.execute`, remove the `stream=False` parameter (the `Transport.execute` port has no `stream` param).
^- [x] 8.5 **Fix concurrency test tuple keys** (design D-D3). In `tests/unit/boundary/test_concurrency.py` `test_concurrent_manager_calls`: change the `RecordingTransport` and `RecordingStreamingTransport` response keys from the string `"docker container inspect --format json ctr1"` to the tuple `("docker", "container", "inspect", "--format", "json", "ctr1")`.
^- [x] **Verify 8:** `uv run pytest tests/unit/ports/ tests/unit/boundary/test_concurrency.py tests/unit/wiring/test_manager_commands.py -q` passes.

## 9. Boundary test corrections (D4)

^- [x] 9.1 **Fix empty-list boundary tests** (design D-D4, spec `oci-test-contracts`). In `tests/unit/boundary/test_empty_outputs.py` `TestEmptyList`: change all 4 tests (`test_list_containers_empty`, `test_list_images_empty`, `test_list_volumes_empty`, `test_list_networks_empty`) from `with pytest.raises(ParsingError, match="Empty response"): ...` to `result = mgr.list(); assert result == []`. Remove the now-unused `ParsingError` import if it becomes unused (it is still used by `TestEmptyInspect`, so keep it).
^- [x] 9.2 **Fix empty-pull boundary test** (design D-D4, spec `oci-pull-contract`, `oci-test-contracts`). In `tests/unit/boundary/test_empty_outputs.py` `test_pull_empty_stdout`: change from `result = mgr.pull("alpine", timeout=30); assert result == ""` to `with pytest.raises(ImageError): mgr.pull("alpine", timeout=30)`. Import `ImageError` from `oci_runtime.domain.exceptions`.
^- [x] 9.3 **Update direct `create_managers` test call sites** (design D-B5 fallout). Search the tests for `provider.create_managers(` calls that pass only positional `(transport, streaming, caps)` and add `tty_detector_factory=lambda: FakeTtyDetector(), output_stream_factory=lambda: __import__("io").BytesIO()`. Specifically in `tests/unit/adapters/test_providers.py` `test_create_managers_returns_managers` (both Docker and Podman classes). Import `FakeTtyDetector` from `tests.helpers.mock_transport`.
^- [x] **Verify 9:** `uv run pytest tests/unit/boundary/test_empty_outputs.py tests/unit/adapters/test_providers.py -q` passes.

## 10. Test relocation (D6)

^- [x] 10.1 **Move `test_workflows.py` to unit/wiring/** (design D-D6, spec `oci-test-contracts`). `git mv tests/integration/functional/test_workflows.py tests/unit/wiring/test_workflows.py`. Update any relative imports inside the file (it uses `tests.helpers.mock_*` — unchanged since pythonpath is `["src", "."]`). Run the file's tests to confirm.
^- [x] 10.2 **Move `test_tty_dispatch.py` to unit/adapters/** (design D-D6). `git mv tests/integration/container/test_tty_dispatch.py tests/unit/adapters/test_tty_dispatch.py`. Confirm its imports still resolve.
^- [x] 10.3 **Remove now-empty integration dirs** (design D-D6). `rmdir tests/integration/functional tests/integration/container` (after confirming they contain only `__init__.py`/`conftest.py` — `git rm` those). Keep `tests/integration/__init__.py`, `tests/integration/conftest.py`, `tests/integration/outputs/` (empty but harmless), and `tests/integration/smoke/`.
^- [x] **Verify 10:** `uv run pytest tests/unit/wiring/test_workflows.py tests/unit/adapters/test_tty_dispatch.py tests/integration/ -q` passes (smoke tests skip without a runtime).

## 11. Filler/duplicate test deletion (D5)

^- [x] 11.1 **Collapse `tests/unit/domain/test_enums.py`** (design D-D5). Replace the entire file with one parametrized test per enum: a `@pytest.mark.parametrize` over each enum's members asserting `member.value == expected`, plus one test for `ContainerState._missing_` returning `UNKNOWN` for `"deleting"` and `""`. Delete all `test_is_strenum`/`test_strenum_is_str`/`test_strenum_equality_with_str`/`test_strenum_fstring`/`test_str_equality`/`test_str_fstring` tests. Keep `test_is_enum`/`test_is_strenum` collapsed into the parametrized member test.
^- [x] 11.2 **Delete `tests/unit/capability/test_capabilities.py`** (design D-D5). `git rm tests/unit/capability/test_capabilities.py` and `rmdir tests/unit/capability` (duplicates `domain/test_capabilities.py` + `TestCapabilitiesContract`).
^- [x] 11.3 **Trim `tests/unit/domain/test_capabilities.py`** (design D-D5). Delete `TestEngineProfileRemoved` (one-shot regression, no longer relevant). Keep `TestRuntimeCapabilities` and `TestRuntimePreference`.
^- [x] 11.4 **Delete `TestCapabilitiesContract` from `tests/unit/contract/test_interface_compliance.py`** (design D-D5). Remove the entire `TestCapabilitiesContract` class (duplicates the domain test).
^- [x] 11.5 **Delete duplicates/filler from `tests/unit/adapters/test_cli_runtime.py`** (design D-D5). Remove `test_is_available_returns_false_when_probe_returns_false` (duplicate of `test_is_available_false_when_probe_returns_false`). Remove `test_is_available_propagates_memory_error` and `test_version_propagates_assertion_error` (exception-propagation filler).
^- [x] 11.6 **Replace `tests/unit/contract/test_public_api.py`** (design D-D5, D-B3, spec `oci-public-api`). Replace the 10 `test_*_exported` methods with a single `TestPublicAPI` class containing: `test_all_names_importable` (loop `getattr(oci_runtime, n) for n in oci_runtime.__all__`), `test_adapters_not_exported` (assert `"CliTransport"`, `"CliRuntime"`, `"DockerRuntimeProvider"`, `"PodmanRuntimeProvider"` not in `__all__`), and `test_runtime_kind_importable` (the key gap). Import `oci_runtime`.
^- [x] **Verify 11:** `uv run pytest tests/unit/ -q` passes; the count is lower than the original 724 by roughly the number of deleted tests (~30) minus zero new tests yet.

## 12. New behavior tests for uncovered paths (D7)

^- [x] 12.1 **Add `test_exec_non_zero_returns_exec_result`** to `tests/unit/adapters/test_cli_container_manager.py` (spec `oci-exec-semantics`): transport returns `returncode=1, stderr=b""`; assert `result.returncode == 1` and no raise.
^- [x] 12.2 **Add `test_exec_not_found_raises_container_not_found`** to the same file: transport returns `returncode=1, stderr=b"No such container: c1"`; assert `pytest.raises(ContainerNotFoundError)`.
^- [x] 12.3 **Add `test_prune_all_counts_deleted_sha256_lines`** to `tests/unit/adapters/test_parser_base.py` (spec `oci-prune-parsing`): feed `"deleted: sha256:abc123def456\ndeleted: sha256:789012abcdef\nTotal reclaimed space: 1.2GB\n"`; assert `PruneResult(deleted=2, reclaimed_bytes=1288490188)`.
^- [x] 12.4 **Add `test_build_context_forbids_path_and_files`** to `tests/unit/domain/test_types.py` (spec `oci-build-context-validation`): assert `pytest.raises(ValueError, match="context_path")` for `BuildContext(build_file_content="FROM alpine", context_path=Path("/x"), files={"a": b"x"})`.
^- [x] 12.5 **Add `test_pull_unparseable_raises_image_error`** to `tests/unit/boundary/test_error_conditions.py` (spec `oci-pull-contract`): transport returns `returncode=0, stdout=b"random text"`; assert `pytest.raises(ImageError)`.
^- [x] 12.6 **Add `test_run_pty_timeout_raises`** to `tests/unit/adapters/test_cli_pty.py` (spec `oci-pty-timeout`): patch `pty.openpty`/`subprocess.Popen`/`select.select`/`os.read` so the process never exits; call `run_pty(["/bin/sleep","5"], timeout=0.3)`; assert `pytest.raises(subprocess.TimeoutExpired)` and `process.kill` was called.
^- [x] 12.7 **Add `test_transport_caches_which`** to `tests/unit/adapters/test_cli_transport.py` (design D-A7): patch `shutil.which` with a counting side_effect returning `"/usr/bin/docker"`; call `t.get_runtime_binary()` then `t.execute(["docker","ps"])` then `t.execute(["docker","ps"])`; assert `which` called exactly once.
^- [x] 12.8 **Add `test_podman_image_list_string_size`** to `tests/unit/adapters/test_podman_parser.py` (spec implied by A9): feed `[{"Id":"sha256:abc","RepoTags":["alpine:latest"],"Size":"5000000",...}]`; assert `result[0].size == 5000000` and `isinstance(result[0].size, int)`.
^- [x] 12.9 **Add `test_podman_list_malformed_port_skipped`** to `tests/unit/adapters/test_podman_parser.py`: feed a list with `Ports: [{"HostPort":"notanint","ContainerPort":80,...}]`; assert no `ValueError` raised and the port entry is skipped (length 0).
^- [x] 12.10 **Add `test_stream_deadline_token_timeout_cancellation`** to `tests/unit/adapters/test_cli_streaming_transport.py`: construct `CliStreamingTransport("docker")`, patch `shutil.which` + `subprocess.Popen` + `selectors.DefaultSelector` with a mock process whose `stdout.read` yields data slowly; call `s.stream([...], timeout=0.1)`; assert `pytest.raises(subprocess.TimeoutExpired)` and `process.kill` called. This covers `streaming.py` lines 37 + 73.
^- [x] 12.11 **Add `test_build_with_no_cache_and_target_flags`** to `tests/unit/wiring/test_manager_commands.py` (or `test_cli_image_manager.py`): `BuildContext(build_file_content="FROM alpine", no_cache=True, target="stage1")`; assert the recorded command contains `--no-cache` and `--target stage1`.
^- [x] 12.12 **Add `test_build_with_file_path_and_context_path`** to `tests/unit/wiring/test_manager_commands.py`: `BuildContext(build_file_path=Path("/d/Dockerfile"), context_path=Path("/ctx"))`; assert the command uses `-f /d/Dockerfile /ctx` (no stdin). Covers the `image.py` `build_file_path` + `context_path` branch.
^- [x] 12.13 **Add `test_runconfig_invalid_memory_limit_raises` and `test_runconfig_invalid_cpu_limit_raises`** to `tests/unit/domain/test_types.py`: assert `pytest.raises(ValueError)` for `RunConfig(image="x", memory_limit="notalimit")` and `RunConfig(image="x", cpu_limit="abc")`.
^- [x] 12.14 **Add `test_runconfig_cpu_limit_rejects_trailing_dot`** to `tests/unit/domain/test_types.py`: assert `pytest.raises(ValueError)` for `RunConfig(image="x", cpu_limit="1.")` (validates the tightened regex from 2.2).
^- [x] 12.15 **Add `test_parsing_error_importable_from_domain`** to `tests/unit/domain/test_exceptions.py`: `from oci_runtime.domain import ParsingError; from oci_runtime.domain.exceptions import ParsingError as P2; assert ParsingError is P2`.
^- [x] 12.16 **Add `test_custom_tty_detector_factory_is_used` and `test_custom_output_stream_factory_is_used`** to `tests/unit/wiring/test_factory_wiring.py` (design D-B5): construct a `RuntimeFactoryConfig` with `tty_detector_factory=lambda: FakeTtyDetector(is_tty=True)` and `output_stream_factory=lambda: io.BytesIO()`; build the factory; assert `engine.containers._tty_detector` is the `FakeTtyDetector` instance and `engine.containers._output_stream` is the `BytesIO` instance.
^- [x] **Verify 12:** `uv run pytest tests/ -q` — all pass.

## 13. CLI flag safety check (A8)

- [x] 13.1 **Verify `docker network disconnect -f` and `docker volume rm -f`** (design D-A8). Run `docker network disconnect --help` and `docker volume rm --help` (if docker is available; if not, consult docker docs at https://docs.docker.com/reference/). If either short `-f` is unsupported, update `src/oci_runtime/adapters/managers/network.py:38` (`disconnect` force flag) and/or `src/oci_runtime/adapters/managers/volume.py:28` (`volume rm` force flag) to use `--force`. Update the corresponding wiring test's expected command tuple. If both are supported, no change — note the result in the commit message.
^- [x] **Verify 13:** `uv run pytest tests/unit/wiring/test_manager_commands.py -q` passes.

## 14. Docs and version (C-docs)

^- [x] 14.1 **Update `docs/ARCHITECTURE.md`** (design migration plan). In the Module Structure block: rename `ports/capabilities.py` → `domain/capabilities.py`; note `ParsingError` now in `domain/exceptions.py`. In the Exception Hierarchy block: `ParsingError` is already listed under `OciError` — add a note that it lives in `domain/exceptions.py` (re-exported by `ports/parsers.py`). In the "Adding a New Runtime" example: show the `create_managers` call receiving `tty_detector_factory` and `output_stream_factory`. Add a Remediation Log row for this change: `2026-06-21 | A1-A9,B1-B6,C,D1-D7 | Audit remediation (see openspec/changes/oci-runtime-audit-remediation)`. Fix the #3.2 claim ("mock-based tests moved to tests/unit/") — it is now true.
^- [x] 14.2 **Bump version** (design migration plan). In `pyproject.toml`, change `version = "0.1.0"` to `version = "0.2.0"` (breaking changes per semver).
^- [x] **Verify 14:** `uv run ruff check src/ && uv run pytest tests/ -q && uv run python -c "import oci_runtime; print('public API OK', len(oci_runtime.__all__), 'names')"` — all green; the final test count is roughly 724 - 30 (deleted) + 16 (new) ≈ 710, all passing.

## Final verification

- [x] 15.1 **Full suite + coverage + lint.** Run `cd src/shared/oci-runtime && uv run ruff check src/ && uv run pytest tests/ --cov=oci_runtime --cov-report=term-missing -q`. Confirm: ruff clean; all tests pass; coverage ≥ 97% (was 96% with the newly-covered branches); no new uncovered lines in `managers/container.py`, `transport/streaming.py`, `image.py`, `domain/types.py`.
- [x] 15.2 **Re-run every prototype against the patched code** to confirm the fixes are live (not just in the prototypes): `cd src/shared/oci-runtime && for f in /tmp/opencode/oci-audit-prototypes/proto_*.py; do PYTHONPATH=src:. uv run python "$f" || echo "FAIL $f"; done` — every prototype must print only OK lines.
