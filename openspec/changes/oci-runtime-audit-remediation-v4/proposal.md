## Why

A full audit of `oci-runtime` (868 tests passing) contrasted against the git history and the archived v1–v3 specs revealed that the module is **not drifting backward** — the hexagonal layering is clean and the F/A/T regression guards hold. Instead it is **stuck in a circle of incomplete remediations**: three v3 requirements were marked "implemented" in the proposal and specced with scenarios, but the code never honored them and no regression test guards them (A4 auth context, `ProviderNotRegisteredError`, R1 port-side `output_stream`). Around those, a spec-level defect (the prune spec mis-documented Docker's capitalized `Deleted:` output), a fix-created regression (the v2 timeout unification introduced a race that misreports completed ops as `OperationTimeoutError`), a half-finished consistency fix (`parse_size_to_bytes` was relaxed to accept `2GB` but `RunConfig._MEMORY_LIMIT_RE` was not), and several pre-existing bugs masked by missing conformance fixtures (`docker ps` crashes on published ports) all survived three audit cycles undetected. This change closes the circle by finishing the incomplete remediations, correcting the spec-level and fix-created defects, and adding the conformance fixtures that would have caught them.

## What Changes

### Closing incomplete v3 remediations (the circle)
- **A4 (finish)**: `check_cli_result` forwards `command`/`exit_code`/`stderr` to `auth_error` — `ImagePullAccessDeniedError.__init__` already accepts them; only the caller was never wired.
- **ProviderNotRegisteredError (finish)**: add the class to `domain/exceptions.py` (an `OciError` subclass carrying the unknown `RuntimeKind`), wire `RuntimeFactory.create()` to raise it instead of `NotImplementedError`, and re-export it. Make `RuntimeKind` extensible so `RuntimeKind("nerdctl")` does not raise `ValueError` (the documented "Adding a New Runtime" example is currently broken at the enum).
- **R1 port-side (finish)**: `PtyTransport.execute_pty()` port declares `output_stream: OutputStream` (required), matching the adapter and the spec; drop `| None = None`.

### Spec-level & fix-created defects
- **B1 prune capitalization**: `parse_prune_result` `id_pattern` gains `re.IGNORECASE` so Docker's `Deleted: sha256:…` (capital D) is counted. Correct the spec text (which wrongly documented lowercase `deleted:`). Add a real-Docker-prune conformance fixture.
- **H3 timeout race**: before raising `OperationTimeoutError` post-read, all three transports check `process.poll() is not None` — if the child already exited (pipes delivered EOF), return the collected `RawExecResult` instead of misreporting timeout. Introduced by v2's timeout-aware poll loop; closed here.

### Half-finished consistency
- **B3 memory-limit regex**: relax `_MEMORY_LIMIT_RE` to accept two-letter units (`2GB`, `512MB`, `1.5gb`) — the same forms v3 already relaxed `parse_size_to_bytes` to accept. The two size validators now agree.

### Pre-existing bugs masked by missing fixtures
- **B5 Docker list `Ports`-as-string**: `docker ps --format '{{json .}}'` emits `Ports` as a formatted string, not a list of dicts; `_parse_docker_ports_from_list` crashes with `AttributeError`. Add `isinstance(item["Ports"], str)` detection with a regex fallback. Add a docker-container-list-with-ports conformance fixture (currently no list fixture exists at all).
- **B4 `_freeze_mapping` aliasing**: `MappingProxyType(dict(value))` — copy before wrapping so the caller's retained dict cannot mutate a "frozen" instance. The v2 "deep immutability" intent finally holds for mappings.
- **H1 `matches_any_pattern` case**: lowercase the pattern (`re.escape(p.lower())`) to match the lowercased text. Latent today (all patterns are lowercase) but the contract becomes safe for mixed-case patterns.
- **H2 Podman host_port drop**: Podman `_parse_ports` appends bindings unconditionally (mirror Docker) instead of `if host_port:` skipping HostIp-only bindings.

### Pipe-reader port contract (H5, M6, M7)
- **H5**: rename `PipeReader.read()` ABC params to `on_stdout`/`on_stderr` (what callers actually use) and delete the `**kwargs` shim — the port becomes substitutable.
- **M6**: `ProcessPipeReader.from_process` validates both `stdout` and `stderr` and raises the documented `TypeError` (not `AttributeError`) when either lacks `fileno()`.
- **M7**: `_read_fd` narrows `except OSError` to `EIO`-as-EOF only; non-EIO `OSError` re-raises (no more silent EBADF-as-EOF).

### Composition root & port consistency
- **M1 factory type narrowing**: introduce a resolved-config type (or `object.__setattr__` assignment) so `RuntimeFactoryConfig` fields are non-`Optional` after `_resolve_config()` — eliminates 57 mypy "None not callable" / `**dict` errors. Types stop lying.
- **M5 `capabilities` property**: `RuntimeProvider.capabilities` becomes a `@property` to match `ContainerEngine.capabilities` and `provider.kind`.
- **M8 public API gap**: re-export `Parsers`, `ThreadCancellationToken`, `DeadlineCancellationToken`, `compose_tokens` from `oci_runtime/__init__.py` (custom providers and token construction currently force submodule imports, contradicting the "no submodule imports" promise).

### Tests & conformance
- **M9 wiring false-confidence**: swap `Mock*Parser` for real `Docker*Parser` in the `docker_engine` fixture; assert values present in the injected JSON (not the mock's hardcoded constants).
- **M10 no-assertion test**: `test_container_exec_with_options` asserts the emitted command.
- **M11 conformance parity + fixtures**: add Docker-vs-Podman parity assertions; add `container ls` (with ports), `prune`, `build`, and podman `network inspect` fixtures.
- **M12 smoke parity**: parametrize lifecycle tests over docker and podman (skip-if-unavailable); podman engine is currently constructed then never exercised.
- **L20 ruff dead code**: remove the F401/F811/F841 clusters in `test_known_bugs.py` / `test_cli_container_manager.py` / `test_workflows.py`; consolidate the 8 copy-pasted manager-construction factories into a shared helper.

### Cleanup
- **M3 `_utils.py` shim**: delete the stale duplicate `parse_size_to_bytes` + `import *` shadow (the sibling `_tar.py` shim was already deleted in v3; this one was skipped).
- **ARCHITECTURE.md drift**: refresh the adapter tree (omits `binary.py`, `transport/`, `engine/`, `discovery/`, `tty.py`, `output_stream.py`) and the allowed-stdlib list (omits `json`/`types`/`collections.abc` the domain actually imports).

**Retracted**: L18 (`version()` raising plain `OciError`) is **not** a defect — `oci-version-error-contract` explicitly requires it. Excluded from this change.

## Capabilities

### New Capabilities
- `oci-domain-immutability`: deep immutability for mapping-typed domain fields (copy-before-wrap), `PortMapping` range/protocol validation, and `RuntimeCapabilities` tuple-field runtime enforcement.
- `oci-error-matching-correctness`: case-insensitive pattern matching in `matches_any_pattern`, and Docker/Podman not-found pattern parity.
- `oci-docker-list-port-parsing`: `DockerContainerParser.parse_list` correctly parses the `Ports` field emitted by `docker ps --format '{{json .}}'` (string form) without crashing.

### Modified Capabilities
- `oci-result-checker-port`: A4 — auth error carries `command`/`exit_code`/`stderr`.
- `oci-prune-error-propagation`: B1 — `parse_prune_result` counts Docker's capitalized `Deleted:` lines.
- `oci-size-parsing-completeness`: B3 — `RunConfig._MEMORY_LIMIT_RE` accepts the same two-letter unit forms as `parse_size_to_bytes`.
- `oci-pipe-reader-port`: H5 (ABC uses `on_stdout`/`on_stderr`, shim deleted), M6 (`from_process` validates both streams, raises `TypeError`), M7 (`_read_fd` narrows `OSError` to `EIO`-as-EOF).
- `oci-port-binding-strictness`: H2 — Podman inspect preserves HostIp-only bindings (no `host_port` truthiness gate).
- `oci-pty-timeout`: B6 (port `output_stream` required), H3 (post-read timeout raise checks `process.poll()`), H4 (manager does not forward `None` output_stream), M2 (`CliTransport.execute()` kills the child in `finally`).
- `oci-version-error-contract`: `ProviderNotRegisteredError` finally added and raised by `RuntimeFactory.create()`; `RuntimeKind` extensible to new values.
- `oci-parser-real-cli-conformance`: M11 — list/prune/build fixtures, Docker-vs-Podman parity assertions.
- `oci-test-contracts`: M9 (real parsers in wiring), M10 (assert exec command), M12 (smoke parametrized over runtimes), L20 (ruff cleanup + shared manager factory).
- `oci-strict-hexagonal-layering`: M1 (factory resolved-config type narrowing), M5 (`capabilities` property), M8 (public API re-exports).
- `oci-doc-cleanup-v3`: M3 (`_utils.py` shim deleted), ARCHITECTURE.md adapter tree + allowed-stdlib list corrected.

## Impact

- **Domain**: `prune_parsing.py`, `result_checking.py`, `types.py` (`_freeze_mapping`, `_MEMORY_LIMIT_RE`, `PortMapping.__post_init__`), `error_matching.py`, `exceptions.py` (new `ProviderNotRegisteredError`), `enums.py` (`RuntimeKind` extensibility).
- **Ports**: `pty_transport.py` (required `output_stream`), `pipe_reader.py` (renamed params, narrowed `OSError`, strict `from_process`), `provider.py` (`capabilities` property), `capabilities.py` (tuple `__post_init__`), `__init__.py` re-exports.
- **Adapters**: `parser/docker.py` (string-`Ports` parsing), `parser/podman.py` (unconditional binding append, pattern parity), `transport/{cli,streaming,pty}.py` (`process.poll()` check before timeout raise; `cli.py` `finally` kill), `managers/container.py` (required `output_stream`), `binary.py` (no change), `_utils.py` (deleted shim), `factory.py` (resolved-config type narrowing, `ProviderNotRegisteredError`).
- **Public API**: adds `Parsers`, `ThreadCancellationToken`, `DeadlineCancellationToken`, `compose_tokens`, `ProviderNotRegisteredError` to `__all__`. `RuntimeProvider.capabilities` becomes a property (BREAKING, internal — callers using `provider.capabilities()` must drop the parens; the factory is the only internal caller and will be updated).
- **Tests**: ~15–20 new regression tests (one per BUG/H finding) added to `tests/audit/test_known_bugs.py`; conformance fixtures added under `tests/conformance/fixtures/`; wiring fixture rewritten to use real parsers; 87 ruff errors cleared.
- **Dependencies**: None. Stdlib only.
- **Risk**: Low. Each fix is small and locally scoped. The `RuntimeKind` extensibility change is the only one touching enum semantics — mitigated by keeping the existing `DOCKER`/`PODMAN` members and adding a `_missing_` hook or `StrEnum` flexibility for unknown values.
