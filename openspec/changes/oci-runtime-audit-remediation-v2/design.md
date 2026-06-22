## Context

The `oci-runtime` module (v0.3.0) wraps the `docker` and `podman` CLIs behind hexagonal-architecture ports. A full audit found 3 critical bugs, 5 high-severity issues, 5 medium issues, and 18 low issues. All 826 tests pass, yet the suite gives false confidence: two Podman bugs crash on real CLI output, a documented feature (`stream_output`) silently discards output, timeout enforcement has a gap that allows indefinite hangs, and several error paths are only tested with mocks that pass for the wrong reason.

This change remediates every finding. Each design decision was validated with a throwaway prototype (`/tmp/opencode/oci-prototypes/`) before being committed to this plan. Evidence was gathered from:
- Podman official docs and source code (`containers/image` library, `pull.go`)
- Python 3 `subprocess` documentation for `wait(timeout=...)` semantics
- Direct empirical verification of current bugs (reproduced crashes)
- Design-analysis agents reading the full codebase

### Current State
- **Domain layer**: clean hexagonal purity, but `frozen=True` is shallow (dict/list fields are mutable containers).
- **Ports layer**: clean, but `RuntimeProvider.create_managers()` leaks CLI-adapter construction concerns (`PtyTransport`, `OutputStream` factory hooks) into the port interface.
- **Adapters layer**: mostly correct, but Podman parser has parity gaps, transports have a timeout-enforcement gap, and `stream_output` is non-functional.
- **Factory**: type annotations don't match call sites.
- **Tests**: well-structured but with coverage gaps on critical error paths and several mock-pass-through tests that assert the wrong behavior.
- **Specs**: 3 active specs reference stale API names (`parse_id_from_pull`, `run_pty`); 1 spec contradicts implementation (`test_build_empty_output` expects `ImageError`, gets `ParsingError`).

## Goals / Non-Goals

**Goals:**
- Fix every critical, high, and medium issue identified in the audit
- Fix every documentation and spec incongruence
- Fix every test quality issue (non-meaningful tests, coverage gaps, bad practices)
- Align all solutions with clean hexagonal architecture principles
- Preserve the zero-dependency constraint (`dependencies = []` in pyproject.toml)
- Preserve Python 3.12+ compatibility
- Every fix backed by evidence and/or prototype validation
- Every new behavior covered by a spec and a meaningful test

**Non-Goals:**
- Adding new runtimes (nerdctl, containerd) — the architecture already supports this
- Changing the CLI-based adapter approach (no HTTP API, no SDK)
- Adding third-party dependencies (frozendict, pydantic, etc.)
- Refactoring the module structure (directory layout is sound)
- Performance optimization (correctness first)
- Backward compatibility for callers that mutate frozen dataclass fields (this is a **BREAKING** change by design — mutation was never intended)

## Decisions

### D-C1: Podman `parse_digest_from_pull` — eliminate premature `return ""`

**Decision**: Rewrite to scan ALL lines in reverse, skipping known progress/noise prefixes, returning the first hash match. Never `return ""` prematurely — only after exhausting all lines.

**Noise prefixes** (evidence from Podman docs/source): `Resolved`, `Trying`, `Getting`, `Copying`, `Writing`, `Storing`. Error/warning lines (`Error`, `Warning`) are skipped (handled by `_check_result`).

**Alternatives considered**:
- A) Parse only `result.stdout` (which is just the bare hex ID for Podman) → Fragile; assumes stdout/stderr separation is guaranteed. The parser receives a string and shouldn't assume its origin.
- B) Use `re.search` for the last `sha256:` occurrence in the full text → Works but less explicit about what constitutes noise. The line-by-line approach is more readable and debuggable.
- C) Keep the current structure but change `return ""` to `continue` → Minimal change, but the nested `if` structure is confusing. A flat loop with a noise-prefix tuple is cleaner.

**Prototype**: `/tmp/opencode/oci-prototypes/proto_c1_podman_pull.py` — all 6 test cases pass with the fixed implementation.

### D-C2: Podman `parse_inspect` null `RepoTags` — use `or []`

**Decision**: Change `tags=item.get("RepoTags", [])` to `tags=(item.get("RepoTags") or [])`, matching `DockerImageParser.parse_inspect` (docker.py:78).

