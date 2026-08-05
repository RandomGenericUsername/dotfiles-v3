---
baseline_commit: 7b3c1aa
---

# Story 1.7: Verify and Bootstrap Use Cases

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-05: Story created — ultimate context engine analysis completed; comprehensive developer guide created.

## Story

As an operator,
I want `VerifyCapabilityUseCase` and `BootstrapUseCase`,
So that I can assert runtime preconditions and run the full aggregate provisioning.

## Acceptance Criteria

1. `VerifyCapabilityUseCase` asserts the four §12 runtime preconditions (binaries installed, assets placed, filesystem structure exists, settings files parseable) without reaching into provisioning internals (AC 1, FR-3, FR-9, NFR-7)
2. `BootstrapUseCase` runs the aggregate `bootstrap.yaml` end-to-end (AC 2, FR-4, FR-9)
3. Unit tests verify each use case with fake ports (AC 3, FR-9, FR-3, FR-4, NFR-7, NFR-5)

## Tasks / Subtasks

- [ ] Add `VerifyCapabilityUseCase` and `BootstrapUseCase` to `application/use_cases.py` (AC: 1, 2)
  - [ ] Constructor injection of `executor` + `fact_reader` + `playbook` (mirror `ProvisionMachineUseCase`), with sensible defaults `Path("verify.yaml")` / `Path("bootstrap.yaml")`
  - [ ] `verify() -> ProvisionResult` — runs the verify playbook with `check=False` (a real check, never `--check`)
  - [ ] `bootstrap(check: bool = False) -> ProvisionResult` — runs the aggregate playbook end-to-end; `check=True` supports `bootstrap --check`
  - [ ] Both pass the **exact** seam extra-vars `install_dir` + `os_family` (shared private helper, see Dev Notes)
  - [ ] Do NOT construct adapters, do NOT import `cli`, do NOT do filesystem checks — the executor port owns all I/O
- [ ] Update `application/__init__.py` (AC: 1, 2)
  - [ ] Re-export `VerifyCapabilityUseCase`, `BootstrapUseCase` (plus existing `ProvisionMachineUseCase`, `resolve_install_dir`); `__all__` must match `use_cases.py`
- [ ] Unit tests with fake ports (AC: 3, NFR-5)
  - [ ] `tests/unit/application/test_verify_capability_use_case.py`
  - [ ] `tests/unit/application/test_bootstrap_use_case.py`
- [ ] Verify against layering guard + full suite
  - [ ] `uv run pytest tests/architecture/test_layering.py` — application/ files scanned, no violations
  - [ ] `uv run pytest` — full suite green (was 127 passed / 0 skipped)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [ ] Standalone nicety: `python tests/architecture/test_layering.py` still exits 0

## Dev Notes

### The two use cases — the AC-mandated wiring (all in the existing `use_cases.py`)

Story 1.6 established the application-layer pattern: constructor injection of the locked ports (Story 1.4), per-run input as a method arg, seam extra-vars computed in the use case. Story 1.7 extends that same module with two sibling classes. Do NOT create new application files — the plan §11 step 4 lists all three use cases in `application/use_cases.py`.

```python
class VerifyCapabilityUseCase:
    def __init__(
        self,
        executor: IProvisionExecutor,
        fact_reader: IFactReader,
        playbook: Path = Path("verify.yaml"),
    ) -> None: ...

    def verify(self) -> ProvisionResult:
        # runs executor with check=False; extra_vars = seam (install_dir + os_family)
        ...

class BootstrapUseCase:
    def __init__(
        self,
        executor: IProvisionExecutor,
        fact_reader: IFactReader,
        playbook: Path = Path("bootstrap.yaml"),
    ) -> None: ...

    def bootstrap(self, check: bool = False) -> ProvisionResult:
        # runs executor with the passed check flag; extra_vars = seam
        ...
```

### What "asserts the four §12 preconditions" MEANS here (critical scope guard)

