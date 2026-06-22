## Context

`src/shared/oci-runtime` is a runtime-agnostic OCI container management module claiming hexagonal architecture. A fresh audit found 42+ issues. 26 are committed as `xfail(strict=True)` reproductions in `tests/audit/test_known_bugs.py`; 7 are conformance xfails in `tests/conformance/test_parser_conformance.py` anchored to real docker/podman CLI fixtures. The import-direction linter in `tests/architecture/test_layering.py` mechanically enforces layering. This change fixes every finding that has a committed failing test.

The prior remediation (archived `2026-06-21`) failed because tasks were marked `[x]` against ephemeral prototypes. This change is structurally different: every task names the exact committed xfail test that must flip from `xfailed` to `passed`. The `strict=True` flag makes it impossible to mark a task complete without the fix being live.

Current state:
- Python 3.12+, zero runtime dependencies.
- `make check` runs lint + full suite (775 passed, 1 skipped, 26 xfailed after guardrail commit).
- Conformance fixtures captured from docker 28.1.1 and podman 5.4.2.
- No repo-level CI; the Makefile is the gate.

## Goals / Non-Goals

**Goals:**
- Flip all 26 audit xfails to passing (remove the xfail markers).
- Flip all 7 conformance xfails to passing (remove the xfail markers).
- Fix the architecture/test-quality findings (F10, F15-F21, F30, F34, F38-F42) verified by existing guardrails.
- Every fix is verified by a committed test, not a judgment call.

**Non-Goals:**
- Adding new runtimes or manager operations.
- Rewriting the transport/streaming layer beyond the targeted timeout/exception fixes.
- Changing the CLI command vocabulary beyond the flagged build-flag additions.
- Adding repo-level CI (the Makefile gate is sufficient for this change).
- Fixing F22-F29 (inconsistencies) and F35-F37 (test drifts) — these are documented but not mechanically verified, so they are deferred to a follow-up.

## Decisions

### D-F1: exec_container preserves stderr on success
**Chosen:** Always decode `result.stderr` into `stderr_str`, regardless of exit code. Remove the `else: stderr_str = ""` branch.
**Why:** The current code forces `stderr_str = ""` when `returncode == 0`, discarding real stderr. A successful `docker exec` can write to stderr (warnings, debug output).
**Verification:** `tests/audit/test_known_bugs.py::TestF01::test_exec_success_preserves_stderr` must flip from xfail to pass.

### D-F2: logs(follow=True) wires on_stderr
**Chosen:** Pass `on_stderr=lambda d: queue.put(self._decode_stdout(d))` to `stream()` alongside `on_stdout`.
**Why:** `docker logs` emits container stderr on the transport's stderr. Currently only `on_stdout` is wired, so stderr is silently discarded.
**Verification:** `TestF02::test_logs_follow_includes_stderr` must flip.

### D-F3: All four prune() methods call _check_result
**Chosen:** Add `self._check_result(result, cmd, operation="prune X", entity="")` before `parse_prune` in all four managers.
**Why:** A failed prune (daemon down) currently returns `PruneResult(0, 0)`, indistinguishable from a successful empty prune.
**Verification:** `TestF03` (4 tests) must flip.

### D-F4: build() emits --build-arg, --label, --pull, --network, --rm
**Chosen:** After the existing `--no-cache`/`--target` block in `image.py`, add:
```python
for k, v in context.build_args.items():
    cmd.extend(["--build-arg", f"{k}={v}"])
for k, v in context.labels.items():
    cmd.extend(["--label", f"{k}={v}"])
if context.pull:
    cmd.append("--pull")
if not context.rm:
    cmd.extend(["--rm", "false"])
if context.network:
    cmd.extend(["--network", context.network])
for k, v in context.build_contexts.items():
    cmd.extend(["--build-context", f"{k}={v}"])
```
**Why:** 6 `BuildContext` fields are currently silently dropped. No documented field may be ignored.
**Verification:** `TestF04` (3 tests for build_args, labels, pull) must flip. The remaining 3 (network, rm, build_contexts) are verified by the same code change but are not in the xfail set — add them as new passing tests.

### D-F7: Per-manager generic error classes
**Chosen:** Add `ImageRuntimeError(ImageError)`, `VolumeRuntimeError(VolumeError)`, `NetworkRuntimeError(NetworkError)` to `domain/exceptions.py`. Change `CliBaseManager` to accept a `_generic_error: type[OciError]` class variable (defaulting to `ContainerRuntimeError`). Set it in each subclass: `CliImageManager._generic_error = ImageRuntimeError`, etc. Change `_check_result` to raise `self._generic_error` instead of `ContainerRuntimeError`.
**Why:** `except VolumeError` currently doesn't catch volume manager failures because `_check_result` raises `ContainerRuntimeError` (a `ContainerError` subclass). The hierarchy is semantically broken.
**Verification:** `TestF07` (3 tests) must flip.
**BREAKING:** Callers catching `ContainerRuntimeError` for image/volume/network failures must catch the entity error instead.

