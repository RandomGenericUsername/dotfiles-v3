## Context

The oci-runtime module went through 3 audit cycles (v1, v2, v3) culminating in commit `1953540` which moved concrete cancellation/pipe-reader implementations from adapters to ports and tightened the architecture linter. That commit fixed real coupling problems but introduced 3 regressions by removing adapter fallbacks while keeping `| None` type hints. Additionally, ~15 AUDIT-v3 findings were never addressed.

## Goals / Non-Goals

**Goals:**
- Fix all 3 regressions from 1953540 (R1-R3)
- Resolve remaining AUDIT-v3 findings that are low-risk and high-value
- Add regression tests for each fix
- No structural architecture changes — targeted fixes only

**Non-Goals:**
- Moving concrete classes out of ports (already addressed, deliberate decision)
- Code deduplication across adapters (cosmetic, high churn)
- Full domain-layer edge case fixes (#6-9 from new audit)
- Creating a `shared/` layer (evaluated and rejected)

## Framework: Where Code Belongs

| Layer | Contains | May Import From |
|-------|----------|----------------|
| domain | Pure logic, value objects, enums, exceptions, helpers | stdlib only |
| ports | ABCs, value objects, port-level aggregates | domain |
| adapters | Concrete implementations | domain, ports |
| factory | Composition root | domain, ports, adapters |

## Decisions

### D1. Transport constructors require collaborators (not `| None`)

**Chosen:** Remove `| None` from `binary_resolver` and `output_stream` parameters.

**Why:** The factory always provides these values. The `| None` type hint is a lie that causes `AttributeError` crashes. The old fallbacks (`or CliBinaryResolver()`, lazy `StdoutBufferStream` import) were removed for good reason (AUDIT-v3 B2 — intra-adapter coupling). Keeping the `| None` without the fallback is the worst of both worlds: the type system says `None` is valid, but the code crashes.

**Alternatives rejected:**
- Re-adding fallbacks: Re-introduces adapter→adapter coupling (the exact problem 1953540 fixed)
- Making the code null-safe with guards: Adds dead code paths that can never execute in production

### D2. Narrow `exec_container` except clause

**Chosen:** Change `except ContainerRuntimeError: pass` to `except ContainerNotFoundError: pass`.

**Why:** The intent of the broad except was to handle the case where exec succeeds but the container is gone (return exit code, don't raise). But `ContainerRuntimeError` is the parent of `ContainerNotFoundError` — catching the parent catches ALL runtime errors including permission denied, disk corruption, etc. Only not-found should be suppressed.

**Evidence:** The old code (pre-1953540) explicitly checked `self._parser.is_not_found_error(stderr_str)` and only raised `ContainerNotFoundError`. The broad except was an overcorrection during refactoring.

### D3. `host_ip` port flag building

**Chosen:** Emit `-p <host_ip>:<host_port>:<container_port>/<protocol>` when `host_ip is not None`.

**Why:** `PortMapping.host_ip` is a required field (no default) — the architecture explicitly states it exists to "prevent a misleading 0.0.0.0 default." Ignoring it reintroduces exactly that default. The fix follows Docker CLI semantics: `-p [host_ip:]host_port:container_port[/protocol]`.

**Alternatives rejected:**
- Making `host_ip` optional with `None` default: Contradicts the architectural intent (AUDIT-v3 A1 explicitly documents this as a security concern)
- Warning when `host_ip` is set: Silent warning doesn't fix the security issue

### D4. Delete dead code rather than fix it

**Chosen:** Delete `_execute_list`, `_NOT_PROBED`, `Managers` aggregate rather than making them work.

**Why:** These are dead code with no callers. Fixing dead code is wasted effort. The ARCHITECTURE.md claims about `_execute_list` dedup are false — the dedup never happened. Deleting the dead code and updating the doc is cleaner than making dead code live.

### D5. Timeout type unification

**Chosen:** Change `timeout: int` to `float` across all manager ABCs.

**Why:** `exec_container` already uses `float | None`. The other methods use `int` with defaults. Python's `int` is a subtype of `float` in the type system, so existing callers passing `int` values continue to work. The change makes the contract consistent and allows sub-second timeouts where needed.

## Component Map

### Modified files

| File | Change |
|------|--------|
| `adapters/transport/pty.py` | Remove `| None` from `output_stream` param |
| `adapters/transport/cli.py` | Remove `| None` from `binary_resolver` param |
| `adapters/transport/streaming.py` | Remove `| None` from `binary_resolver` param |
| `adapters/managers/container.py` | Narrow except to `ContainerNotFoundError`; fix `host_ip` in port flags |
| `adapters/managers/base.py` | Delete `_execute_list` (or entire file if empty) |
| `adapters/binary.py` | Delete `_NOT_PROBED` |
| `ports/streaming.py` | Fix stale docstring |
| `ports/managers.py` | Unify timeout types to `float` |
| `ports/aggregates.py` | Delete `Managers` aggregate |
| `ports/__init__.py` | Remove `Managers` from exports |
| `docs/ARCHITECTURE.md` | Remove `create_managers` claim, fix `_execute_list` claim |
| `tests/...` | ~10 test additions/fixes |

## Migration Plan

1. Fix regressions R1-R3 (transport signatures + except clause)
2. Fix A1 (host_ip)
3. Delete dead code (C1, C2, A8)
4. Fix doc/type drift (C4, E5)
5. Fix test quality (D2-D5, D7)
6. Add regression tests (T1-T4)
7. Run full suite, update ARCHITECTURE.md

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Constructor signature change breaks tests | Fix tests in same phase; factory always provides values |
| Narrowing except clause reveals hidden errors | That's the point — real errors should propagate |
| Deleting dead code breaks doc claims | Update ARCHITECTURE.md in same change |
| Timeout type change breaks existing callers | `int` is a subtype of `float` in Python; no breakage |