**Evidence**: Docker returns `"RepoTags": null` for untagged images; Podman returns `"RepoTags": []` (non-nil empty slice in Go). `dict.get("RepoTags", [])` returns `None` when the key exists with `null` value — the `[]` default only applies when the key is *absent*. The `or []` idiom handles both `None` and `[]`.

**Alternatives**: None needed — this is the established pattern in the Docker parser. The fix is a one-line parity correction.

### D-C3: `stream_output=True` — route through `OutputStream` callbacks

**Decision**: When `config.stream_output=True` and not TTY, `run()` calls `streaming.stream()` with `on_stdout`/`on_stderr` callbacks that write to `self._output_stream` (the same `OutputStream` used by PTY mode). Returns `""` (output went to the stream, consistent with PTY mode returning `""`).

**Rationale**: Reuses existing infrastructure — no new ports, types, or port signature changes. Consistent with PTY routing (both modes write to `output_stream`). The `RunConfig.stream_output` flag already exists and is documented.

**Routing matrix** (validated by prototype):
| Condition | Transport | Output | Return |
|-----------|-----------|--------|--------|
| `detach=True` | batch `execute()` | captured | container ID |
| `effective_tty=True` | `pty_transport.execute_pty()` | → `output_stream` | `""` |
| `stream_output=True` | `streaming.stream()` with callbacks | → `output_stream` | `""` |
| neither | `streaming.stream()` no callbacks | captured | `stdout.strip()` |

**Alternatives considered**:
- A) Add `on_stdout`/`on_stderr` params to `run()` → Changes the port signature; callbacks are behavior, not data, so they don't belong in `RunConfig`. Adding them to `run()` changes the `ContainerManager` ABC.
- B) Return a generator from `run()` → Breaks the `-> str` return type; changes the port contract; generators can't be used in contexts that expect a string.
- C) Make `stream_output=True` return the accumulated stdout (like `stream_output=False`) → Loses the real-time streaming benefit; the flag becomes meaningless (same as `False`).

**Prototype**: `/tmp/opencode/oci-prototypes/proto_c3_stream_output.py` — all 4 routing cases pass.

### D-H1: Timeout-aware `process.wait()` — poll loop pattern

**Decision**: After `ProcessPipeReader.read()` returns (pipes drained), replace bare `process.wait()` with a poll loop:
```python
while True:
    if effective_token is not None and effective_token.is_cancelled:
        process.kill()
        process.wait()
        if deadline_token is not None and deadline_token.is_cancelled:
            raise OperationTimeoutError(command=command, timeout=timeout)
        return RawExecResult(returncode=-1, ...)
    try:
        returncode = process.wait(timeout=0.5)
        break
    except subprocess.TimeoutExpired:
        continue
```

**Evidence** (Python docs): "It is safe to catch this exception and retry the wait." After pipes are drained, `wait(timeout=...)` cannot deadlock (the deadlock warning applies only when pipes still have pending output). The busy-loop-with-short-sleeps implementation is POSIX-standard.

**Alternatives considered**:
- A) Single `process.wait(timeout=remaining_deadline)` → Requires tracking `start_time` and computing remaining time. More complex; doesn't poll user cancellation during the wait. If user cancels during the wait, the full remaining deadline must elapse before the cancel is noticed.
- B) `process.communicate(timeout=...)` → Docs say "do not call `wait()` after `communicate()` raises `TimeoutExpired`." Also, `communicate` reads from pipes — but pipes are already drained by `ProcessPipeReader`. Would need to use `communicate()` instead of the reader entirely, which changes the architecture.
- C) Use `select`/`poll` on the process PID → Not portable; `signal.SIGCHLD` handling is complex and race-prone.

**Applied to**: `CliTransport.execute()`, `CliStreamingTransport.stream()`, `CliPtyTransport.execute_pty()` — all three transports get the same poll loop.

**Prototype**: `/tmp/opencode/oci-prototypes/proto_h1_timeout_wait.py` — normal exit (rc=42), timeout fires (1.0s), user cancellation (0.5s), all pass.

### D-H2: Factory type annotations — `Callable[[str, BinaryResolver], ...]`

**Decision**: Update `RuntimeFactoryConfig` field annotations:
```python
transport_factory: Callable[[str, BinaryResolver], Transport] | None = None
streaming_transport_factory: Callable[[str, BinaryResolver], StreamingTransport] | None = None
```

