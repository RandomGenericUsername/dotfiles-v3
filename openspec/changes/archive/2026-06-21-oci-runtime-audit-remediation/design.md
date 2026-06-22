## Context

`src/shared/oci-runtime` is a runtime-agnostic OCI container management module claiming hexagonal architecture (domain → ports → adapters → factory). A full audit read all 29 source files and ~45 test files, ran the suite (724 passed, ruff clean, 96% line coverage), and empirically verified 9 functional bugs and 6 architecture drifts via executable prototypes in `/tmp/opencode/oci-audit-prototypes/`. The misleading part: several bugs are locked in as "correct" by the tests, and the mock helpers violate the very port contracts the contract-tests enforce. This change remediates every audit finding.

Current state constraints:
- Python 3.12+ (`StrEnum`, `type[...]` PEP 585), zero runtime dependencies.
- Existing public consumers reachable via `from oci_runtime import ...` — the public API surface is part of the contract.
- The repo uses OpenSpec spec-driven changes; this is the first spec for the module (no existing `openspec/specs/`).
- All 8 architecture/semantic decisions were resolved with the maintainer via gated questions (see "Decisions" — each cites the chosen option).

## Goals / Non-Goals

**Goals:**
- Fix all 9 functional bugs (A1–A9) with evidence-backed patches.
- Restore honest hexagonal layering: `ParsingError` and `RuntimeCapabilities` in `domain/`; `ports/` contains only ABCs; composition root (`RuntimeFactoryConfig`) exposes hooks for every adapter it wires.
- Make the public API sufficient to use the module without submodule dives.
- Make the test suite conform to the port contracts it asserts (mocks return correct types; no extra params; tuple response keys); delete filler; relocate mock-based "integration" tests to `unit/`.
- Every fix validated by an executable prototype before being specified.

**Non-Goals:**
- Adding new runtimes (nerdctl, containerd) — out of scope; the provider extension mechanism already exists.
- Adding new manager operations (e.g. `stats`, `top`, `events`) — out of scope.
- Rewriting the transport/streaming layer — only targeted fixes (caching, timeout, cancellation test coverage).
- Changing the `docker`/`podman` CLI command vocabulary beyond the flagged `disconnect -f` / `volume rm -f` safety check.
- Performance optimization beyond eliminating the double `shutil.which` probe.
- E2E tests requiring a real runtime beyond the existing skipped smoke tests.

## Decisions

Each decision cites the resolved option from the maintainer gating round and the prototype that validates it.

### D-A1: Empty `list()` result is valid → returns `[]`
**Chosen:** `_parse_json_list` returns `[]` for an empty JSON array; only `_parse_json_item` (inspect) keeps raising `ParsingError` on empty.
**Why:** The port declares `-> list[...]`; an empty list is a valid runtime state (zero containers). The current `if not data: raise` treats `[]` (falsy) as malformed.
**Evidence:** `proto_a1_empty_list.py` — 5/5 cases pass: `parse_list('[]')` → `[]`, `parse_list('')` still raises, NDJSON unaffected, `_parse_json_item('[]')` still raises.
**Alternatives rejected:** Keep raising (treats a normal empty runtime as an error — inconsistent with the return type).
**Test impact:** 4 boundary tests (`test_empty_outputs.py::TestEmptyList`) flip from asserting `ParsingError` to asserting `[]`.

### D-A2: `exec_container` returns `ExecResult` on non-zero; raises only on not-found
**Chosen:** Remove `_check_result` from `exec_container`; replace with a not-found-only check: on non-zero exit, inspect stderr via `parser.is_not_found_error` and raise `ContainerNotFoundError` if matched, otherwise return `ExecResult(returncode, stdout, stderr)`.
**Why:** `ExecResult.returncode` exists to surface the inner command's exit code. `docker exec false` returning exit 1 is normal output, not a runtime error. Other managers raise not-found; exec should match that pattern for the missing-container case only.
**Evidence:** `proto_a2_exec.py` — model (b): `exec false` → `ExecResult(returncode=1)` no raise; not-found → `ContainerNotFoundError(container_id='c1')`; success → `ExecResult(returncode=0, stdout='ok\n')`.
**Alternatives rejected:** (a) drop checks entirely (loses typed not-found detection); (b) status quo (`returncode` dead for failures).
**Test impact:** Add `test_exec_non_zero_returns_exec_result`; existing exec tests (all use `returncode=0`) unchanged.

