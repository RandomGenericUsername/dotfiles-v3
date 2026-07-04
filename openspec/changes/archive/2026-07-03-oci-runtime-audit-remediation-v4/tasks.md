## 1. Domain fixes (no I/O, pure)

- [x] 1.1 **B1** — `domain/prune_parsing.py`: add `re.IGNORECASE` to `id_pattern` flags; hoist both compiled patterns to module scope. Add `tests/audit/test_known_bugs.py::TestB01PruneCapitalD` with the capitalized/`Deleted:` scenario.
- [x] 1.2 **B2/A4** — `domain/result_checking.py:24`: forward context to `auth_error` — `raise auth_error(entity, command=cmd, exit_code=result.returncode, stderr=stderr_str)`. Add `TestB02AuthErrorContext` asserting `command`/`exit_code`/`stderr` are populated on the raised `ImagePullAccessDeniedError`.
- [x] 1.3 **B3** — `domain/types.py:30`: relax `_MEMORY_LIMIT_RE` to `^\d+(\.\d+)?[kmg]b?$` (`re.IGNORECASE`). Add `TestB03MemoryLimitTwoLetterUnits` (`2GB`, `512MB`, `1.5gb` accepted; `abc` rejected).
- [x] 1.4 **B4** — `domain/types.py:19-20` `_freeze_mapping`: `MappingProxyType(dict(value))` (copy before wrap). Add `TestB04FreezeMappingNoAlias` asserting source-dict mutation does not leak.
- [x] 1.5 **B4/L4** — `domain/types.py` `PortMapping`: add `__post_init__` validating `0 < container_port <= 65535`, `host_port is None or 0 < host_port <= 65535`, `protocol in ("tcp","udp","sctp")`. Add `TestPortMappingValidation`.
- [x] 1.6 **H1** — `domain/error_matching.py:5-6`: lowercase the pattern — `re.escape(p.lower())`. Add `TestH01MatchesAnyPatternCase` (uppercase pattern matches; lowercase still matches; non-match False).
- [x] 1.7 **L1/L2** — `domain/exceptions.py` `ImagePullAccessDeniedError.__init__` params typed (`command: list[str] | None = None` etc.); `domain/size_parsing.py` `coerce_size(size: str|int|float|None) -> int` and `safe_int(v: object) -> int | None` annotated. (No new test; mypy covers.)
- [x] 1.8 Run `uv run pytest -q tests/unit/domain tests/audit` and `uv run ruff check src/oci_runtime/domain` — green.

## 2. Ports fixes (ABCs + concrete port impls)

- [x] 2.1 **B6/R1** — `ports/pty_transport.py:22`: `output_stream: OutputStream,` (remove `| None = None`). Add `TestB06PtyPortOutputStreamRequired` asserting the port signature has no default.
- [x] 2.2 **H5** — `ports/pipe_reader.py` ABC `read()`: rename `on_primary`/`on_secondary` → `on_stdout`/`on_stderr`; delete the `**kwargs` shim in `ProcessPipeReader.read()`. Add `TestH05PipeReaderSubstitutable` (a no-shim test double works with `on_stdout=`/`on_stderr=`).
- [x] 2.3 **M6** — `ports/pipe_reader.py` `from_process`: validate both `stdout` and `stderr`; add `AttributeError` to the caught tuple (or pre-check) so `stderr=None` raises the documented `TypeError`. Add `TestM06FromProcessStderrNone`.
- [x] 2.4 **M7** — `ports/pipe_reader.py` `_read_fd`: narrow `except OSError` to `errno.EIO`-as-EOF; re-raise non-EIO. Add `TestM07ReadFdNonEioPropagates`.
- [x] 2.5 **M5** — `ports/provider.py`: make `capabilities` a `@property` (match `kind`/`ContainerEngine`). Add `TestM05ProviderCapabilitiesProperty`.
- [x] 2.6 **L8** — `ports/capabilities.py` `RuntimeCapabilities`: add `__post_init__` coercing tuple-typed fields via `object.__setattr__(self, name, tuple(...))`. Add `TestRuntimeCapabilitiesTupleEnforcement`.
- [x] 2.7 **L9** — `ports/cancellation.py` `DeadlineCancellationToken.__del__`: guard with `getattr(self, "_timer", None)`. (No new test; manual partial-init check.)
- [x] 2.8 Run `uv run pytest -q tests/unit/ports tests/audit` and `uv run ruff check src/oci_runtime/ports` — green.

## 3. Adapters fixes (parsers, transports, managers)