**Rationale**: The call sites already pass `binary_resolver=binary_resolver` (factory.py:143-144,192). The default factories already accept it (`_default_transport_factory(binary, binary_resolver=None)`). ARCHITECTURE.md:233-234 already documents the correct signature. Only the type annotations are wrong.

**Alternatives**: None — this is a type-annotation fix to match the actual contract. No runtime behavior changes.

**Prototype**: `/tmp/opencode/oci-prototypes/proto_h2_factory_types.py` — default factories, custom factories, and wrong-signature rejection all pass.

### D-H4: Podman auth-error patterns — Podman-specific strings

**Decision**: Add to `PodmanImageParser`:
```python
_auth_error_patterns = (
    "authentication required",
    "requested access to the resource is denied",
)
```

**Evidence** (from `containers/image` library source):
- HTTP 401 → `ErrorCodeUnauthorized` → `"authentication required"` (`register.go:40`)
- HTTP 403 → `ErrorCodeDenied` → `"requested access to the resource is denied"` (`register.go:52`)
- Podman does NOT use Docker's `"pull access denied"` phrasing (confirmed: zero matches in Podman pull source)

**Alternatives**: None — these are the exact strings Podman emits. Using Docker's patterns would be incorrect.

### D-M1: `CliTransport` stdin thread — catch `ValueError` too

**Decision**: Change `except OSError:` to `except (OSError, ValueError):` in the stdin writer thread. `CliTransport` uses default `bufsize=-1` (`BufferedWriter`); closing `process.stdin` in the `finally` block while the thread is writing raises `ValueError: I/O operation on closed file` (not `OSError`). `CliStreamingTransport` avoids this by using `bufsize=0` (raw `FileIO`), but `CliTransport` should be robust regardless.

**Alternative**: Set `bufsize=0` in `CliTransport` to match streaming → Changes buffering behavior for batch transport; unnecessary when the `except` fix is simpler and more targeted.

### D-M2: `ProcessPipeReader._read_fd` — remove `fd < 1000`

**Decision**: Change `if isinstance(fd, int) and fd < 1000:` to `if isinstance(fd, int):`. Integer file descriptors ALWAYS use `os.read()`. The `< 1000` heuristic has no OS basis — fd numbers can exceed 1000 on systems with many open files or after `pty.openpty()`.

**Prototype**: `/tmp/opencode/oci-prototypes/proto_m2_fd_dispatch.py` — confirmed high fds (>= 1000) are correctly read with `os.read()` after the fix.

### D-M3: `CliStreamingTransport` — kill before joining stdin thread

**Decision**: Move the `process.kill()` + `process.wait()` BEFORE `_stdin_thread.join(timeout=5)` in the cancellation branch. If the pipe buffer is full, the stdin thread blocks on write and can't finish until the process is killed. Killing first breaks the pipe, allowing the thread to exit quickly.

**Rationale**: `CliTransport` already joins in the `finally` block (after kill). `CliStreamingTransport` should match this ordering.

### D-M4: `logs(follow=True)` — guard against `GeneratorExit` masking

**Decision**: In the `finally` block, separate the error-raising from generator cleanup:
```python
finally:
    cancel_token.cancel()
    thread.join(timeout=_LOGS_JOIN_TIMEOUT)
    if errors and not isinstance(errors[0], GeneratorExit):
        raise errors[0]
```
If the generator is being closed (`GeneratorExit`), don't raise the streaming error — let the generator close cleanly. If the streaming produced a real error (not `GeneratorExit`), raise it.

**Alternative**: Use `try/except GeneratorExit` around the `raise errors[0]` → More explicit but equivalent. The `isinstance` check is simpler.

### D-M5: Build error contract — wrap `ParsingError` in `ImageRuntimeError`

**Decision**: In `CliImageManager.build()`, wrap `parse_build_output` in `try/except ParsingError`:
```python
try:
    ident = self._parser.parse_build_output(self._decode_bytes(result.stdout))
except ParsingError as e:
    raise ImageRuntimeError(
        message=f"Could not parse image id from build output: {e.message}",
        stderr=self._decode_bytes(result.stdout),
    ) from e
```
Remove the dead `if not ident or ident == "sha256:":` guard (unreachable — `parse_build_output` always raises before returning invalid output).