### D-F8: _coerce_size wraps return in int()
**Chosen:** Change `return size or 0` to `return int(size or 0)` in `_coerce_size`.
**Why:** Float JSON sizes (e.g. `5000.0`) currently leak through as float, violating `-> int`. Docker zeroes them (isinstance check); podman stores the float.
**Verification:** `TestF08::test_coerce_size_float_returns_int` must flip.

### D-F9: parse_size_to_bytes fullmatch + K/M/G/T/TIB
**Chosen:** Change `re.search` to `re.fullmatch`. Add `'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4, 'TIB': 1024**4` to the units dict. Keep existing units. The regex stays `(\d+\.?\d*)\s*([a-zA-Z]+)` but `fullmatch` ensures the entire string is a valid size.
**Why:** Task C of the prior remediation promised this but never implemented it. Substring matches like `"junk 1.5GB trailing"` currently parse silently.
**Verification:** `TestF09` (4 tests) must flip.

### D-F11: get_runtime_binary returns resolved path
**Chosen:** Change `return self.binary` to `return self._which_cache` after `_ensure_binary()`.
**Why:** `_which_cache` holds the `shutil.which`-resolved path; `self.binary` is just the name. ARCHITECTURE.md says "returns the resolved binary path".
**Verification:** `TestF11::test_get_runtime_binary_returns_resolved_path` must flip.
**Note:** Callers that string-compare the binary name will see the resolved path. This is a behavior change but aligns with the documented contract.

### D-F14: OperationTimeoutError(OciError)
**Chosen:** Add `OperationTimeoutError(OciError)` to `domain/exceptions.py` with `command` and `timeout` fields. In `streaming.py`, replace `raise subprocess.TimeoutExpired(...)` with `raise OperationTimeoutError(command=command, timeout=timeout, message=...)`. In `pty.py`, same replacement. Export `OperationTimeoutError` from the public API.
**Why:** The architecture promises `except OciError` catches every error. `subprocess.TimeoutExpired` is a builtin that escapes this hierarchy.
**Verification:** `TestF14::test_stream_timeout_is_oci_error` must flip. Add a PTY timeout version too.
**BREAKING:** Callers catching `subprocess.TimeoutExpired` from this module must catch `OperationTimeoutError` (or `OciError`) instead.

### D-F-CONF-1: DockerContainerParser handles string Names
**Chosen:** In `parse_list`, before the `isinstance(names, list)` check, coerce: `if isinstance(names, str): names = [names]`.
**Why:** Real `docker ps --format '{{json .}}'` emits `Names` as a string, not a list. The parser currently raises `ParsingError`.
**Verification:** `TestContainerListConformance::test_docker_parse_list_produces_container_infos` must flip.

### D-F-CONF-2: PodmanContainerParser guards null Ports
**Chosen:** In `_parse_ports_from_list`, change `for p in item.get("Ports", []):` to `ports = item.get("Ports") or []; for p in ports:`.
**Why:** Real `podman ps --format json` emits `Ports: null` when no ports are mapped. Iterating `None` raises `TypeError`.
**Verification:** `test_podman_parse_list_produces_container_infos` must flip.

### D-F-CONF-3/4: All inspect parsers coerce null Labels to {}
**Chosen:** In every `parse_inspect` method, change `labels=item.get("Labels", {})` to `labels=item.get("Labels") or {}`. This handles both `None` and missing keys uniformly.
**Why:** `item.get("Labels", {})` returns `None` when the key exists with value `null` (JSON null). The `or {}` coercion handles this.
**Verification:** `test_parse_inspect_labels_is_dict[podman]` (container) and `[docker]` (volume) must flip.

### D-F-CONF-5: PodmanImageParser prefixes bare-hex pull ids
**Chosen:** In `parse_id_from_pull`, before returning a bare line as the id, check if it matches `^[a-f0-9]{12,64}$` and prefix with `sha256:` if so.
**Why:** Real podman pull output for a cached image is a single bare-hex line. The current code returns it as-is, violating the `sha256:`-prefix contract.
**Verification:** `test_parse_id_from_pull_returns_sha256[podman]` must flip.

### D-F10: exists() stops catching ParsingError
**Chosen:** Change `except (XNotFoundError, ParsingError): return False` to `except XNotFoundError: return False` in all four `exists()` methods. Let `ParsingError` propagate.
**Why:** A parse error means the parser is broken, not that the entity doesn't exist. Catching it hides parser bugs and misreports present entities as absent.

### D-F15: RuntimeFactoryConfig gains cancellation_factory
**Chosen:** Add `cancellation_factory: Callable[[], CancellationToken] | None = None` to `RuntimeFactoryConfig`. Default resolves to `lambda: ThreadCancellationToken()`. Thread it through `BaseCliRuntimeProvider.create_managers` to `CliContainerManager`.
**Why:** The cancellation adapter is currently hardwired in `CliContainerManager.__init__`. The composition root must expose it.