- [x] 3.1 **B5** — `adapters/parser/docker.py` `_parse_docker_ports_from_list`: detect `isinstance(item["Ports"], str)` and parse with a regex (`(\S*):?(\d+)->(\d+)/(tcp|udp|sctp)` + bare `(\d+)/(proto)`). Add `TestB05DockerListPortsAsString` (real `docker ps --format '{{json .}}'` shape).
- [x] 3.2 **H2** — `adapters/parser/podman.py:48-62` `_parse_ports`: append unconditionally (mirror Docker), `host_port=int(host_port) if host_port else None`. Add `TestH02PodmanHostIpOnlyBinding`.
- [x] 3.3 **M4** — `adapters/parser/podman.py:26`: add `"no such object"` to `_not_found_patterns` (parity with Docker). Add `TestM04PodmanNotFoundParity`.
- [x] 3.4 **H3** — `adapters/transport/{cli,streaming,pty}.py`: before the post-read `raise OperationTimeoutError`, insert `if process.poll() is not None: return RawExecResult(process.returncode, stdout, stderr)`. Add `TestH03TimeoutRaceCompletedNotMisreported` for each transport (mock reader EOF + deadline already-cancelled + `process.poll()` returning 0 → no raise).
- [x] 3.5 **H4** — `adapters/managers/container.py`: make `output_stream` required OR guard before `execute_pty` and raise `OciError("output_stream required for TTY run")` when `None`. Add `TestH04ManagerNoneOutputStream`.
- [x] 3.6 **M2** — `adapters/transport/cli.py`: add `finally` guard `if process is not None and not _process_reaped: process.kill(); process.wait()` (mirror streaming). Add `TestM02CliTransportFinallyKillsOnException`.
- [x] 3.7 **M3** — delete `adapters/_utils.py` local `parse_size_to_bytes` + `import *` shim; update `tests/audit/test_known_bugs.py:21` import to `from oci_runtime.domain.size_parsing import parse_size_to_bytes`. (Verified by ruff + grep.)
- [x] 3.8 Run `uv run pytest -q tests/unit/adapters tests/audit` and `uv run ruff check src/oci_runtime/adapters` — green.

## 4. Factory & enums & public API

- [x] 4.1 **ProviderNotRegisteredError** — `domain/exceptions.py`: add `class ProviderNotRegisteredError(OciError)` carrying `kind: RuntimeKind`.
- [x] 4.2 **ProviderNotRegisteredError** — `domain/enums.py` `RuntimeKind`: add `_missing_` classmethod returning an ad-hoc member for unknown non-empty values (so `RuntimeKind("nerdctl")` does not raise `ValueError`). Add `TestRuntimeKindExtensible`.
- [x] 4.3 **ProviderNotRegisteredError** — `factory.py:239-243`: replace `NotImplementedError` with `ProviderNotRegisteredError(preference.kind)`. Add `TestProviderNotRegisteredRaised` (`except OciError` catches it).
- [x] 4.4 **M8** — `oci_runtime/__init__.py`: re-export `Parsers`, `ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken`, `compose_tokens`, `ProviderNotRegisteredError` in `__all__`. Add `TestPublicApiReexports`.
- [x] 4.5 **M1** — `factory.py`: introduce `ResolvedRuntimeFactoryConfig` (non-Optional fields) produced by `_resolve_config()` (or `object.__setattr__` assignment), consumed by `create()`. Verify `uv run --with mypy --with pathspec mypy src/oci_runtime/factory.py` reports zero "None not callable" / `**dict` errors.
- [x] 4.6 Update `RuntimeProvider.capabilities` callers in `factory.py` to drop the `()` (property change from 2.5). Run full suite.
- [x] 4.7 Run `uv run pytest -q` and `uv run --with mypy --with pathspec mypy src/oci_runtime` — green, error count drops from 83 toward 0.

## 5. Tests: cleanup + conformance + regression

