## Why

The prior remediation (archived `2026-06-21-oci-runtime-audit-remediation`) marked ~30 tasks `[x]` against ephemeral prototypes in `/tmp/opencode/oci-audit-prototypes/` that no longer exist. At least four marked-complete fixes were never applied to the codebase (`parse_size_to_bytes` single-letter units, B5 wiring tests, `run()` timeout wiring, single-availability-path), and one introduced a test-suite-crashing regression (PTX test closing real FDs). A fresh audit found 42+ issues, 26 of which are now committed as `xfail(strict=True)` reproductions and 7 as conformance xfails anchored to real docker/podman CLI output. This change fixes every finding that has a committed failing test, with the structural guarantee that no task can be marked complete unless its xfail flips to passing — the verification is mechanical, not a judgment call.

## What Changes

### Silent-failure bug fixes (each flips a committed xfail)
- **F1** `exec_container` preserves stderr on success (no longer forces `stderr_str=""` when `returncode==0`). Flips `tests/audit/test_known_bugs.py::TestF01`.
- **F2** `logs(follow=True)` wires `on_stderr` to the queue so container stderr is delivered to the caller. Flips `TestF02`.
- **F3** All four `prune()` methods call `_check_result` before `parse_prune`; a failed prune raises `OciError` instead of returning `PruneResult(0,0)`. Flips `TestF03` (4 tests).
- **F4** `build()` emits `--build-arg`, `--label`, `--pull` flags from `BuildContext` fields that are currently silently dropped. Flips `TestF04` (3 tests).
- **F7** `_check_result` raises the manager's own entity-typed error (not `ContainerRuntimeError`) for generic failures in image/volume/network managers. Flips `TestF07` (3 tests).
- **F8** `_coerce_size` wraps its return in `int()` so float JSON sizes don't leak into `ImageInfo.size: int`. Flips `TestF08`.
- **F9** `parse_size_to_bytes` uses `re.fullmatch`, adds single-letter `K/M/G/T` and `TIB` units, rejects substring matches. Flips `TestF09` (4 tests).
- **F11** `get_runtime_binary()` returns the `shutil.which`-resolved path from `_which_cache`, not the unresolved `self.binary`. Flips `TestF11`.
- **F14** Introduce `OperationTimeoutError(OciError)`; `stream()` and `run_pty` raise it instead of bare `subprocess.TimeoutExpired`. Flips `TestF14`.

### Conformance bugs found by real-CLI fixtures (each flips a conformance xfail)
- **F-CONF-1** `DockerContainerParser.parse_list` coerces string `Names` to `[string]` (real `docker ps --format '{{json .}}'` emits `Names` as a string). Flips `TestContainerListConformance::test_docker_parse_list_produces_container_infos`.
- **F-CONF-2** `PodmanContainerParser.parse_list` guards `Ports: null` before iterating. Flips `test_podman_parse_list_produces_container_infos`.
- **F-CONF-3** `PodmanContainerParser.parse_inspect` coerces `Labels: null` to `{}`. Flips `test_parse_inspect_labels_is_dict[podman]`.
- **F-CONF-4** `DockerVolumeParser.parse_inspect` (and all inspect parsers) coerce `Labels: null` to `{}`. Flips `test_parse_inspect_labels_is_dict[docker]`.
- **F-CONF-5** `PodmanImageParser.parse_id_from_pull` prefixes bare-hex ids with `sha256:`. Flips `test_parse_id_from_pull_returns_sha256[podman]`.

