## Why

A full audit of `src/shared/oci-runtime` surfaced 9 functional bugs (3 silent failures, 1 unreachable code path, 1 wrong-result bug), 6 hexagonal-architecture drifts (exception in the wrong layer, value object in the ports layer, incomplete public API, hardwired adapters at the composition root), and a test suite whose 96% coverage is misleading: the mocks violate the port contracts they claim to enforce, several boundary tests codify bugs as expected behavior, and ~30 tests are structural filler inflating the count. The module ships correctness regressions that its own tests protect from being noticed. This change remediates the audit findings in a single, evidence-backed plan so the hexagon becomes honest.

## What Changes

### Functional bug fixes (with test corrections)
- **BREAKING** `list()` methods return `[]` for an empty JSON array instead of raising `ParsingError`. Empty result is a valid state. Only `inspect()` (single-item) keeps raising on empty. (A1)
- **BREAKING** `exec_container()` returns `ExecResult` with the inner command's exit code on non-zero exits; raises `ContainerNotFoundError` only when the container is missing. `ExecResult.returncode` is no longer dead for failures. (A2)
- `parse_prune()` counts `deleted: sha256:…` lines emitted by `image prune --force --all`; `deleted` is no longer 0 for `--all` runs. (A3)
- **BREAKING** `BuildContext.__post_init__` raises `ValueError` when both `context_path` and `files` are set (an impossible-to-satisfy combination that currently silently drops `files`). (A4)
- `pull()` raises `ImageError` when no image id can be parsed from output, instead of silently returning `""`. (A5)
- `run_pty()` gains a `timeout: float | None` parameter enforcing a wall-clock deadline via `select` timeout; a hung PTY container run no longer blocks forever. (A6)
- `CliTransport` caches the `shutil.which` result so `get_runtime_binary()` + `execute()` no longer double-probe the binary on every operation. (A7)
- Podman parser consistency: `PodmanImageParser.parse_list` coerces string `Size` to `int` (matching Docker); `PodmanContainerParser._parse_ports_from_list` guards `int()` so a malformed port value is skipped instead of crashing with `ValueError`. (A9)
- `parse_size_to_bytes` uses `re.fullmatch` (no substring matches), adds single-letter units `K/M/G/T` and `TIB` for consistency, keeps rejecting bare numbers. (C)

### Hexagonal architecture corrections
- **BREAKING** `ParsingError` moves from `ports/parsers.py` to `domain/exceptions.py` (it is an `OciError` subclass and belongs with the exception hierarchy). `ports/parsers.py` re-exports it for backward compatibility; `domain/__init__.py` exports it. (B1)
- **BREAKING** `RuntimeCapabilities` moves from `ports/capabilities.py` to `domain/capabilities.py` (it is a pure frozen value object, not an interface). `ports/capabilities.py` is removed; all import sites updated. `ports/engine.py` and `ports/provider.py` import it from `domain` (ports→domain is allowed). (B2)
- `oci_runtime/__init__.py` re-exports the full domain layer (enums, exceptions including `ParsingError`, all types including `PruneResult`/`RawExecResult`/`CancellationToken`) plus the port ABCs (`ContainerEngine`, the four manager ABCs, the four parser ABCs, `Transport`, `StreamingTransport`, `TtyDetector`, `OutputStream`, `RuntimeDiscovery`, `RuntimeProvider`). Adapter classes stay unexported. (B3)
- `RuntimeFactoryConfig` gains `tty_detector_factory: Callable[[], TtyDetector] | None` and `output_stream_factory: Callable[[], OutputStream] | None`, defaulted to `StdoutTtyDetector`/`StdoutBufferStream`. `BaseCliRuntimeProvider.create_managers` receives and uses them instead of hardwiring the concrete adapters. (B5)
- `CliBaseManager` generic `P` is bounded to `ContainerParser | ImageParser | VolumeParser | NetworkParser`. (B6)
- `CliRuntime.is_available()` and `version()` use a single availability path through the cached transport. (B4)

### Code quality
- `RunConfig.__post_init__` invalid `memory_limit`/`cpu_limit` branches get dedicated tests (currently uncovered). `cpu_limit` regex tightened to reject `"1."`. (C)
- `container.py` dead `if config.network:` / `if config.restart_policy:` outer guards removed (the `StrEnum` is always truthy; the inner `!= NO/BRIDGE` checks are the real logic). (C)
- `logs(follow=True)` catches `Exception` instead of `BaseException` (no longer swallows `KeyboardInterrupt`/`SystemExit`); errors re-raised from the generator. (C)
- `base.py` `Type[OciError]` → `type[OciError]`. (C)
- `factory.py` `discovery` property caches the `RuntimeDiscovery` instance. (C)

