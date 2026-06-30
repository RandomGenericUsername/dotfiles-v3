# oci-runtime Full Audit Report

Test suite status: **840 passed, 1 skipped** — every finding below is masked by a passing suite.

---

## A. Critical Bugs (functional & semantic correctness)

### A1. `PortMapping.host_ip` silently dropped by `CliContainerManager.run()` ⚠ Security relevant
- `src/oci_runtime/adapters/managers/container.py:110-116`
- `host_ip` is a required field (no default; ARCHITECTURE.md L95 explicitly states it is "required"). The parsers faithfully populate `host_ip` from `HostIp` / `binding.get("HostIp")`. But `run()` builds `-p` flags as **`8080:80/tcp`** regardless of `host_ip`, ignoring it completely.
- **Empirically verified:** `PortMapping(container_port=80, host_port=8080, host_ip='127.0.0.1')` emits `-p 8080:80/tcp`, producing `0.0.0.0:8080` binding instead of `127.0.0.1:8080`. The user asked for loopback-only binding and got host-wide exposure.
- Architectural intent: the field is required specifically to "prevent a misleading 0.0.0.0 default" (ARCHITECTURE.md L95). The implementation reintroduces exactly that.
- Should emit `-p <host_ip>:<host_port>:<container_port>/<protocol>` when `host_ip is not None`.

### A2. `_parse_json_item` accepts scalar JSON without raising `ParsingError`
- `src/oci_runtime/adapters/parser/base.py:42-50`
- `_parse_json_list` (L52-82) explicitly rejects non-list/non-dict JSON scalars (`ParsingError`). The architecture doc L209 advertises this guard for both methods.
- `_parse_json_item` does **not** have the guard. `parse_inspect('42')` returns `int 42` (type-annotated as `dict`). The next `.get()` call then raises **`AttributeError: 'int' object has no attribute 'get'`** instead of `ParsingError` — confirmed empirically.
- Subsequently `_check_result` only swallows `OciError`/subclass exceptions — `AttributeError` escapes the manager layer, breaking the "all module exceptions descend from `OciError`" contract (ARCHITECTURE.md L101).

### A3. `ProcessPipeReader` retains the very deadlock path the doc claims was "fixed"
- `src/oci_runtime/adapters/_process_reader.py:35-44`
- ARCHITECTURE.md L167 ("ProcessPipeReader", B2 remediation) explicitly says "`fileobj.read(n)` on `FileIO` blocks until `n` bytes or EOF, which would deadlock on processes that emit small chunks then wait" and presents `os.read(fd, n)` as the fix.
- The implementation retains the broken fallback in `_read_fd`'s `else` branch — `fd.read(size)` on a `BufferedReader`. When `from_process()` falls back to the file-object path (`fileno()` raises), readers use blocking `read()` → deadlock.
- Empirically verified: a `BytesIO`-based reader reports `primary type: BytesIO` and would use the blocking path.
- Even in the happy path the `isinstance(fd, int)` check (L36) is dead defensive code — `fileno()` always returns int when it succeeds.

### A4. `_check_result` throws away command context on auth errors
- `src/oci_runtime/adapters/managers/base.py:71-73`
- `is_auth = getattr(self._parser, "is_auth_error", None)` — because `BaseCliParser` defines `is_auth_error` unconditionally (base.py L36-40), this `getattr` **never** returns `None`. The `is_auth is not None` part of the conditional is dead, masking the real intent.
- The `ImagePullAccessDeniedError` is raised with only `image_name` (domain/exceptions.py L57) but `command`, `exit_code`, `stderr` are discarded — meaning debug context for pull auth failures is lost (compare to `ContainerRuntimeError` which keeps all three in base.py L86-91).