### D-F16: CliStreamingTransport and run_pty use cached which
**Chosen:** Both `CliStreamingTransport.stream()` and `run_pty()` currently call `shutil.which(self.binary)` / `shutil.which(runtime)` uncached. Change them to accept the resolved binary from `CliTransport` or use a shared cache. Minimal change: have `run_pty` accept an optional `binary_path: str | None = None` and skip `which` if provided. `CliStreamingTransport` can cache its own `_which_cache` like `CliTransport` does.
**Why:** Four uncached availability paths remain after A7. Every `run()`/`logs()`/PTY call re-probes.

### D-F17: RunConfig validates invariants in domain
**Chosen:** Add to `RunConfig.__post_init__`: `if self.network == NetworkMode.CONTAINER and not self.network_container: raise ValueError(...)`. Add `if self.detach and (self.tty or self.auto_tty): raise ValueError(...)`. Remove the corresponding checks from `CliContainerManager.run()`.
**Why:** These are domain invariants, not adapter concerns. A second adapter must not re-implement them.

### D-F19: ports/__init__.py drops RuntimeCapabilities re-export
**Chosen:** Remove `from oci_runtime.domain.capabilities import RuntimeCapabilities` and `"RuntimeCapabilities"` from `ports/__init__.py.__all__`.
**Why:** After B2 moved `RuntimeCapabilities` to domain, the ports re-export is residual. ARCHITECTURE.md says ports contains only ABCs + the ParsingError re-export.

### D-F20: CliBaseManager._not_found_error default to OciError
**Chosen:** Change `_not_found_error: type[OciError] = ContainerRuntimeError` to `_not_found_error: type[OciError] = OciError` and `_generic_error: type[OciError] = ContainerRuntimeError`. The default `_not_found_error = OciError` is safe because every subclass overrides it. A new manager that forgets the override raises a generic `OciError` for not-found, not a misleading `ContainerRuntimeError`.

### D-F21: RuntimeCapabilities list fields become tuple
**Chosen:** Change `list_format_flags: list[str]`, `default_run_flags: list[str]`, `default_build_flags: list[str]` to `tuple[str, ...]`. Update default_factory to produce tuples. Update all construction sites (docker/podman providers) to pass tuples.
**Why:** `frozen=True` with mutable `list` defaults is false immutability. `caps.list_format_flags.append("x")` mutates the "frozen" object.

### D-F30: B5 wiring tests assert injected instances
**Chosen:** In `test_factory_wiring.py::TestFactoryCustomInjection`, change `assert engine.capabilities is not None` to `assert engine.containers._tty_detector is custom_tty` and `assert engine.containers._output_stream is custom_stream`.
**Why:** The current assertions are tautologies. B5 has zero effective coverage.

### D-F34: test_build_empty_output asserts ImageError
**Chosen:** In `test_empty_outputs.py::test_build_empty_output`, change `assert result == "sha256:"` to `with pytest.raises(ImageError): mgr.build(...)`. Add a `build()` empty-output check analogous to `pull()`'s A5 fix.
**Why:** `"sha256:"` is a silent failure, not a valid image id. The test codifies the bug.

### D-F38-F42: Code smells
- `parser/base.py`: remove the redundant local `from ... import parse_size_to_bytes` inside `_coerce_size` (line 10).
- `cli.py:15`: change `_which_cache: str | None | None` to `str | None | object` (or define a sentinel class).
- `cli.py:46-47`: remove the no-op `except subprocess.TimeoutExpired: raise`.
- `container.py`: rename `_decode_stdout` to `_decode_bytes` (it decodes any bytes, not just stdout).

## Risks / Trade-offs

- **[BREAKING: F7 entity-typed errors]** Callers catching `ContainerRuntimeError` for image/volume/network failures must catch the entity error. Mitigation: the entity errors are parent classes of the new runtime errors, so `except ImageError` catches `ImageRuntimeError`. Version bump to 0.3.0.
- **[BREAKING: F14 OperationTimeoutError]** Callers catching `subprocess.TimeoutExpired` must catch `OperationTimeoutError`. Mitigation: `OperationTimeoutError` is an `OciError`, so `except OciError` works. Document in ARCHITECTURE.md.
- **[BREAKING: F11 resolved path]** `get_runtime_binary()` returns the resolved path, not the name. Mitigation: aligns with documented contract; callers that need the name can use `transport.binary` (add as a property if needed).
- **[F21 tuple fields]** Callers that mutate `caps.list_format_flags` will get `AttributeError`. Mitigation: frozen dataclass shouldn't be mutated; this is the correct behavior.
- **[Conformance fixtures may go stale]** If docker/podman change their JSON format, conformance tests may fail on new versions. Mitigation: `make capture-fixtures` regenerates; the test failure is the signal to update parsers.