### Test quality
- All mock `parse_prune` implementations (in `tests/helpers/mock_parsers.py` and 4 local `_MockParser` classes) return `PruneResult` instead of `dict`; the 5 wiring/functional assertions `result == {"deleted":0,...}` become `result == PruneResult()`. (D1)
- Port-test fake signatures fixed: `tests/unit/ports/test_managers.py` `_Parser.parse_prune` returns `PruneResult`; `_make_transport`'s `execute` drops the non-existent `stream=` param. (D2)
- `test_concurrency.py` response keys converted from string to `tuple` so they actually match `RecordingTransport`; the test then proves concurrent inspect works against real canned responses, not just list-append thread-safety. (D3)
- Boundary tests that codify bugs rewritten: empty-list tests assert `[]`; empty-pull test asserts `ImageError`. (D4)
- ~30 filler/duplicate tests deleted; one canonical frozen-dataclass test retained; per-enum language-feature tests collapsed to one parametrized test; `test_public_api` replaced with a single `__all__` membership + import test. (D5)
- Mock-based tests relocated: `tests/integration/functional/test_workflows.py` → `tests/unit/wiring/test_workflows.py`; `tests/integration/container/test_tty_dispatch.py` → `tests/unit/adapters/test_tty_dispatch.py`. `tests/integration/` retains only `smoke/` (real runtime, skip-if-absent). (D6)
- New tests added for the previously-uncovered paths that hid bugs: `exec_container` non-zero, `DeadlineCancellationToken` timeout-cancellation in `stream()`, `build` with `build_file_path` + `context_path`, `--no-cache`/`--target` build flags, `run_pty` timeout, parser string-size coercion, malformed-port skipping. (D7)

### CLI flag safety
- `network disconnect -f` and `volume rm -f` verified/adjusted against the docker CLI grammar in the design phase (no code change unless the design check flags an incompatibility). (A8)

## Capabilities

### New Capabilities
- `oci-list-semantics`: Defines the empty-result contract for `list()` methods across all four managers and the `_parse_json_list`/`_parse_json_item` split.
- `oci-exec-semantics`: Defines the `exec_container()` failure model — return `ExecResult` on non-zero, raise `ContainerNotFoundError` only on missing container.
- `oci-prune-parsing`: Defines `parse_prune()` counting for both bare-hex and `deleted: sha256:` line formats, including the `--all` case.
- `oci-build-context-validation`: Defines `BuildContext` field-combination rules, including the forbidden `context_path` + `files` combination.
- `oci-pull-contract`: Defines `pull()` return contract — returns a non-empty id string or raises `ImageError`.
- `oci-pty-timeout`: Defines the `run_pty()` timeout contract.
- `oci-public-api`: Defines the set of names re-exported by `oci_runtime/__init__.py` and the rule that adapters are not exported.
- `oci-test-contracts`: Defines the rules mock helpers and tests must follow to conform to port contracts (return types, no extra params, tuple response keys).

### Modified Capabilities
<!-- No existing specs in openspec/specs/; this is the first spec-driven change for this module. -->

## Impact

- **Code**: ~20 source files under `src/shared/oci-runtime/src/oci_runtime/` (domain, ports, adapters, factory, `__init__`). No new runtime dependencies (`pyproject.toml` stays dependency-free).
- **Tests**: ~45 test files under `src/shared/oci-runtime/tests/`; net test count decreases (~30 filler deleted, ~15 new behavior tests added).
- **Public API**: **BREAKING** for consumers relying on (1) `list()` raising on empty, (2) `exec_container()` raising on non-zero, (3) `BuildContext(context_path=..., files=...)` silently dropping files, (4) `pull()` returning `""`, (5) `ParsingError`/`RuntimeCapabilities` import paths. All other exports are additive.
- **Architecture**: `domain/` gains `capabilities.py` and absorbs `ParsingError`; `ports/` loses `capabilities.py`. Dependency direction stays acyclic (verified by prototype `proto_b1`, `proto_b2`).
- **Docs**: `docs/ARCHITECTURE.md` updated to reflect the moves, the new factory hooks, and the corrected test layout (the "#3.2 mock-based tests moved to tests/unit/" claim becomes true).
- **Evidence**: All fixes validated by executable prototypes in `/tmp/opencode/oci-audit-prototypes/` (referenced per-finding in design.md).
