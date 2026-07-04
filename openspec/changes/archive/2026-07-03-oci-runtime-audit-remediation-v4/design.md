## Context

`oci-runtime` is at v0.3.0 with 868 passing tests and a clean hexagonal layering linter. Three prior audit-remedication rounds (guardrail, v1, v2, v3) plus a post-v3 hardening and a regression-fix commit are archived under `openspec/changes/archive/`. A fresh audit contrasted against that history shows the module is **not regressing** — the F/A/T regression guards all hold and zero adapter→adapter imports remain. The remaining defects fall into four distinct categories, each requiring a different remediation stance:

1. **Incomplete v3 remediations** — requirements that exist in the live `openspec/specs/` (with scenarios) but were never implemented (A4 auth context, `ProviderNotRegisteredError`) or were half-done (R1 fixed the adapter but not the port). These need **implementation + regression tests only**, no new spec text.
2. **Spec-level & fix-created defects** — the prune spec itself mis-documented Docker's capitalized `Deleted:` output (B1); the v2 timeout unification introduced a race (H3). These need **spec correction + code fix + fixture**.
3. **Half-finished consistency** — v3 relaxed `parse_size_to_bytes` to accept `2GB` but not the sibling `_MEMORY_LIMIT_RE` (B3). Needs **the second half of the v3 change**.
4. **Pre-existing bugs masked by missing fixtures** — `docker ps` crashes on published ports (B5); `_freeze_mapping` aliases the dict (B4); `matches_any_pattern` lowercases text only (H1); Podman drops HostIp-only bindings (H2). None were in any prior spec's scope. Need **new spec requirements + code fix + conformance fixtures**.

Constraint: stdlib-only, frozen dataclasses, ports-pure-ABC intent. The AST layering linter (`tests/architecture/test_layering.py`) is the hard gate and must stay green.

## Goals / Non-Goals

**Goals:**
- Close the three incomplete v3 remediations so the spec and code finally agree.
- Correct the spec-level prune defect and the fix-created timeout race.
- Finish the size-validation consistency so `RunConfig(memory_limit="2GB")` and `parse_size_to_bytes("2GB")` both accept the same forms.
- Fix the four pre-existing bugs and add the conformance fixtures (docker list with ports, prune, build, podman network) that would have caught them.
- Make the `PipeReader` port substitutable, the factory types non-lying, and the public API complete (`Parsers`, cancellation constructors, `ProviderNotRegisteredError`).
- Every BUG/H finding gets a regression test in `tests/audit/test_known_bugs.py`; every conformance gap gets a fixture.

**Non-Goals:**
- No new features, no new runtimes, no API redesign.
- No re-audit of the LOW cleanup items already stable (tty re-resolution, `stop` truncation, `_caps` unused state) — they are tracked in tasks as optional polish.
- No change to `version()`'s `OciError` contract (L18 retracted — it is correct per `oci-version-error-contract`).
- No broadening of `RuntimeKind` beyond keeping it extensible for the already-documented nerdctl example.

## Decisions

### D1 — Implementation-only fixes for already-specced requirements (A4, ProviderNotRegisteredError)
**Decision**: Do not write new spec text for these two; create regression tests + implement.
**Rationale**: The live specs already contain the requirements and scenarios (`oci-result-checker-port:70-72` A4 scenario; `oci-version-error-contract:19,29` ProviderNotRegisteredError requirements). Re-stating them in a delta would duplicate. Tasks.md references the existing requirement IDs.
**Alternatives considered**: MODIFY the existing requirements to sharpen them — rejected because the requirement text is already correct; MODIFIED-with-same-content is an anti-pattern flagged by the spec instructions.