### D-A3: `parse_prune` counts `deleted: sha256:…` lines
**Chosen:** Change `id_pattern` from `r"^[a-f0-9]{12,64}$"` to `r"^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$"` (multiline). Bare-hex and `deleted: sha256:` both counted; no false positives from prose (line-anchored).
**Why:** `image prune --force --all` emits `deleted: sha256:…` lines that the current regex misses, reporting `deleted=0`.
**Evidence:** `proto_a3_prune_all.py` — 5/5 cases: `--all` → `deleted=2` (was 0), normal unchanged, empty unchanged, prose no false positive, no-reclaimed-line works.
**Test impact:** Add `test_prune_all_counts_deleted_sha256_lines` to `test_parser_base.py`.

### D-A4: Forbid `BuildContext(context_path=..., files=...)`
**Chosen:** `BuildContext.__post_init__` raises `ValueError` when both `context_path` and `files` are non-empty. Clear message naming the two incompatible fields and the two valid alternatives.
**Why:** `docker build -f - PATH` takes context from the PATH; in-memory `files` cannot be injected in the same invocation, so they are silently dropped today. This is a CLI limitation, not a code bug — the API must make it impossible to express.
**Evidence:** `proto_a4_build_context.py` — option X: the combo raises `ValueError`; path-without-files allowed; (option Y "files wins" rejected as silent override).
**Alternatives rejected:** files-wins (silent override of an explicit field); status quo (silent data loss).
**Test impact:** Add `test_build_context_forbids_path_and_files` to `test_types.py`; existing build tests (no `files`+`path` combo) unchanged.

### D-A5: `pull()` raises `ImageError` on unparseable output
**Chosen:** `ImageManager.pull()` checks the parser's return; if `parse_id_from_pull` returns `""`, raise `ImageError(message="Could not parse image id from pull output", stderr=<raw stdout>)`. The parser methods themselves are unchanged (they already return `""` as a sentinel).
**Why:** The port contract is `-> str` (an image id); `""` is an undetectable silent failure. Raising a typed `ImageError` lets callers catch it uniformly with other image failures.
**Evidence:** `proto_a5_pull.py` — docker Digest line → `sha256:abc123`; empty → `ImageError`; unparseable → `ImageError`; podman → `sha256:def456`.
**Test impact:** `test_empty_outputs.py::test_pull_empty_stdout` flips from asserting `result == ""` to asserting `pytest.raises(ImageError)`.