### A5. `CliPtyTransport.execute_pty` raises wrong-domain exception
- `src/oci_runtime/adapters/transport/pty.py:33-34`
- `if not command: raise ContainerRuntimeError("Empty command list", command=command)`
- PtyTransport is a generic transport unrelated to containers. Raising `ContainerRuntimeError` (a container-specific error subclass) from a transport port is a layering violation (architecture.md L101 — the exception tree domain model couples port knowledge where it shouldn't).
- Worse: passing `command=[]` to `OciError._format_message` skips the "Command:" line because `if self.command: parts.append(...)` evaluates `[]` as falsy → the empty-command error has no command in its formatted message.

### A6. `image.py pull()` raises base `ImageError` instead of `ImageRuntimeError`
- `src/oci-runtime/adapters/managers/image.py:91-94`
- When `parse_digest_from_pull` returns `""`, `pull()` raises `ImageError` (the abstract base). The other generic-failure paths in this manager use `ImageRuntimeError` (`_generic_error = ImageRuntimeError`). Inconsistent — callers catching `ImageRuntimeError` will miss this; callers catching `ImageError` will catch it. Plus, no `command`/`exit_code`/`stderr` is attached, even though the result is available.

### A7. `version()` raises `RuntimeNotAvailableError` for any non-zero exit
- `src/oci-runtime/adapters/engine/cli.py:53-60`
- A non-zero exit from `docker --version` does **not** necessarily mean the runtime isn't available. Captured `stderr` is discarded — the user gets "Container runtime 'docker' is not available…" with no clue why. Should raise `OciError`/`RuntimeError` with the captured stderr/exit code, or at minimum include them.

### A8. `RuntimeProvider` port is missing `create_managers` — docs mismatch
- ARCHITECTURE.md L141 advertise `create_managers(transport, streaming, caps, *, tty_detector_factory, output_stream_factory, cancellation_factory, pty_transport) -> Managers` as the canonical provider method.
- The actual `RuntimeProvider` ABC (`ports/provider.py:8-26`) defines only `kind`, `capabilities()`, `create_parsers()`. `create_managers` was removed in v2 remediation ("composition root consolidation"). **The doc was not updated** to match.
- The `Managers` aggregate (`ports/aggregates.py:27-34`) exists but is **dead code** — never returned by any port method, only declared then exported via `ports/__init__.py`. Two grep hits specifically — definition and re-export; zero usages.

## B. Hexagonal-Architecture Drifts

### B1. Architecture linter allows adapter→adapter imports (permissive)
- `tests/architecture/test_layering.py:38` allows `"adapters": {"domain", "ports", "adapters"}`.
- Concrete consequences:
  - `transport/cli.py:9` `from oci_runtime.adapters.binary import CliBinaryResolver`
  - `transport/streaming.py:10` same
  - `transport/pty.py:38` lazy `from oci_runtime.adapters.output_stream import StdoutBufferStream`
- Strict hexagonal: adapters only depend on **ports** (never on other adapters); the composition root is the sole place where concrete adapters meet. The current linter should disallow `adapters → adapters` and enforce that adapters receive their collaborators injected from the factory.

### B2. Transports instantiate adapter fallbacks internally, breaking DI
- `transport/cli.py:22` `self._resolver = binary_resolver or CliBinaryResolver()` — same in `streaming.py:21`.
- `transport/pty.py:37-40` lazy-imports `StdoutBufferStream` inside `execute_pty` when `output_stream is None`.
- The factory always provides these collaborators. Falling back to a concrete adapter inside the adapter itself couples the adapter to a sibling and breaks the "factory is the single composition root" rule (ARCHITECTURE.md L80).

### B3. Composition root leaks adapter types
- `factory.py:90-111` — `_default_container_manager_cls()`, `_default_image_manager_cls()`, etc. — the factory knows about each manager class individually (`CliContainerManager`, `CliImageManager`, …). The "extensibility" provision for `BaseCliRuntimeProvider` (ARCHITECTURE.md L353-378) says "no `create_managers`" needed, but adding a new run-kind still requires hooking 4 cls defaults into `RuntimeFactoryConfig`.
- The `RuntimeFactoryConfig` dataclass has fields named `container_manager_cls` etc. but uses the singular `_resolve_config` to instantiate each separately. Hard to extend without editing the composition root.

## C. Code Smells & Dead/Defensive Code

### C1. `_execute_list` is dead code; all 4 managers duplicate it inline
- `adapters/managers/base.py:36-52` defines `_execute_list()`. Confirmed via grep: zero callers outside the definition itself.
- ARCHITECTURE.md L183 explicitly claims: "Each manager's `list()` delegates to this helper, eliminating the 4× copy-pasted list method."
- Yet `container.py:232-244`, `image.py:124-132`, `volume.py:64-72`, `network.py:86-94` each paste the same `cmd = [binary] + subcommand; cmd.extend(format_flags); if filters: ...; execute; check; parse` boilerplate. The advertised dedup never happened; the shipped tests do not enforce it.

### C2. `_NOT_PROBED` sentinel in `binary.py` is dead
- `adapters/binary.py:7` `_NOT_PROBED = object()` — defined, never used. The doc (L159) frames it as the "previously existing, now eliminated mechanism" — leftover only.

### C3. `RuntimeFactoryConfig` type signatures disagree with their default factories
- `factory.py:31,33`: `Callable[[str, BinaryResolver], Transport]` — second arg is `BinaryResolver`, not optional.
- `factory.py:60-66, 68-74`: `_default_transport_factory(binary, binary_resolver: BinaryResolver | None = None)` — declares the same arg as optional `None`. The factory always passes via keyword (`binary_resolver=binary_resolver`), so the mismatch survives at runtime, but static checkers / consumers would expect a non-None resolver and the docstring tells a different story from the signature.

### C4. Timed-out or stale docstrings
- `ports/streaming.py:11-12` "Unlike `Transport.execute()` which is batch (subprocess.run)…" — `CliTransport.execute()` no longer uses `subprocess.run` (it was replaced with `Popen + ProcessPipeReader`). Stale.
- `ARCHITECTURE.md L131`: `Transport.execute` "runs a command to completion and returns raw bytes." but return type is `RawExecResult` (not "raw bytes"). Minor phrasing error.

### C5. `archive_threads` / not used
- `adapters/_tar.py:8-11` `_validate_tar_path` — `norm.startswith("..")` matches `..foo` (a valid filename, not a parent reference) and `norm == ".."` is redundant. Should be `norm == ".." or norm.startswith("../")`. Also no Windows-path handling (low priority since Linux-only).

### C6. `parse_size_to_bytes` rejects trailing whitespace and no-unit input
- `adapters/_utils.py:27` `re.fullmatch(r"(\d*\.?\d+)\s*([a-zA-Z]+)", size_str.upper())` — requires a unit; `"1024"` fails although Docker commonly omits units; `"1.5GB "` (trailing whitespace) also fails. Minor.

### C7. `container.py` port-mapping `host_ip`-ignore: helper needed but absent — see A1.

## D. Tests That Don't Mean What They Claim

### D1. Tests **forward** the host_ip bug instead of catching it
- `tests/unit/wiring/test_manager_commands.py:175,193` and `test_workflows.py:161,156`:
  - `ports=[PortMapping(container_port=80, host_port=8080, host_ip="0.0.0.0")]` on input,
  - `assert st.calls[0].command == [..., "-p", "8080:80/tcp", ...]` on assertion.
- The author **accommodates** the bug rather than asserting correct behavior. There is **no test** that verifies `-p 127.0.0.1:8080:80/tcp` is emitted when `host_ip="127.0.0.1"`. → A1 hides behind a "passing" test.

### D2. Contract test passes wrong parser types into the aggregate
- `tests/unit/contract/test_interface_compliance.py:471-478` `test_parsers_is_frozen_dataclass`:
  ```python
  parsers = Parsers(
      container_parser=DockerContainerParser(),
      image_parser=DockerContainerParser(),     # wrong type!
      volume_parser=DockerContainerParser(),    # wrong type!
      network_parser=DockerContainerParser(),   # wrong type!
  )
  ```
- `Parsers` has no `__post_init__` enforcement, so a container-parser is silently stored in every slot. The test proves frozen-dataclass semantics but proves nothing about the aggregate's type contract.

### D3. `test_factory_config_defaults_are_none` checks 4 of 12 fields
- `test_interface_compliance.py:462-468` only asserts `transport_factory, streaming_transport_factory, runtime_cls, discovery_factory` are None. The other 8 fields (`tty_detector_factory`, `output_stream_factory`, `cancellation_factory`, `binary_resolver_factory`, `pty_transport_factory`, `container_manager_cls`, `image_manager_cls`, `volume_manager_cls`, `network_manager_cls`) are unasserted. Regression-prone.

### D4. `test_factory_wiring.py:77` uses broken dict key, still passes
- `transport = RecordingTransport("docker", {"docker --version": RawExecResult(...)})`. The recording transport uses `tuple(command)` lookup, so `"docker --version"` (string) never matches the actual `("docker", "--version")` tuple. The test still "passes" because `engine.is_available()` calls `probe()` returning `True` without invoking `execute()` — the broken key is never exercised. Misleading.

### D5. `test_factory_wiring.py:25-31` patches `subprocess.run` (never called)
- `@patch("subprocess.run")` decorates several factory tests. `RuntimeFactory().create()` and `engine.is_available()` do not call `subprocess.run` — `CliTransport` uses `subprocess.Popen`. The mock is dead weight.

### D6. `test_run_with_all_options` — test dict-key contain `-t` but the asserted command does not
- `test_manager_commands.py:163,193` — the response map key includes `-t`; the asserted actual command doesn't (because `effective_tty=False`). The lookup intentionally misses, the default `RawExecResult(0, b"", b"")` is returned, the assertion passes because it just compares the actual emitted command. Misleading fixture data — should be cleaned up to match the actual command.

### D7. Wiring tests assert on concrete adapter classes (re-introduces coupling)
- `test_factory_wiring.py:42-58` `assert isinstance(runtime.images, CliImageManager)` etc. — wires concrete classes into the "this is a hexagonal composition" assertion. If a future provider swaps in an alternative `ImageManager` adapter (the doc's extensibility story), these "wiring" tests break — but not because behavior broke, only because the adapter class changed. Smell.

### D8. No `_not_found_error` enforcement test
- ARCHITECTURE.md L175 says `_not_found_error` is "required — no default". This is enforced purely at the class via attribute absence; no test asserts that a `_not_found_error=…` omitted manager raises (or fails). Could regress.

### D9. Conformance tests skip on missing fixtures but never commit
- `tests/conformance/test_parser_conformance.py` skips tests when `fixtures/<runtime>/<file>` doesn't exist. The repo doesn't ship the fixtures either — so unless `make capture-fixtures` was run on a machine with both runtimes, all conformance tests skip silently. Confirmed by the suite report: **1 skipped** is likely a single fixture being absent.

### D10. (Tangential) McL rou `_safe_int` is used inconsistently
- Parsers use `_safe_int` for `PublicPort` / `HostPort` (docker, podman) but never for `PortMapping.host_port` directly back to domain — yet `container.py` emits `host_port` raw without `_safe_int`. Cosmetic only.

## E. Documentation/Code Incongruences (beyond A8)

### E1. Doc table says `detach=True` uses batch `transport.execute()`, but it uses `streaming.stream()`
- ARCHITECTURE.md L188-197 routing matrix: `detach=True → batch execute() (via transport)`.
- `container.py`: when `detach=True, effective_tty=False, stream_output=False`, the only executed branch is line 164 `self._streaming.stream(cmd, timeout=config.timeout)`. There is no `transport.execute()` path for detached runs. Empirically confirmed by grep showing `transport.execute` is never reached from `run()`.

### E2. Docs mention `_parse_json_list scalar guard + empty NDJSON`, omit `_parse_json_item`
- ARCHITECTURE.md L401 lists "_parse_json_list scalar guard" as a remediation. It was added there but skipped for `_parse_json_item` (see A2). The docs implicitly promise the property across both.

### E3. `ports/streaming.py:11` stale `subprocess.run` reference
- "Unlike Transport.execute() which is batch (subprocess.run)" — already-stale per the remediation log that says CliTransport uses Popen.

### E4. ARCHITECTURE.md L141 vs port reality — `RuntimeProvider.create_managers` documented but not present (see A8).

### E5. Timeout type unification incomplete
- ARCHITECTURE.md v2 remediation (L401) mentions "timeout type unification (float)". But `ports/managers.py` still declares:
  - `build(timeout: int = 600)` L19
  - `push(timeout: int = 300)` L26
  - `pull(timeout: int = 300)` L29
  - `stop(timeout: int = 10)` L55
  - `restart(timeout: int = 10)` L58
- Only `exec_container` uses `float | None` (L88). Inconsistent contract across the same ABC.

### E6. `RuntimeCapabilities` is in `ports/`, but ARCHITECTURE.md L91 mixes layering prose
- L91 says: "RuntimeCapabilities lives in `ports/capabilities.py`" — correct. But the sentence then says "It is consumed by adapters and providers, never by the domain itself" — correct, but the architecture doc earlier (L20) lists `capabilities` under "Ports" hierarchy and there's no clear domain configuration source. Minor — the substance is fine.

## F. Minor

- `engine/cli.py:57`: passing `timeout` to `execute` for `--version`? No timeout is set, so a hung `docker --version` blocks forever (no `OperationTimeoutError`).
- `engine/cli.py:59`: `result.stdout.decode("utf-8", errors="replace")`. `--version` emits ASCII only today but "replace" may mask encoding issues arbitrarily.
- `discovery/cli.py:23`: catches `(FileNotFoundError, OSError, RuntimeNotAvailableError)` — but `transport.probe()` returns bool and **doesn't raise**. The except branch is dead code unless a factory raises.
- `container.py:79` `elif config.network != NetworkMode.BRIDGE`: silently omits `--network bridge` — fine for default semantics but means explicitly requesting BRIDGE is impossible. Minor.
- `container.py:85` silently drops `log_driver` when `supports_log_drivers` is False. Should at least raise/warn when the user explicitly requested a log driver the runtime can't honor.
- `container.py:118` `is_auth = getattr(self._parser, "is_auth_error", None)` — see A4.
- `factory.py:189-191`: `RuntimeFactory.create()` raises `NotImplementedError` on missing provider. Inconsistent with the rest of the codebase using `OciError` subclasses for errors. Mixes stdlib error type into module hierarchy.
- `adapters/_cancellation.py:39` `is_cancelled` is `@property` per port; ✓ correct everywhere.
- `adapters/engine/cli.py:48` `return self._caps` shadows type `RuntimeCapabilities` — fine.
- `factory.py:32,33` `Callable[..., Transport]` annotations are fine but every default impl takes `**kwargs` accepting, smuggled keys (`binary_resolver=`). Loose.

---

## Recommended Prioritized Fix Order

1. **A1 (host_ip drop)** — fix `container.py:110-116`; emit `host_ip:host_port:container_port/proto` when `host_ip is not None`. Add a regression test asserting `-p 127.0.0.1:8080:80/tcp`. Update D1/D6 to assert correct shape rather than forward the bug.
2. **A2 (`_parse_json_item` scalar guard)** — port the guard from `_parse_json_list` to `_parse_json_item` so malformed inspect returns `ParsingError` (which descends from `OciError`).
3. **A3 (`ProcessPipeReader` blocking fallback)** — drop the `fd.read(size)` branch; force fd-based reading (raise if `fileno()` doesn't work, or convert via `os.read` consistently). Remove the dead `isinstance(fd, int)` defensive check.
4. **A8/E4 (docs)** — update ARCHITECTURE.md L141 to remove `create_managers`; or reintroduce it on the provider and have the factory delegate. Pick one, eliminate drift. Also delete the unused `Managers` aggregate or actually use it.
5. **C1 (`_execute_list`)** — refactor the 4 managers to call `_execute_list`, or delete the helper. The doc claims the consolidation happened; make code and doc agree; add a test enforcing single-call-site (`wiring/test_manager_commands.py` can verify the base method is invoked).
6. **B1/B2** — strengthen the architecture linter to disallow adapter→adapter concrete imports; require injection. Remove the `or CliBinaryResolver()`/`or StdoutBufferStream()` fallbacks.
7. **A4 (`is_auth is not None`)** — drop the dead defensive check (since `BaseCliParser.is_auth_error` is always defined). Or genuinely make `is_auth_error` optional via a `NotImplemented` sentinel and skip parsers that don't override.
8. **A5** — change `pty.py:33-34` to raise `ValueError` for empty commands (transport concern, not container) or define a transport-level error in `OciError`.
9. **A6** — `pull()` should raise `ImageRuntimeError` (the `_generic_error`) and attach `command/exit_code/stderr`. Audit how `ImagePullAccessDeniedError` vs `ImageRuntimeError` should be typed for the parse-failed branch.
10. **A7** — `version()` should include `stderr`/`exit_code` in the raised error.
11. **E1** — either update the routing-matrix row to "streaming" or change the implementation back to using `transport.execute()` when `detach=True` (preferred — detach means we don't need streaming semantics).
12. **D2/D3** — fix `test_parsers_is_frozen_dataclass` to use the correct parser types; expand `test_factory_config_defaults_are_none` to assert every field is `None`.
13. **D5/D4** — drop dead `subprocess.run` patches; fix broken `"docker --version"` dict keys; (probably remove `RecordingTransport._probe_result` indirection).
14. **E5** — unify `timeout` types across `ports/managers.py`: `float | None` consistently.
15. **D7** — refactor to use spec=ImageManager via MagicMock, or keep as-is and add spec tests separately.
16. Remove `_NOT_PROBED` (C2), `Managers` aggregate if unused (A8), `_safe_int` where redundant.

Module version stays at `0.3.0`; suggest bumping to `0.4.0` after the above remediations + adding tests with `xfail` removed (conformance already removed xfail per the doc — only skipped on missing fixtures). All the above are **silent in the test suite** — the audit must be re-run periodically until either an audit-style regression suite covers *behavioral contracts* (host_ip round-trip, parser type guards, transport port-injection) or each finding is converted into a regression test in `tests/audit/`.