- [x] 5.1 **L20** — `tests/helpers/`: add a single shared `build_container_mgr`/`build_image_mgr`/`build_volume_mgr`/`build_network_mgr` factory; replace the 8 copy-pasted copies across `test_known_bugs.py`, `test_empty_outputs.py`, `test_malformed_output.py`, `test_error_conditions.py`, `test_interface_compliance.py`, `test_cli_container_manager.py`, `test_tty_dispatch.py`, `test_manager_commands.py`.
- [x] 5.2 **L20** — remove F401/F811/F841 clusters: delete unused `subprocess`/`MockResultChecker`/`MockListExecutor` imports and the duplicate `ContainerRuntimeError` import in `test_known_bugs.py`; delete duplicate `ContainerRuntimeError` + unused mock imports in `test_cli_container_manager.py`; delete unused `t`/`exc`/`runtime` captures in `test_workflows.py`/`test_engine_lifecycle.py`. Verify `uv run ruff check tests/` is clean.
- [x] 5.3 **M9** — `tests/unit/wiring/conftest.py`: swap `Mock*Parser` → real `Docker*Parser` in the `docker_engine` fixture; update `test_workflows.py` and `test_manager_commands.py` inspect/list assertions to assert injected-JSON values (`info.id == "ctr1"` etc.).
- [x] 5.4 **M10** — `tests/unit/wiring/test_workflows.py:282` `test_container_exec_with_options`: add `assert t.calls[0].command == ["docker","exec","-d","-u","root","ctr1","ls"]`.
- [x] 5.5 **L21** — add a mid-flight cancellation test: real `ThreadCancellationToken` cancelled from another thread after the first stdout chunk, asserting the streaming call returns/times out within a bound (use `RecordingStreamingTransport` with a side_effect that cancels then sleeps).
- [x] 5.6 **L22** — replace `MagicMock()` returns in `_NoOp*Parser.parse_inspect` (`test_known_bugs.py`) with real `ContainerInfo`/`ImageInfo`/etc.
- [x] 5.7 **M11** — `tests/conformance/capture.py`: extend to capture `docker container ls` (with a published port), `docker/podman image prune --force` (sentinel image), `build` (`echo FROM alpine | <runtime> build -t conformance -`), and `podman network inspect bridge`. Commit JSON fixtures under `tests/conformance/fixtures/`.
- [x] 5.8 **M11** — `tests/conformance/test_parser_conformance.py`: add `container ls` (assert non-empty `ports`), `prune` (assert `deleted >= 1` with capitalized `Deleted:` for docker), `build` (assert `^sha256:[a-f0-9]{12,64}$`), and podman `network inspect` tests against the new fixtures. Add a docker-vs-podman parity test (`docker_info.id.lstrip("sha256:") == podman_info.id`).
- [x] 5.9 **M12** — `tests/integration/smoke/test_real_runtime.py`: parametrize the lifecycle tests over `live_docker_engine`/`live_podman_engine` (skip-if-unavailable). Remove the podman-only `isinstance` placeholder.
- [x] 5.10 Run `uv run pytest -q` — all green (target: 868 + new regression tests, 0 failures).

## 6. Docs & architecture linter

- [x] 6.1 **ARCHITECTURE.md** — refresh Module Structure tree to list `adapters/binary.py`, `adapters/output_stream.py`, `adapters/tty.py`, `adapters/_utils.py` (or its deletion), `adapters/transport/{cli,streaming,pty}.py`, `adapters/engine/cli.py`, `adapters/discovery/cli.py`.
- [x] 6.2 **ARCHITECTURE.md** — update Domain Layer allowed-stdlib sentence to include `json`, `types`, `collections.abc`.
- [x] 6.3 **ARCHITECTURE.md** — update the "Adding a New Runtime" example to reflect `RuntimeKind("nerdctl")` now working and `ProviderNotRegisteredError` being raised for unregistered kinds; note `Parsers`/cancellation constructors are now in the public API.
- [x] 6.4 **ARCHITECTURE.md** — append a `2026-07-xx oci-runtime-audit-remediation-v4` row to the Remediation Log summarizing the closure of incomplete v3 remediations (A4, ProviderNotRegisteredError, R1 port), the spec/fix-created defects (B1, H3), the consistency fix (B3), and the pre-existing bugs (B4/B5/H1/H2).
- [x] 6.5 Run `uv run pytest -q tests/architecture` — layering linter green (no adapter→adapter, no adapter→factory imports introduced).

## 7. Final verification

- [x] 7.1 `uv run pytest -q` — full suite green (868 prior + new regression/conformance tests, ≤1 skip).
- [x] 7.2 `uv run ruff check .` — zero errors (87 → 0).
- [x] 7.3 `uv run --with mypy --with pathspec mypy src/oci_runtime` — error count reduced from 83 to ≤5 (factory `None not callable` cluster eliminated).
- [x] 7.4 `openspec status --change "oci-runtime-audit-remediation-v4"` — all artifacts done; ready to archive after implementation.
- [x] 7.5 Bump `pyproject.toml` version `0.3.0` → `0.4.0` (semver: additions to public API `__all__` + one internal BREAKING `capabilities` property).