### D-A6: `run_pty()` gains `timeout`
**Chosen:** Add `timeout: float | None = None` to `run_pty()`. Compute `remaining = max(0, timeout - elapsed)` each loop; `select` timeout = `min(0.1, remaining)`; when `remaining == 0`, kill the process, wait, raise `subprocess.TimeoutExpired(command, timeout)`. The `CliContainerManager.run()` TTY path passes `timeout` through from a new optional `RunConfig`-independent kwarg (see D-A6-detail below).
**Why:** The non-TTY `stream()` path supports timeouts; the TTY path blocks forever on a hung container. Inconsistent liveness guarantee.
**Evidence:** `proto_a6_a7_pty_probe.py` — `run_pty(["/bin/sleep","5"], timeout=0.3)` → `TimeoutExpired`; `run_pty(["/bin/echo","hi"], timeout=5)` → `returncode=0`.
**D-A6-detail (no new decision, just specification):** `CliContainerManager.run()` does NOT add a `timeout` kwarg in this change (the `run` command's timeout semantics for detached containers are out of scope — Non-Goal). The `run_pty` timeout is exposed for direct callers of `run_pty` and for a future `run` timeout. `run_pty`'s default `timeout=None` preserves current behavior.
**Test impact:** Add `test_run_pty_timeout_raises` to `test_cli_pty.py`.

### D-A7: `CliTransport` caches `shutil.which`
**Chosen:** Add `self._which_cache: str | None | NotProbed = _NOT_PROBED` sentinel. `_ensure_binary` checks the cache; on first call runs `shutil.which` and stores the result (path or `None`); subsequent calls skip the syscall. A cached `None` re-raises `RuntimeNotAvailableError` without re-probing (the binary won't appear mid-process; if the caller wants to re-probe they construct a new transport).
**Why:** Every manager call does `get_runtime_binary()` (`_ensure_binary`) + `execute()` (`_ensure_binary`) → 2 `shutil.which` syscalls per op. Caching cuts to 1 per transport lifetime.
**Evidence:** `proto_a6_a7_pty_probe.py` — `CachedCliTransport` → `shutil.which` called 1× across 3 operations (was 2× per op); missing binary still raises `RuntimeNotAvailableError`.
**Test impact:** Add `test_transport_caches_which` to `test_cli_transport.py` asserting `which` call count.

### D-A8: CLI flag safety check (no code change unless flagged)
**Chosen:** In the design-check task, verify `docker network disconnect -f` and `docker volume rm -f` against the docker CLI grammar (man pages / `--help`). If either is unsupported, switch to the long form (`--force`). No speculative code change now.
**Why:** Flagged as a risk in the audit but not empirically confirmed; a design-check task gates any code change.
**Test impact:** If a change is needed, add a unit test asserting the flag form in the recorded command.

### D-A9: Podman parser consistency with Docker parser
**Chosen:** (1) Extract a `coerce_size(size) -> int` helper into `BaseCliParser`; use it in both `DockerImageParser.parse_list` (replacing the inline try/except blocks) and `PodmanImageParser.parse_list` (which currently lacks coercion). (2) Extract `safe_int(v) -> int | None` and use it in `PodmanContainerParser._parse_ports_from_list` so a malformed port value is skipped (matching the docker inspect parser's `try/except (ValueError, AttributeError): continue`).
**Why:** Podman returning `Size` as a string currently produces `ImageInfo.size: str`, violating the typed field. A malformed port value crashes the list parser with `ValueError` instead of being skipped.
**Evidence:** `proto_a9_podman_parser.py` — current podman `Size='5000000'` → `str`; docker → `int`. `coerce_size` unifies. Current podman bad port → `ValueError` crash; `safe_int` skips.
**Test impact:** Add `test_podman_image_list_string_size` and `test_podman_list_malformed_port_skipped` to `test_podman_parser.py`.

### D-B1: `ParsingError` moves to `domain/exceptions.py`
**Chosen:** Move the `ParsingError` class definition from `ports/parsers.py` to `domain/exceptions.py` (next to the other `OciError` subclasses). `ports/parsers.py` keeps `from oci_runtime.domain.exceptions import ParsingError` and includes it in `__all__` (re-export for backward compatibility). `domain/__init__.py` exports `ParsingError`.
**Why:** `ParsingError` is an `OciError` subclass; `ARCHITECTURE.md` lists it in the domain exception tree. An exception sitting in the ports layer is a layering inversion.
**Evidence:** `proto_b1_parsing_error_move.py` — imports cycle-free; `ports.parsers` re-export works; `domain` and public api import clean. The move adds zero new module edges (`ParsingError` needs only `OciError`, same module).
**Test impact:** Existing `from oci_runtime.ports.parsers import ParsingError` keeps working (re-export). Add `test_parsing_error_importable_from_domain`.

### D-B2: `RuntimeCapabilities` moves to `domain/capabilities.py`
**Chosen:** Move `RuntimeCapabilities` from `ports/capabilities.py` to `domain/capabilities.py`. Delete `ports/capabilities.py`. Update import sites: `ports/engine.py`, `ports/provider.py`, `ports/aggregates.py` (if it imports caps — it doesn't), `adapters/provider/_base.py`, `adapters/managers/base.py`, `adapters/managers/*.py`, `adapters/engine/cli.py`, `factory.py`, `tests/helpers/*`, conftests. `ports/`→`domain/` imports are allowed (ports depend on domain).
**Why:** `RuntimeCapabilities` is a pure frozen dataclass (value object), not an interface. Ports layer must contain only ABCs.
**Evidence:** `proto_b2_b6_caps_generic.py` — source imports only `dataclass`/`field`; no `from oci_runtime` edges; move adds no domain→ports edges.
**Test impact:** Update import paths in ~6 test files; behavior unchanged.

### D-B3: Public API exports full domain + key ports
**Chosen:** `oci_runtime/__init__.py` re-exports:
- All domain enums: `RuntimeKind`, `ContainerState`, `RestartPolicy`, `NetworkMode`, `VolumeMountType`.
- All domain exceptions: `OciError`, `ContainerError`, `ContainerRuntimeError`, `ContainerNotFoundError`, `ImageError`, `ImageNotFoundError`, `VolumeError`, `VolumeNotFoundError`, `NetworkError`, `NetworkNotFoundError`, `RuntimeNotAvailableError`, `ParsingError`.
- All domain types: `BuildContext`, `RunConfig`, `ContainerInfo`, `ImageInfo`, `VolumeInfo`, `NetworkInfo`, `PortMapping`, `VolumeMount`, `PruneResult`, `ExecResult`, `RawExecResult`, `RuntimePreference`, `CancellationToken`.
- `RuntimeCapabilities` (now from domain).
- Port ABCs: `ContainerEngine`, `ImageManager`, `ContainerManager`, `VolumeManager`, `NetworkManager`, `ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`, `Transport`, `StreamingTransport`, `TtyDetector`, `OutputStream`, `RuntimeDiscovery`, `RuntimeProvider`.
- `RuntimeFactory`, `RuntimeFactoryConfig`.
- Adapters are NOT exported (implementation detail).
**Why:** Currently `RuntimeKind` (required to build a `RuntimePreference`) and the entire exception hierarchy are not exported; users dive into submodules.
**Evidence:** `proto_b1_parsing_error_move.py` — `import oci_runtime` is cycle-free with the full re-export set.
**Test impact:** Replace `test_public_api.py` (10 `is not None` tests) with one `test_public_api_surface` asserting `__all__` membership and that every name imports.

### D-B4: Single availability path
**Chosen:** `CliRuntime.is_available()` → `transport.probe()` (unchanged). `CliRuntime.version()` → `transport.get_runtime_binary()` + `transport.execute([...,"--version"])` (unchanged). Both now benefit from the cached `_ensure_binary` (D-A7). No semantic change to the methods; the decision is "do not unify them into one method" — they answer different questions ("is it there" vs "what version").
**Why:** The audit flagged double-probing; D-A7's cache resolves the performance issue without merging two semantically distinct methods.
**Test impact:** None beyond D-A7's test.

### D-B5: Factory hooks for `TtyDetector` and `OutputStream`
**Chosen:** Add to `RuntimeFactoryConfig`:
```
tty_detector_factory: Callable[[], TtyDetector] | None = None
output_stream_factory: Callable[[], OutputStream] | None = None
```
Defaults resolved in `_resolve_config` to `lambda: StdoutTtyDetector()` and `lambda: StdoutBufferStream()`. `RuntimeFactory.create()` passes `cfg.tty_detector_factory` and `cfg.output_stream_factory` to `provider.create_managers(...)` (extend the method signature). `BaseCliRuntimeProvider.create_managers` calls the factories and passes results to `CliContainerManager`.
**Why:** The composition root must expose every adapter it wires. Currently TTY/output-stream injection requires bypassing the factory.
**Evidence:** No prototype needed — straightforward DI extension; import direction verified in `proto_b2_b6` (factories produce port instances, no new edges).
**Test impact:** Extend `test_factory_wiring.py::TestFactoryConfigInjection` with `test_custom_tty_detector_factory_is_used` and `test_custom_output_stream_factory_is_used`. Update `RuntimeProvider.create_managers` contract test signatures.

### D-B6: Bounded generic `P`
**Chosen:** `P = TypeVar("P", bound=ContainerParser | ImageParser | VolumeParser | NetworkParser)` in `adapters/managers/base.py`.
**Why:** Unbounded `P` accepts any object as the parser, weakening type safety.
**Evidence:** `proto_b2_b6_caps_generic.py` — `TypeVar('P', bound=ParserUnion)` accepted on 3.12+.
**Test impact:** None (type-only; existing concrete managers already use valid parser types).

### D-C: Code quality fixes
- `RunConfig.__post_init__`: keep existing regexes; add tests for the two uncovered raise branches; tighten `_CPU_LIMIT_RE` from `r"^\d+\.?\d*$"` to `r"^\d+(\.\d+)?$"` (rejects `"1."`).
- `container.py`: remove the dead `if config.network:` (line 69) and `if config.restart_policy:` (line 79) outer guards — `StrEnum` members are always truthy; the inner `!= NetworkMode.BRIDGE` / `!= RestartPolicy.NO` checks are the real logic.
- `logs(follow=True)`: change `except BaseException` → `except Exception` in `_run` (no longer swallows `KeyboardInterrupt`/`SystemExit`).
- `base.py`: `Type[OciError]` → `type[OciError]` (PEP 585).
- `factory.py`: cache `self._discovery` on first access in the `discovery` property.
- `image.py`: `parse_build_output` returning `"sha256:"` for empty input is kept (the parser is a best-effort extractor; the caller's `build()` does not validate the id — that's a separate concern, Non-Goal). Document the behavior in the parser docstring.
- `image.py`: `if not size:` → `if size == 0:` to avoid treating a legitimate `0` as falsy when `VirtualSize` fallback is intended (edge case; keep the fallback only when `size is None or size == 0`).

### D-D1: Mocks return `PruneResult`
**Chosen:** `tests/helpers/mock_parsers.py`: all four `MockXxxParser.parse_prune` return `PruneResult()` instead of `{"deleted":0,"reclaimed_bytes":0}`. The 4 local `_MockParser` classes in `test_cli_container_manager.py`, `test_cli_image_manager.py`, `test_tty_dispatch.py`, `test_factory_wiring.py` updated identically. The 5 assertions `result == {"deleted":0,...}` (in `test_manager_commands.py` ×4 and `test_workflows.py` ×1) become `result == PruneResult()`.
**Why:** The port declares `-> PruneResult`; mocks must conform or the contract tests are theater.
**Evidence:** `proto_d1_mock_contract.py` — fixed mock returns `PruneResult`; `PruneResult() == PruneResult()` is True; `PruneResult() == dict` is False (so the assertions must change).

### D-D2: Port-test fake signatures fixed
**Chosen:** `tests/unit/ports/test_managers.py`: `_Parser.parse_prune` return type `-> PruneResult` and returns `PruneResult()`; `_make_transport`'s `execute` drops the `stream=False` param.
**Why:** The port tests themselves must conform to the port contract.

### D-D3: Concurrency test uses tuple keys
**Chosen:** `tests/unit/boundary/test_concurrency.py`: change `RecordingTransport` / `RecordingStreamingTransport` response keys from `"docker container inspect --format json ctr1"` (string) to `("docker","container","inspect","--format","json","ctr1")` (tuple), matching `RecordingTransport.execute`'s `tuple(command)` lookup. The test then proves concurrent inspect works against real canned responses.
**Why:** Currently the response is never matched; the test only proves `list.append` is thread-safe.

### D-D5: Delete ~30 filler/duplicate tests
**Chosen (concrete list, not left to the implementer):**
- `tests/unit/domain/test_enums.py`: collapse to one parametrized test per enum verifying members + `_missing_` fallback for `ContainerState`. Delete the ~25 `test_is_strenum`/`test_strenum_is_str`/`test_strenum_equality_with_str`/`test_strenum_fstring`/`test_str_equality`/`test_str_fstring` tests (they test the `StrEnum` language feature).
- `tests/unit/capability/test_capabilities.py`: delete the file entirely (duplicates `domain/test_capabilities.py` and `TestCapabilitiesContract`).
- `tests/unit/domain/test_capabilities.py`: keep `TestRuntimeCapabilities` (defaults, custom values, new-list-each-time) and `TestRuntimePreference`; delete `TestEngineProfileRemoved` (one-shot regression test, no longer needed).
- `tests/unit/contract/test_interface_compliance.py::TestCapabilitiesContract`: delete (duplicates the domain test).
- `tests/unit/adapters/test_cli_runtime.py`: delete `test_is_available_returns_false_when_probe_returns_false` (duplicate of `test_is_available_false_when_probe_returns_false`); delete `test_is_available_propagates_memory_error` and `test_version_propagates_assertion_error` (assert Python propagates exceptions — filler).
- `tests/unit/contract/test_public_api.py`: replace the 10 `test_*_exported` tests with one `test_public_api_surface` (see D-B3).
**Why:** These tests inflate the count without guarding behavior; the audit counted ~30.
**Net count:** ~30 deleted, ~15 behavior tests added → net ~-15.

### D-D6: Relocate mock-based "integration" tests
**Chosen:**
- `tests/integration/functional/test_workflows.py` → `tests/unit/wiring/test_workflows.py` (uses `RecordingTransport`/mock parsers).
- `tests/integration/container/test_tty_dispatch.py` → `tests/unit/adapters/test_tty_dispatch.py` (uses `MagicMock` transport).
- Delete the now-empty `tests/integration/functional/`, `tests/integration/container/` directories (keep `tests/integration/__init__.py`, `tests/integration/conftest.py`, `tests/integration/smoke/`).
**Why:** `ARCHITECTURE.md` #3.2 claims mock-based tests were moved to `tests/unit/` — make the claim true. `tests/integration/` retains only real-runtime tests.

### D-D7: New tests for previously-uncovered paths
**Chosen (concrete list):**
- `test_exec_non_zero_returns_exec_result` (A2)
- `test_prune_all_counts_deleted_sha256_lines` (A3)
- `test_build_context_forbids_path_and_files` (A4)
- `test_pull_unparseable_raises_image_error` (A5)
- `test_run_pty_timeout_raises` (A6)
- `test_transport_caches_which` (A7)
- `test_podman_image_list_string_size` (A9)
- `test_podman_list_malformed_port_skipped` (A9)
- `test_stream_deadline_token_timeout_cancellation` (covers `streaming.py:37,73` — the `DeadlineCancellationToken` path)
- `test_build_with_no_cache_and_target_flags` (covers `image.py:36,38`)
- `test_build_with_file_path_and_context_path` (covers the `build_file_path` + `context_path` branch)
- `test_runconfig_invalid_memory_limit_raises` and `test_runconfig_invalid_cpu_limit_raises` (covers `types.py:95,97`)
- `test_runconfig_cpu_limit_rejects_trailing_dot` (tightened regex)
- `test_parsing_error_importable_from_domain` (B1)
- `test_public_api_surface` (B3)
- `test_custom_tty_detector_factory_is_used`, `test_custom_output_stream_factory_is_used` (B5)

## Risks / Trade-offs

- **[BREAKING changes for existing consumers]** → Mitigation: all 5 breaking changes are behavior corrections (empty list, exec non-zero, build context combo, pull empty, import paths). The `ParsingError` move keeps a re-export in `ports/parsers.py` for one cycle. Document in `docs/ARCHITECTURE.md` Remediation Log. Version bump to `0.2.0`.
- **[`RuntimeCapabilities` move touches ~12 import sites]** → Mitigation: mechanical rename; `proto_b2` verified no new edges; ruff + tests catch any missed import.
- **[`provider.create_managers` signature change (D-B5) breaks `RuntimeProvider` subclassers]** → Mitigation: add the two new params as keyword-only with defaults `tty_detector_factory=lambda: StdoutTtyDetector()`, `output_stream_factory=lambda: StdoutBufferStream()` so external subclassers keep working. Document in `docs/ARCHITECTURE.md` "Adding a New Runtime".
- **[`exec_container` behavior change (A2) may surprise callers who catch `ContainerRuntimeError`]** → Mitigation: callers catching `ContainerRuntimeError` for exec non-zero will stop seeing it; they must check `ExecResult.returncode`. This is the documented correct pattern. Called out in proposal as BREAKING.
- **[Pruning ~30 tests may mask a real regression one of them would have caught]** → Mitigation: every deleted test was audited as either a language-feature test or an exact duplicate; the behavior they appeared to guard is covered by the canonical retained test. No behavior loses coverage.
- **[Relocating test files may break a CI path that references the old path]** → Mitigation: check `Makefile` (`test` target runs `tests/` recursively — unaffected) and any CI config (none found in the module; repo-level CI TBD but the module's `Makefile` is path-agnostic).
- **[`run_pty` timeout uses `select` + wall-clock — not cancelable mid-read]** → Mitigation: acceptable for v1; a `CancellationToken` param for `run_pty` is a Non-Goal (the streaming path already has cancellation).
- **[CLI flag safety (A8) unverified]** → Mitigation: a design-check task runs `docker network disconnect --help` / `docker volume rm --help` before any code change; only changes the flag form if the short `-f` is unsupported.

## Migration Plan

1. Implement in task order (tasks.md) — domain first, then ports, then adapters, then factory, then tests.
2. After each task group, run `uv run pytest tests/ -q` and `uv run ruff check src/`; both must pass before the next group.
3. Update `docs/ARCHITECTURE.md` Remediation Log with the new IDs (A1–A9, B1–B6, C, D1–D7).
4. Bump `pyproject.toml` version `0.1.0` → `0.2.0` (breaking changes).
5. Rollback: each task is a separate commit; revert by commit hash. No data migration involved.

## Open Questions

None — all 8 architecture/semantic decisions were resolved during the gating round. The only remaining check is empirical (D-A8 CLI flag safety), handled as a task rather than an open question.