**Rationale**: `build()` is an `ImageManager` operation. Any failure to produce a valid image ID is an `ImageError`. `ParsingError` is a subclass of `OciError` but NOT of `ImageError` — callers catching `except ImageError:` won't catch `ParsingError`. The wrapping ensures the operation-level error type is raised, with the parsing error preserved as `__cause__` for debugging. `ImageRuntimeError` is the `_generic_error` for images, so this is consistent with `_check_result`'s error classification.

**Spec impact**: `oci-test-contracts` requires `test_build_empty_output` to assert `ImageError`. This fix makes the implementation match the spec. The test is updated to assert `ImageRuntimeError` (a subclass of `ImageError`).

**Prototype**: `/tmp/opencode/oci-prototypes/proto_m5_build_error_contract.py` — all 6 test cases pass: valid output, empty output, invalid hex, `except ImageError` catches it, `except OciError` catches it, `__cause__` chain preserved.

### D-A1: Composition root consolidation — factory builds managers

**Decision**: Move manager construction from `BaseCliRuntimeProvider.create_managers()` into `RuntimeFactory.create()`. Remove `create_managers` from the `RuntimeProvider` port. Provider retains `kind`, `capabilities`, `create_parsers` only.

**Implementation**:
1. Add four `*_manager_cls` fields to `RuntimeFactoryConfig` (defaulting to `None`, resolved lazily like `runtime_cls`):
   ```python
   container_manager_cls: type[ContainerManager] | None = None
   image_manager_cls: type[ImageManager] | None = None
   volume_manager_cls: type[VolumeManager] | None = None
   network_manager_cls: type[NetworkManager] | None = None
   ```
2. In `RuntimeFactory.create()`, after creating parsers via `provider.create_parsers()`, instantiate managers directly:
   - `CliImageManager(transport, parsers.image_parser, caps)` — simple 3-arg constructor
   - `CliContainerManager(transport, parsers.container_parser, caps, streaming, tty_detector, *, pty_transport, cancellation_factory, output_stream)` — full constructor with the kwargs the factory already assembles
   - Same for volume/network managers
3. Remove `create_managers` from `RuntimeProvider` ABC, `BaseCliRuntimeProvider`, `DockerRuntimeProvider`, `PodmanRuntimeProvider`.
4. Remove the adapter manager imports from `provider/_base.py`.
5. Update `ARCHITECTURE.md:85` to: "The factory is the composition root: it is the only place manager, transport, engine, discovery, and infrastructure adapter classes are referenced. Provider subclasses reference only parser adapter classes (the one genuinely runtime-specific piece)."

**Rationale** (from design-analysis agent):
- Strictly purer hexagonally — the `RuntimeProvider` port stops being polluted by CLI-family adapter hooks (`PtyTransport`, `OutputStream`, `TtyDetector`, `CancellationToken` factories).
- Matches the factory's existing composition-root behavior for every other adapter (transport, streaming, engine, discovery, tty, output, cancellation, binary resolver, pty all default-lazily-imported in the factory).
- Generalizes cleanly to a 3rd runtime (nerdctl): the new provider declares parser classes + capabilities, and manager wiring is automatic — the provider doesn't need to know about `PtyTransport`/`OutputStream`.
- The factory already learns `CliRuntime`'s 6-arg constructor (`factory.py:166-173`); adding manager construction is a small, consistent step.

**BREAKING**: `RuntimeProvider.create_managers()` is removed. Any custom provider implementing this method must be updated to only implement `kind`, `capabilities`, `create_parsers`.

**Alternatives considered**:
- A) Accept the split, update docs (Option D) → Cheapest but doesn't fix the port-shape leak. A non-CLI provider still has to accept `PtyTransport`/`OutputStream` factory hooks.
- B) Provider returns a "manager factory spec" dataclass (Option C) → Adds indirection the factory would still interpret; complexity without benefit with only 2 providers and identical wiring.

### D-A2: Deep immutability — `MappingProxyType` + `tuple`