### Architecture and test-quality fixes (no new xfails; verified by existing guardrails)
- **F10** `exists()` stops catching `ParsingError`; only entity-not-found returns False.
- **F15** `RuntimeFactoryConfig` gains `cancellation_factory` field; `BaseCliRuntimeProvider` threads it through.
- **F16** `CliStreamingTransport` and `run_pty` use the cached `shutil.which` from `CliTransport` instead of re-probing.
- **F17** `RunConfig.__post_init__` validates `network==CONTAINER` requires `network_container`, and `detach`+`tty` mutual exclusion (moved from adapter to domain).
- **F19** `ports/__init__.py` drops the residual `RuntimeCapabilities` re-export.
- **F20** `CliBaseManager._not_found_error` default changes from `ContainerRuntimeError` to `OciError` (or a new `GenericRuntimeError`).
- **F21** `RuntimeCapabilities` mutable `list` defaults become `tuple` (true frozen value object).
- **F30** B5 wiring tests (`test_custom_tty_detector_factory_is_used`, `test_custom_output_stream_factory_is_used`) assert the injected instances, not `engine.capabilities is not None`.
- **F34** `test_build_empty_output` asserts `ImageError` instead of codifying `"sha256:"` as valid.
- **F38-F42** Code smells: redundant local import, `_which_cache` type annotation, no-op try/except, `_decode_stdout` naming, tar path sanitization note.

## Capabilities

### New Capabilities
- `oci-prune-error-propagation`: Defines that all four `prune()` methods must call `_check_result` and raise `OciError` on failure, not silently return `PruneResult(0,0)`.
- `oci-build-flag-completeness`: Defines that `build()` must emit `--build-arg`, `--label`, `--pull`, `--network`, `--rm` flags from `BuildContext` fields; no documented field is silently dropped.
- `oci-exception-typing`: Defines that generic manager failures raise the manager's entity-typed error (`ImageError`/`VolumeError`/`NetworkError`), not `ContainerRuntimeError`; timeouts raise `OperationTimeoutError(OciError)`.
- `oci-parser-real-cli-conformance`: Defines that parsers must round-trip real docker/podman CLI output (captured fixtures), including `Names` as string, `Ports: null`, `Labels: null`, and bare-hex pull ids.
- `oci-size-parsing-completeness`: Defines that `parse_size_to_bytes` accepts `K/M/G/T` single-letter units, `TIB`, and uses `re.fullmatch` (no substring matches).

### Modified Capabilities
- `oci-exec-semantics`: `ExecResult.stderr` must preserve real stderr content on success (F1修正).
- `oci-pull-contract`: `parse_id_from_pull` must return `sha256:`-prefixed ids for both docker and podman (F-CONF-5).
- `oci-pty-timeout`: `run()` must pass timeout through to `run_pty`/`stream()` (F5); `OperationTimeoutError` replaces `subprocess.TimeoutExpired` (F14).
- `oci-test-contracts`: B5 wiring tests must assert injected instances, not tautologies (F30); `test_build_empty_output` must assert `ImageError` (F34).

## Impact

- **Code**: ~15 source files under `src/oci_runtime/` (domain exceptions, types, capabilities, adapter base/managers/parsers/transport, factory). New exception class `OperationTimeoutError`. No new runtime dependencies.
- **Tests**: 26 `xfail(strict=True)` tests in `tests/audit/test_known_bugs.py` must flip to `xpassed` → xfail markers removed. 7 conformance xfails in `tests/conformance/` must flip. ~5 existing tests corrected (F30, F34). The `xfail` markers are the verification gate — no task is complete until its marker is removed.
- **Public API**: New export `OperationTimeoutError`. `subprocess.TimeoutExpired` no longer escapes the module. `get_runtime_binary()` returns resolved path (may affect callers that string-compare the binary name). **BREAKING** for callers catching `ContainerRuntimeError` for image/volume/network failures (F7) — they must catch `ImageError`/`VolumeError`/`NetworkError` instead.
- **Architecture**: `RuntimeCapabilities` list fields become tuples (frozen). `RunConfig` gains validation in `__post_init__` (F17). `RuntimeFactoryConfig` gains `cancellation_factory` (F15). The import-direction linter (`tests/architecture/`) and conformance harness (`tests/conformance/`) are already committed and run on every `make check`.
- **Guardrails**: This is the first remediation where every task is tied to a committed test that must flip from `xfailed` to `passed`. The `strict=True` xfail flag makes it impossible to mark a task complete without the fix being live in the codebase.