### D2 — `RuntimeKind` extensibility for the documented nerdctl example
**Decision**: Keep `StrEnum` but add a `_missing_` classmethod that constructs an ad-hoc member for unknown values (or use `enum`'s native `StrEnum` flexibility). `RuntimeKind("nerdctl")` returns a member with `.value == "nerdctl"` that compares unequal to `DOCKER`/`PODMAN`.
**Rationale**: The existing spec scenario `RuntimeFactory().create(RuntimePreference(kind=RuntimeKind("nerdctl"), ...))` assumes construction succeeds. Today it raises `ValueError`. A `_missing_` hook is the minimal change that preserves the two known members while allowing the documented extension path.
**Alternatives**: (a) switch to a plain `str` alias enum (loses `isinstance` checks); (b) require callers to use `RuntimeKind.DOCKER` only (breaks the documented example). Both rejected.

### D3 — `_freeze_mapping` copies before wrapping
**Decision**: `object.__setattr__(self, name, MappingProxyType(dict(value)))`.
**Rationale**: `MappingProxyType` is a view, not a copy — the v2 "deep immutability" claim is false for every mapping field. `dict(value)` is a shallow copy; since domain mapping values are themselves immutable (`str`/`bytes`/`Path`), shallow copy is sufficient for deep immutability here. `_freeze_sequence` already does `tuple(value)` (a copy); mappings now match.
**Alternatives**: deep-copy via `copy.deepcopy` — rejected (unnecessary; values are immutable).

### D4 — Timeout race fix: check `process.poll()` before raising
**Decision**: In all three transports, after `reader.read()` returns and before the `if effective_token.is_cancelled` raise, insert `if process.poll() is not None: return RawExecResult(process.returncode, stdout, stderr)`.
**Rationale**: If the child already exited and closed its pipes, `read()` returned on EOF. The deadline token may have fired in the ~0.1s selector gap; treating that as timeout discards collected data and calls `process.kill()` on a dead process. Checking `poll()` distinguishes "done" from "still running + deadline expired".
**Alternatives**: check `is_cancelled` only before `read()`, not after — rejected (post-read wait phase also needs the check, per v2's own rationale).

### D5 — `PipeReader` ABC rename to `on_stdout`/`on_stderr`
**Decision**: Rename the ABC params to `on_stdout`/`on_stderr` and delete the `**kwargs` shim from `ProcessPipeReader.read()`.
**Rationale**: Adapters call `reader.read(on_stdout=…, on_stderr=…)`. The ABC declares `on_primary`/`on_secondary`, so any substitute impl without the shim raises `TypeError`. The port seam is fake. Renaming to what callers use makes the port substitutable. `on_primary`/`on_secondary` are PTY-generic terms but the only consumers are stdout/stderr handlers.
**Alternatives**: keep `on_primary`/`on_secondary` in the ABC and fix `container.py` to use those names — rejected (the ABC is internal-only; matching caller vocabulary is clearer and removes the shim entirely).

### D6 — Factory type narrowing without breaking the frozen config
**Decision**: Introduce a `ResolvedRuntimeFactoryConfig` (non-`Optional` fields) produced by `_resolve_config()`, or assign resolved fields via `object.__setattr__` on the frozen instance and expose a `# type: ignore`-free accessor. `RuntimeFactory.create()` consumes the resolved config.
**Rationale**: `dataclasses.replace(cfg, **dict)` is opaque to mypy → 57 "None not callable"/`**dict` errors. The runtime is correct; the types lie. A resolved-config type makes the post-resolution non-None guarantee static.
**Alternatives**: make every field non-Optional with sentinel defaults — rejected (breaks the "default None, lazy fill" pattern documented in ARCHITECTURE.md:231).

### D7 — Conformance fixtures captured, not synthetic
**Decision**: Extend `tests/conformance/capture.py` to capture `docker container ls` (with a published port), `docker/podman image prune --force`, `build` (from `echo FROM alpine | docker build`), and `podman network inspect bridge`. Commit the JSON fixtures.
**Rationale**: B5 (Docker list crash) and B1 (prune count) survived because no real-fixture anchor existed. Synthetic tests mock the exact layer where the bugs live. Real captures are the ground truth.
**Alternatives**: hand-write fixtures — rejected (prior audits showed hand-written fixtures sidestep the real CLI quirks, e.g. the `{{json .}}` Ports-as-string shape).

## Risks / Trade-offs

- **[Risk] `RuntimeKind._missing_` could mask typos** → Mitigation: the `_missing_` hook returns a member only for non-empty strings; `RuntimeFactory.create()` then raises `ProviderNotRegisteredError` for unregistered kinds, so a typo still fails loudly (just at the factory, not the enum).
- **[Risk] `PipeReader` ABC rename is a BREAKING internal API change** → Mitigation: only `CliContainerManager.logs()` and `CliStreamingTransport` call `read()`; both are updated in the same change. The layering linter confirms no other consumers.
- **[Risk] Conformance capture modifies the local docker/podman state (prune deletes images)** → Mitigation: `capture.py` already cleans up after itself (per v3 audit); prune capture uses a dedicated sentinel image tagged `conformance-prune-target` and is skipped when the runtime is absent.
- **[Risk] `RuntimeProvider.capabilities` property change breaks callers using `()`** → Mitigation: the factory is the only internal caller; updated in the same change. Marked BREAKING in the proposal.
- **[Trade-off] Adding ~15 regression tests grows `test_known_bugs.py` further** → Mitigation: consolidate the 8 copy-pasted manager-construction factories into one shared helper first (L20), then add the regression tests against the helper.

## Migration Plan

1. No external API removals — only additions (`Parsers`, cancellation constructors, `ProviderNotRegisteredError` to `__all__`) and one internal BREAKING (`RuntimeProvider.capabilities` property).
2. Implement in dependency order: domain fixes → port fixes → adapter fixes → factory → tests. Run `pytest` + `ruff` + the layering linter after each phase.
3. The conformance fixtures are captured once and committed; CI runs them as skip-if-runtime-absent (existing pattern).
4. Rollback: each fix is a separate commit; any single revert restores prior behavior without cascading.