**Decision**: Apply the `RuntimeCapabilities` precedent uniformly to all domain types:
- All `dict[...]` fields → annotated as `Mapping[K, V]` (from `collections.abc`), wrapped in `MappingProxyType` in `__post_init__` via `object.__setattr__`.
- All `list[...]` fields → annotated as `tuple[...]`, converted to `tuple` in `__post_init__` via `object.__setattr__`.
- `RunConfig.command: list[str] | None` → `tuple[str, ...] | None` (None stays None).
- Shared module-level helpers `_freeze_mapping(self, field_names)` and `_freeze_sequence(self, field_names)` avoid 4× `__post_init__` duplication.

**Fields changed** (16 total):
| Dataclass | Field | Current | New |
|-----------|-------|---------|-----|
| `BuildContext` | `files` | `dict[str, bytes]` | `Mapping[str, bytes]` + MappingProxyType |
| `BuildContext` | `build_args` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `BuildContext` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `BuildContext` | `build_contexts` | `dict[str, str \| Path]` | `Mapping[str, str \| Path]` + MappingProxyType |
| `RunConfig` | `command` | `list[str] \| None` | `tuple[str, ...] \| None` |
| `RunConfig` | `environment` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `RunConfig` | `volumes` | `list[VolumeMount]` | `tuple[VolumeMount, ...]` |
| `RunConfig` | `ports` | `list[PortMapping]` | `tuple[PortMapping, ...]` |
| `RunConfig` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `RunConfig` | `runtime_flags` | `list[str]` | `tuple[str, ...]` |
| `ImageInfo` | `tags` | `list[str]` | `tuple[str, ...]` |
| `ImageInfo` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `ContainerInfo` | `ports` | `list[PortMapping]` | `tuple[PortMapping, ...]` |
| `ContainerInfo` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `VolumeInfo` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |
| `NetworkInfo` | `labels` | `dict[str, str]` | `Mapping[str, str]` + MappingProxyType |

**Evidence**:
- No code anywhere mutates these fields after construction (verified by agent: adapters only iterate, `.items()`, `cmd.extend()` — all work on tuple/MappingProxyType).
- `MappingProxyType({}) == {}` is `True` — existing `== {}` assertions pass unchanged.
- `tuple != list` — `== [...]` assertions must be updated to `== (...)` (approximately 6 assertions in test_types.py).
- `RuntimeCapabilities` already uses `tuple[str, ...]` and is documented as the immutability precedent (ARCHITECTURE.md:91,386).

**BREAKING**: Callers that mutate domain type fields after construction (e.g. `config.environment["x"] = "y"`) will get `TypeError`. This is intentional — mutation was never the intended usage pattern, and the documentation always claimed immutability.

**Alternatives considered**:
- A) Accept shallow immutability, fix docs only → Leaves the real footgun (`config.environment["x"] = "y"` silently succeeds) and contradicts the `RuntimeCapabilities` precedent.
- B) Use third-party `frozendict`/`pydantic` → Violates `dependencies = []` and `ARCHITECTURE.md:82` (stdlib-only domain).
- C) `__setattr__` override → Redundant; `frozen=True` already blocks attribute reassignment. The gap is container contents, not attribute assignment.

**Prototype**: `/tmp/opencode/oci-prototypes/proto_a2_immutable.py` — all 10 test cases pass.

### D-T1: Unify `timeout` type to `float | None`

**Decision**: Change `Transport.execute()` and `StreamingTransport.stream()` port signatures from `timeout: int | None` to `timeout: float | None`. This matches `PtyTransport.execute_pty()` (already `float | None`), `RunConfig.timeout` (already `float | None`), `ContainerManager.exec_container()` (already `float | None`), and `DeadlineCancellationToken.__init__` (accepts `float`).

**Rationale**: `int` was overly restrictive. `float` is a superset. The adapters already pass `float` values (e.g., `config.timeout` which is `float | None`). No runtime behavior changes — `DeadlineCancellationToken` and `threading.Timer` both accept `float`.

**Alternative**: Change `RunConfig.timeout` and `exec_container` to `int | None` → Loses sub-second precision; `DeadlineCancellationToken` already handles `float`; `float` is the more natural type for timeouts.

### D-T2: Fix `RuntimePreference` docstring

**Decision**: Update the docstring to: "Explicit user declaration of what engine to use. No guessing, no fallback. Creation does NOT probe availability — callers who need to verify reachability should call `engine.is_available()` after `factory.create()`."

### D-Q1: Concurrency tests — remove misleading tests