The four §12 runtime preconditions — binaries installed, assets placed, filesystem structure exists, settings files parseable — are **asserted by the Ansible `verify.yaml` playbook** (Epic 2, Story 2.12's verify role). `VerifyCapabilityUseCase` is the **Python orchestration seam**: it runs that playbook through `IProvisionExecutor.run(playbook, check=False, extra_vars)` and returns the `ProvisionResult` unchanged.

**The Python use case MUST NOT:**
- Implement capability checks itself (no `Path.exists()`, no `shutil.which()`, no parsing of `ansible -m setup` output beyond `IFactReader`).
- Reach into provisioning internals (no adapter imports, no reading manifests, no `verify.yaml` content knowledge).
- Instantiate any adapter — composition happens in Story 1.8's CLI, exactly as Story 1.6's dev note states.

This is the NFR-7 "without reaching into provisioning internals" contract: the use case touches only the two ports (executor + fact reader). Verification semantics live in Epic 2 content; the Python side only selects the playbook and the seam. Any temptation to "helpfully" add Python-side checks is a layering violation and scope creep.

### Verify runs with `check=False` always; bootstrap supports `--check`

- `verify()` passes `check=False` to the executor unconditionally — verification is a real assertion against provisioned locations, never a dry run.
- `bootstrap()` accepts `check: bool = False` so Story 1.8's CLI can wire `dotfiles-provision bootstrap --check` (FR-4 consequence: `bootstrap --check` completes cleanly with no mutation). Default `False` = end-to-end run (FR-4).

### The shared seam — one private helper, no triplication

All three use cases compute the identical seam: resolve the install dir, read `os_family`, pass exactly `{"install_dir": ..., "os_family": ...}` (Story 1.5's seam contract test locks these two keys and nothing else). Add a module-private helper so verify/bootstrap don't duplicate the 1.6 logic:

```python
def _seam_extra_vars(fact_reader: IFactReader) -> dict[str, str]:
    return {
        "install_dir": str(resolve_install_dir()),
        "os_family": fact_reader.os_family(),
    }
```

Use it in both new use cases. Optionally refactor `ProvisionMachineUseCase.provision()` to call it too — low risk, keeps the file DRY; the 1.6 tests already pin the exact extra-vars dict, so any change stays verified. Do not change `ProvisionMachineUseCase`'s public signature.

### Which playbooks?

- `BootstrapUseCase` default `playbook = Path("bootstrap.yaml")` — the aggregate that runs all roles in dependency order (`packages` → `cli_tools` → `filesystem` → `assets` → `default_palette` → `compositor_configs` → `symlinks` → `settings` → `verify`). [Source: epics Story 2.12 AC]
- `VerifyCapabilityUseCase` default `playbook = Path("verify.yaml")` — the verification playbook that asserts the ten done-criteria / four §12 preconditions. [Source: plan §7, plan §8 item 10]
- The playbook path is **constructor config** like Story 1.6, not a literal — Story 1.8's CLI supplies the real absolute paths (e.g. `ansible/playbooks/verify.yaml`). Tests pass any `Path`.

### Layering guard (Story 1.3) — already active for application/

Adding two classes to an existing `application/use_cases.py` file changes nothing structurally:

1. `_ALLOWED_TARGETS["application"] = {"domain", "ports", "adapters", "application"}` — the new classes import only `provisioning.domain.models` (ProvisionResult) + `provisioning.ports` (IFactReader, IProvisionExecutor), which 1.6 already does. No `cli` imports.
2. `_classify_layer` resolves by directory — `application/use_cases.py` is already classified `application`. No guard edits.
3. Rule 5 cross-package: no new third-party imports. No dependencies added.

### Style / tooling (repo conventions, from Stories 1.1–1.6)

- `from __future__ import annotations`, `requires-python >= 3.12`, ruff `line-length = 100`, double quotes, ruff selects `E F I N W UP B`, ignore `B905`.
- `mypy src tests` strict (`import-untyped` disabled) — annotate every helper, fixture param, and test method; fully-typed fake bodies (no `...` stubs).
- `uv run pytest` from `src/provisioning/`.
- Re-export pattern: `from provisioning.application.use_cases import ...` + matching `__all__` in both `use_cases.py` and `application/__init__.py` (the 1.6 review fixed an `__init__`/`__all__` mismatch — keep them in sync).
- Test fixtures use `monkeypatch: pytest.MonkeyPatch` annotations (1.6 mypy finding).

### What this story is NOT (scope guard)

- No `cli/` changes (Story 1.8), no manifests (`dotfiles/provisioning/*.yaml`, Story 2.1), no Ansible content or `verify.yaml`/`bootstrap.yaml` playbooks (Epic 2 — Story 2.12).
- No new ports. The existing three ports (executor / fact reader / manifest reader) fully suffice; `IManifestReader` is NOT consumed by these use cases.
- No Python-side verification logic, no adapter instantiation, no distro branching.
- Deferred from 1.6 review — "resolved spine path is opaque to callers; plan/apply can diverge" — is explicitly **Story 1.8 CLI scope**, not this story.

## Previous Story Intelligence

### Story 1.6 — Provision Use Case (the template to mirror)

- `ProvisionMachineUseCase(executor, fact_reader, playbook=Path("bootstrap.yaml"))` with `provision(check) -> ProvisionResult` — resolve `os_family` via `IFactReader`, resolve install dir via `resolve_install_dir()`, call `executor.run(playbook, check, {"install_dir": ..., "os_family": ...})`. Return the executor's `ProvisionResult` unchanged.
- `resolve_install_dir()` is a module-level helper in `use_cases.py` — reuse it directly; it is already exported and tested (`$XDG_DATA_HOME/dotfiles/`, default `~/.local/share/dotfiles/`, absolute).
- Adapter errors propagate uncaught to the CLI (Story 1.8) — verify/bootstrap do not catch them.
- 1.6 review fixes to carry forward: playbook has a constructor default; `__init__.py` exports must match `use_cases.__all__` exactly; annotate monkeypatch params.

### Story 1.5 — Adapters (seam contract the new classes must honor)

- `AnsibleExecutor` seam test locks extra-var keys `install_dir` + `os_family` exactly. The use cases are the callers that fill those two keys — same keys, same types (`str`), nothing else.
- `ProvisionResult(success, tasks, returncode, stderr)` — return unchanged.

### Story 1.4 — Ports (locked signatures)

- `IProvisionExecutor.run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult`
- `IFactReader.os_family() -> str` — `"arch"` | `"debian-family"`.
- `IManifestReader.read(manifest_path) -> ProvisionManifest` — NOT consumed here.

### Story 1.3 / 1.2 / 1.1

- Layering guard is fail-closed for `application/`; new classes must respect `_ALLOWED_TARGETS["application"]`.
- Package root `src/provisioning/src/provisioning/`; tests in `src/provisioning/tests/`; only cross-package dep is `cli-output` (application adds none).

## Architecture Compliance

- **In-package hexagon (plan §11 step 4):** all three use cases live in `application/use_cases.py` — the application ring wiring ports. `_ALLOWED_TARGETS["application"] = {"domain", "ports", "adapters", "application"}`; may NOT import `cli`.
- **FR-3 / FR-9 / NFR-7:** `VerifyCapabilityUseCase` asserts the four §12 preconditions via the executor port (the verify playbook), never reaching into provisioning internals — [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#177-182].
- **FR-4 / FR-9:** `BootstrapUseCase` runs the aggregate `bootstrap.yaml` end-to-end — [Source: prd.md#112-116].
- **Seam contract lock (hardening):** both new use cases pass exactly `install_dir` + `os_family` extra-vars — the keys Story 1.5's seam contract test and Story 1.6 pin.
- **NFR-2 (No persisted provisioning state):** verify re-derives state on demand via the verify playbook — no `provisioning-state.json`.
- **NFR-5 (Testability):** use cases testable with fake ports — no real `ansible-playbook`. AC 3 requirement.

## Testing Requirements

- **`tests/unit/application/test_verify_capability_use_case.py`** — fake `IProvisionExecutor` records `(playbook, check, extra_vars)`; fake `IFactReader` returns canned family. Assert:
  - `verify()` calls the executor with `check=False` (never `--check`).
  - The injected playbook is passed through (default `Path("verify.yaml")` when not injected).
  - `extra_vars == {"install_dir": <resolved>, "os_family": <family>}` — exactly those two keys.
  - The executor's `ProvisionResult` is returned unchanged.
- **`tests/unit/application/test_bootstrap_use_case.py`** — same fakes. Assert:
  - `bootstrap()` with default calls the executor with `check=False` (end-to-end).
  - `bootstrap(check=True)` calls the executor with `check=True` (supports `bootstrap --check`).
  - The injected playbook is passed through (default `Path("bootstrap.yaml")`).
  - `extra_vars == {"install_dir": ..., "os_family": ...}` — exactly those two keys.
  - The executor's `ProvisionResult` is returned unchanged.
- `uv run pytest tests/unit/application/` — new tests green.
- `uv run pytest tests/architecture/test_layering.py` — no violations (16 source files, application scanned).
- `uv run pytest` — full suite green (was 127 passed / 0 skipped).
- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean.
- Standalone nicety: `python tests/architecture/test_layering.py` still exits 0.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-3, FR-4, FR-9 (§4.3), NFR-5/NFR-7 (§5)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — §12 preconditions constraint, CAP-3/CAP-4, §11 boundary
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §7 reconciliation shape (verify → verify.yaml, bootstrap → bootstrap.yaml), §8 done-criteria item 10, §11 step 4
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.7 ACs, FR-9, FR-3, FR-4
- Domain: `src/provisioning/src/provisioning/domain/models.py` — `ProvisionResult` shape
- Ports (locked contracts): `src/provisioning/src/provisioning/ports/{provision_executor,fact_reader}.py`
- Application (extend this): `src/provisioning/src/provisioning/application/use_cases.py` + `__init__.py`
- Layering guard: `src/provisioning/tests/architecture/test_layering.py` — `_ALLOWED_TARGETS["application"]`
- Port test shape (fake-port pattern): `src/provisioning/tests/unit/ports/`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#249-261] — Story 1.7 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#102-116] — FR-3 verify / FR-4 bootstrap
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#177-182] — FR-9 use cases (VerifyCapabilityUseCase, BootstrapUseCase)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#336] — NFR-7 verify-gate contract
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#37-39] — four §12 preconditions assertable via VerifyCapabilityUseCase
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#28-30] — CAP-4 one-command bootstrap
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#215-228] — §7 reconciliation shape (verify → verify.yaml; bootstrap → bootstrap.yaml)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#234-249] — §8 done-criteria (item 10 = §12 preconditions)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#275-287] — §11 implementation order (step 4: all three use cases in application/use_cases.py)
- [Source: src/provisioning/src/provisioning/application/use_cases.py] — existing `ProvisionMachineUseCase` + `resolve_install_dir` to mirror
- [Source: src/provisioning/src/provisioning/ports/provision_executor.py] — `run(playbook, check, extra_vars)` locked signature
- [Source: src/provisioning/src/provisioning/ports/fact_reader.py] — `os_family() -> str` locked signature
- [Source: src/provisioning/tests/unit/application/test_provision_machine_use_case.py] — fake-port test pattern to mirror

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-05: Story created via create-story workflow — context loaded from epics Story 1.7 ACs, PRD FR-3/FR-4/FR-9/NFR-7, SPEC §12 preconditions + CAP-3/CAP-4, plan §7/§8/§11, prior story 1.6 (use-case pattern), seam contract from 1.5, layering guard `_ALLOWED_TARGETS["application"]`.

### Completion Notes List

- (Pending dev-story implementation.)

### File List

- `src/provisioning/src/provisioning/application/use_cases.py` (update — add two classes + `_seam_extra_vars` helper)
- `src/provisioning/src/provisioning/application/__init__.py` (update — re-export new use cases)
- `src/provisioning/tests/unit/application/test_verify_capability_use_case.py` (new)
- `src/provisioning/tests/unit/application/test_bootstrap_use_case.py` (new)