**Decision**: Remove `test_concurrent_manager_calls` and `test_recording_transport_thread_safety` (they test GIL atomicity, not manager thread-safety). Keep `test_concurrent_factory_create` (it tests that factory creation is stateless and safe to call concurrently — this IS a real property worth testing, since `_providers` and `_cfg` are read-only shared state). Add a docstring to the remaining test explaining what concurrency property it verifies.

**Alternative**: Replace with real shared-state tests using a `Lock`-protected counter → Adds test infrastructure complexity for a property that isn't a design goal (managers are not documented as thread-safe).

### D-Q2: Fix build-command canned-response keys

**Decision**: Update all test response keys that have `("-", "--quiet")` to `("--quiet", "-")`, matching the actual emitted command order (`image.py:44` emits `default_build_flags` before `positional`). Files affected: `test_image_manager_contract.py`, `test_workflows.py`, `test_malformed_output.py`.

**Evidence**: Docker build CLI allows interspersed flags and positionals (cobra `interspersed=true`), so both orderings are valid Docker syntax. But the adapter emits a specific order, and the tests should match the actual command shape.

### D-Q5: Deterministic `DeadlineCancellationToken` tests

**Decision**: Replace `time.sleep`-based tests with a mock `threading.Timer` or a direct test of the `cancel()` → `is_cancelled` relationship without waiting for the timer. Test the timer firing separately with a generous timeout (1s for a 0.1s timer).

## Risks / Trade-offs

- **[BREAKING: Domain type field types change from `list`/`dict` to `tuple`/`MappingProxyType`]** → Callers that index (`config.volumes[0]`), iterate, or call `.items()` are unaffected. Callers that mutate (`config.environment["x"] = "y"`) will get `TypeError`. Mitigation: This is intentional — mutation was never documented as supported. The `ARCHITECTURE.md` already claims "instances cannot be mutated after creation."

- **[BREAKING: `RuntimeProvider.create_managers()` removed]** → Custom providers implementing this method must be updated. Mitigation: Only `DockerRuntimeProvider` and `PodmanRuntimeProvider` exist in the codebase. The `ARCHITECTURE.md` "Adding a New Runtime" section is updated to reflect the new provider interface (only `kind`, `capabilities`, `create_parsers`).

- **[BREAKING: `build()` raises `ImageRuntimeError` instead of `ParsingError` for invalid output]** → Callers catching `except ParsingError:` for build failures won't catch it. Mitigation: `ImageRuntimeError` is a subclass of `ImageError` which is a subclass of `OciError`. Callers catching `except OciError:` (the documented catch-all) are unaffected. The `ParsingError` is preserved as `__cause__`. The spec `oci-test-contracts` already requires `ImageError`.

- **[Poll loop adds 0.5s latency to process exit detection]** → `process.wait(timeout=0.5)` polls every 0.5s. If a process exits between polls, there's up to 0.5s delay before the exit is detected. Mitigation: `wait(timeout=0.5)` uses an internal busy loop with short sleeps (per Python docs), so the actual delay is much less than 0.5s. The timeout value can be tuned if needed.

- **[Conformance fixture update for Podman pull]** → The current fixture (`pull_alpine.txt`) is a single bare hex line. Updating it to realistic multi-line output would require recapturing from a live Podman daemon. Mitigation: The fixture represents `result.stdout` (which is just the hex ID for Podman), so the current fixture is actually correct for stdout-only. The parser fix is for robustness against multi-line stdout, not because the fixture is wrong.

- **[Test churn is significant]** → ~20 test files modified. Mitigation: Each change is small and targeted. The test changes are mechanical (assertion updates, fixture key corrections, new test additions).

## Migration Plan

1. **Phase 1 — Non-breaking fixes**: C1, C2, H4, M1, M2, M3, M4, Q2, Q3, Q4, Q5, Q6, D1, D2, D3. These can be applied independently.
2. **Phase 2 — Type contract fixes**: H2, T1, T2. These are annotation-only changes (no runtime behavior change).
3. **Phase 3 — Breaking changes**: A1 (composition root), A2 (deep immutability), M5 (build error contract), C3 (stream_output). These change public APIs.
4. **Phase 4 — Test additions**: H3, H5, Q1. New tests for previously-untested paths.
5. **Rollback**: Each phase is independently revertible via git. No data migration needed (the module is stateless).

## Open Questions

None — all design decisions have been validated by prototype or evidence.
