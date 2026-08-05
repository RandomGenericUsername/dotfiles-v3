---
baseline_commit: 3430c4055b8af65cac6c1b8377bea66692699c7b
---

# Story 1.4: Ports

Status: review

## Change Log

- 2026-08-05: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-05: Story implemented — `src/provisioning/src/provisioning/ports/` created with the three locked ABC contracts: `IProvisionExecutor.run(playbook, check, extra_vars) -> ProvisionResult` (seam carries `install_dir` + `os_family`), `IManifestReader.read(path) -> ProvisionManifest`, `IFactReader.os_family() -> str`; each abstract body raises `NotImplementedError`; `ports/__init__.py` re-exports all three. 15 contract tests (5 per port: ABC, abstract, cannot-instantiate, NotImplementedError, fake satisfies contract). Story 1.3 layering guard's ports tests now run (were skipped) and pass. Full suite 72 passed / 1 skipped (was 51/3), ruff + mypy strict clean, standalone `test_layering.py` exits 0 over 10 source files. Status → review.

## Story

As an operator,
I want explicit port abstractions for provisioning execution,
So that adapters and use cases stay decoupled and testable.

## Acceptance Criteria

1. `IProvisionExecutor` abstracts `ansible-playbook` with a `check: bool` parameter (AC 1, FR-8)
2. `IManifestReader` reads `dotfiles/provisioning/*.yaml` manifests (AC 2, FR-8)
3. `IFactReader` exposes `os_family() -> str` selecting `group_vars` without inspecting packages (AC 3, FR-8)
4. All three are abstract base classes (Protocol-compatible) that raise `NotImplementedError` on unimplemented methods (AC 4, FR-8)
5. Unit tests verify each port's interface contract with fakes (AC 5, FR-8, NFR-5)

## Tasks / Subtasks

- [x] Create `src/provisioning/src/provisioning/ports/` package (AC: 1, 2, 3, 4)
  - [x] `provision_executor.py` — `class IProvisionExecutor(ABC)` with abstract `run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult` (AC 1; `extra_vars` is the locked seam — see Dev Notes)
  - [x] `manifest_reader.py` — `class IManifestReader(ABC)` with abstract `read(manifest_path: Path) -> ProvisionManifest` (AC 2)
  - [x] `fact_reader.py` — `class IFactReader(ABC)` with abstract `os_family() -> str` (AC 3)
  - [x] `__init__.py` — re-export all three ports (mirror `src/shared/oci-runtime/src/oci_runtime/ports/__init__.py`)
  - [x] Every abstract method body is exactly `raise NotImplementedError` (AC 4)
- [x] Port contract unit tests (AC: 5, NFR-5)
  - [x] `tests/unit/ports/__init__.py`
  - [x] `tests/unit/ports/test_provision_executor.py` — ABC subclass, `run` abstract, cannot instantiate, calling the unimplemented method raises `NotImplementedError`, fake subclass satisfies the interface
  - [x] `tests/unit/ports/test_manifest_reader.py` — same shape for `IManifestReader.read`
  - [x] `tests/unit/ports/test_fact_reader.py` — same shape for `IFactReader.os_family`
- [x] Verify against layering guard + full suite
  - [x] `uv run pytest tests/architecture/test_layering.py` — `test_ports_files_are_abstract_only` and `test_ports_import_no_adapters` now RUN (ports/ exists; previously skipped) and pass
  - [x] `uv run pytest` — full suite green, no regressions
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean

## Dev Notes

### Port contracts — exact signatures (locked for Stories 1.5 and 1.6)

- **`IProvisionExecutor`** — abstracts `ansible-playbook`:
  ```python
  class IProvisionExecutor(ABC):
      @abstractmethod
      def run(
          self,
          playbook: Path,
          check: bool,
          extra_vars: Mapping[str, str],
      ) -> ProvisionResult:
          raise NotImplementedError
  ```
  `check: bool` is the AC-mandated plan/apply switch (`plan` → `check=True`, `apply` → `check=False`).
  **`extra_vars` MUST be on the port now** — Story 1.5's seam contract test asserts `AnsibleExecutor` passes exactly the extra-var keys `install_dir` and `os_family`, and Story 1.6's use case resolves both and passes them through. If the port omits `extra_vars`, the adapter cannot receive them without violating the interface. `ProvisionResult` (domain, Story 1.2) = `success: bool` + `tasks: tuple[tuple[str, str], ...]` — the "per-task changed/ok results" Story 1.5 surfaces.
- **`IManifestReader`** — reads one declarative manifest:
  ```python
  class IManifestReader(ABC):
      @abstractmethod
      def read(self, manifest_path: Path) -> ProvisionManifest:
          raise NotImplementedError
  ```
  `ProvisionManifest` (domain, Story 1.2) = `kind: str` + `entries: tuple[Spec, ...]`. The use case globs `dotfiles/provisioning/*.yaml` itself; the port only parses one file at a time.
- **`IFactReader`** — distro seam:
  ```python
  class IFactReader(ABC):
      @abstractmethod
      def os_family(self) -> str:
          raise NotImplementedError
  ```
  Returns the `group_vars` basename (`"arch"` | `"debian-family"`), matching `Distro` values (Story 1.2: "Values MUST match the group_vars filenames so `IFactReader.os_family()` maps directly onto this enum"). Never inspects packages — it only selects which `group_vars` apply.

### "Protocol-compatible" — do NOT reach for `typing.Protocol`

AC 4 says "abstract base classes (Protocol-compatible)". Use **`class X(ABC)`** with `@abstractmethod`, exactly like the mirror (`src/shared/oci-runtime/src/oci_runtime/ports/engine.py`). "Protocol-compatible" means a fake/adapters that implement the same method set satisfy the interface structurally — it does **not** mean define `typing.Protocol` classes. Using ABC keeps Story 1.3's `test_ports_files_are_abstract_only` classification simple and matches the mirror.

### CRITICAL — Story 1.3's layering guard now exercises ports/ (no longer skipped)

Story 1.3's `test_layering.py` had forward-compatible skips for the empty `ports/` dir. Creating `ports/` activates them:

1. **`test_ports_files_are_abstract_only`** — every **top-level** class in `ports/*.py` must classify as `"abc"`. The classifier (post-review hardening) handles `class X(ABC)` + `@abstractmethod` with plain imports, aliased imports, `Protocol`, and `async def` — but the simple pattern below is guaranteed safe:
   ```python
   from abc import ABC, abstractmethod
   class IProvisionExecutor(ABC):
       @abstractmethod
       def run(...) -> ProvisionResult:
           raise NotImplementedError
   ```
   Do NOT add helper/concrete classes at the top level of a ports file (e.g. an exception type) — they would be flagged. `_PORTS_ALLOWED_AGGREGATES` is empty; do not add to it.
2. **`test_ports_import_no_adapters`** — ports may import only `provisioning.domain.*` + `provisioning.ports.*` (layer `ports`). Domain imports are fine (`from provisioning.domain.models import ProvisionManifest, ProvisionResult`). No `provisioning.application` / `provisioning.cli` / `provisioning.adapters` imports — those layers don't exist yet and must not be imported.
3. **`test_no_layering_violations`** — ports files are now scanned. Stdlib (`abc`, `collections.abc`, `pathlib`, `typing`) and domain imports only.

### File layout — match the plan §11 exactly

From [Source: docs/01-dotfiles-provisioning-phase1-plan.md#172-175]:
```
src/provisioning/ports/
├── __init__.py            # re-export the three ports
├── provision_executor.py  # IProvisionExecutor (abstracts ansible-playbook; check: bool)
├── manifest_reader.py     # IManifestReader
└── fact_reader.py         # IFactReader.os_family() -> str (thin: selects group_vars, never inspects packages)
```
Re-export pattern from [Source: src/shared/oci-runtime/src/oci_runtime/ports/__init__.py]: import each port and list it in `__all__`. The `ports/__init__.py` re-exports are what adapters/use cases import from.

### Zero-I/O domain stays pure — ports may use stdlib freely

The domain stdlib allowlist / banned set applies to `domain/` only. Ports live in the next ring and may use `pathlib.Path`, `collections.abc.Mapping`, etc. The port interface itself performs no I/O — it only declares the seam.

### Style / tooling (repo conventions, from Stories 1.1–1.3)

- `from __future__ import annotations`, `requires-python >= 3.12`, ruff `line-length = 100`, double quotes.
- `mypy src tests` runs strict (`import-untyped` disabled) — **annotate every helper, fixture param, and test method** (Story 1.1 review finding: untyped test params fail mypy).
- `uv run pytest` from `src/provisioning/`.
- Standalone runner parity: `python tests/architecture/test_layering.py` must still exit 0 after ports/ exists.

## Previous Story Intelligence

### Story 1.3 — Hexagonal Boundary Lock (learnings that apply here)

- The layering guard is **fail-closed** after review: unknown top-level dirs are violations, imports resolve to real files, and `from provisioning import <name>` expands to the layer. ports/ is a known layer — nothing special needed.
- `_classify_ports_class` (post-review) recognizes `class X(ABC)` with `@abstractmethod` — including `async def` and aliased imports — and only checks **top-level** classes. Keep each ports file to a single top-level ABC.
- Tests were 51 passed / 3 skipped before this story. The 3 skips were `test_ports_import_no_adapters`, `test_ports_files_are_abstract_only` (both gated on `ports/` existing), and `test_adapters_import_no_application` (gated on `adapters/`). Creating `ports/` turns the first two into live assertions; only `test_adapters_import_no_application` stays skipped until Story 1.5.
- ruff + mypy strict clean is the entry gate; keep it that way.

### Story 1.2 — Domain Models and Enums (learnings that apply here)

- Domain exports `ProvisionManifest`, `ProvisionResult`, `Spec`, `MachineState` from `provisioning/domain/models.py` and `Distro`, `Capability`, `CapabilityKind`, `AssetKind` from `provisioning/domain/enums.py` (see `domain/__init__.py` re-exports).
- `ProvisionResult` = `(success: bool, tasks: tuple[tuple[str, str], ...])`; `ProvisionManifest` = `(kind: str, entries: tuple[Spec, ...])`.
- `Distro.ARCH = "arch"`, `Distro.DEBIAN_FAMILY = "debian-family"` — these ARE the group_vars filenames the `IFactReader.os_family()` seam selects.

### Story 1.1 — Scaffold (learnings that apply here)

- Package layout: `src/provisioning/src/provisioning/` is the package root; tests live in `src/provisioning/tests/` (outside the scanned `_SRC_ROOT`).
- `mypy` strict requires annotated test params.
- Only cross-package dep is `cli-output`; the ports files add no dependencies.

## Architecture Compliance

- **In-package hexagon (plan §11 step 2):** ports is the second ring. It imports domain only (allowed by `_ALLOWED_TARGETS["ports"] = {"domain", "ports"}`) and is the base for `adapters/` (Story 1.5).
- **NFR-5 Testability:** ports are pure ABCs — no I/O, no implementation — so adapters (1.5) and use cases (1.6) are testable with fakes. This story delivers the ABC-only contract and proves it with fake-based tests.
- **FR-8 Ports:** all three ports per the PRD description — [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#161-167].
- **Seam contract lock (Story 1.5 forward):** `IProvisionExecutor.run(..., extra_vars)` carries exactly the `install_dir` + `os_family` extra-vars keys; `IFactReader.os_family()` supplies the os_family value; the install dir is resolved by the use case (Story 1.6).

## Testing Requirements

- Mirror the contract-test shape from [Source: src/shared/oci-runtime/tests/unit/ports/test_engine.py]: per port, assert (a) `issubclass(Port, ABC)`, (b) each method is abstract (`Port.method.__isabstractmethod__`), (c) `pytest.raises(TypeError)` on `Port()`, (d) calling the unimplemented method raises `NotImplementedError` (`with pytest.raises(NotImplementedError): Port.run(object(), Path("x"), True, {})`), (e) a fully-implemented fake subclass instantiates, passes `isinstance(fake, Port)`, and round-trips its arguments/return through the declared signature.
- Fakes must be concrete subclasses implementing every abstract method (no `...` stubs — full typed bodies), because `mypy --strict` enforces implementations.
- `uv run pytest tests/unit/ports/` — new tests green.
- `uv run pytest tests/architecture/test_layering.py` — the two ports tests run (not skipped) and pass.
- `uv run pytest` — full suite green (expect 51 passed + N new, 1 remaining skip for adapters/).
- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean.
- Optional mirror nicety: `python tests/architecture/test_layering.py` still exits 0.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-8 (§4.2), NFR-5 (§5)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — §11 boundary, "reads only `ansible_os_family` (IFactReader)"
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §11 step 2, file structure §6 (ports layout), reconciliation shape §7 (`IFactReader` → `group_vars/{arch,debian-family}.yml`)
- Architecture: `docs/99-dotfiles-hexagonal-architecture.md` — §8 (hexagonal style), §11 (bounded contexts)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.4, FR-8, NFR-5
- Mirror: `src/shared/oci-runtime/src/oci_runtime/ports/` and `src/shared/oci-runtime/tests/unit/ports/test_engine.py`
- Domain: `src/provisioning/src/provisioning/domain/{models.py,enums.py}`
- Layering guard: `src/provisioning/tests/architecture/test_layering.py`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#172-175] — ports file structure (`provision_executor.py`, `manifest_reader.py`, `fact_reader.py`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#278] — plan §11 step 2: ports pure, no Ansible, no I/O
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#200-214] — Story 1.4 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#161-167] — FR-8: ports description
- [Source: src/shared/oci-runtime/src/oci_runtime/ports/engine.py] — ABC port pattern (read fully before implementing)
- [Source: src/shared/oci-runtime/src/oci_runtime/ports/__init__.py] — re-export pattern
- [Source: src/shared/oci-runtime/tests/unit/ports/test_engine.py] — contract-test shape
- [Source: src/provisioning/src/provisioning/domain/models.py] — `ProvisionResult`, `ProvisionManifest` signatures
- [Source: src/provisioning/src/provisioning/domain/enums.py] — `Distro` values (`arch`, `debian-family`) = group_vars filenames
- [Source: src/provisioning/tests/architecture/test_layering.py] — active ports guards (`test_ports_files_are_abstract_only`, `test_ports_import_no_adapters`)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- RED confirmed: 3 collection errors before `provisioning/ports` existed (imports unresolved).
- mypy strict flagged 6 errors on the contract tests: `Port.method.__isabstractmethod__` not recognized on the bound `Callable` type (`attr-defined`) and `Port()` instantiation of an abstract class (`abstract`). Resolved with targeted `# type: ignore[attr-defined]` / `# type: ignore[abstract]` comments — the standard strict-mode pattern for abstractness contract tests (same friction the oci-runtime mirror tests would hit).
- Layering guard verified after ports/ created: `test_ports_files_are_abstract_only` + `test_ports_import_no_adapters` went from skip → pass (22→29 tests in test_layering.py; full suite 51/3 → 72/1: +15 port contract tests, +4 parametrized layering cases over the new ports files, +2 formerly-skipped ports guards).

### Completion Notes List

- Created `src/provisioning/src/provisioning/ports/` with the three locked ABC contracts (mirrors `oci_runtime/ports` ABC pattern exactly):
  - `IProvisionExecutor.run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult` — `check` is the plan/apply switch; `extra_vars` is the locked seam that Story 1.5's seam-contract test and Story 1.6's use case depend on (`install_dir` + `os_family` keys).
  - `IManifestReader.read(manifest_path: Path) -> ProvisionManifest` — one file at a time; the use case globs `dotfiles/provisioning/*.yaml`.
  - `IFactReader.os_family() -> str` — returns the `group_vars` basename (`arch`/`debian-family`), matching `Distro` values; never inspects packages.
  - `ports/__init__.py` re-exports all three (mirror `oci_runtime/ports/__init__.py`).
- AC 4 ("Protocol-compatible", raise NotImplementedError): used `class X(ABC)` + `@abstractmethod` with `raise NotImplementedError` bodies (NOT `typing.Protocol`) — matches the layering guard's ports-ABC classification and the mirror.
- AC 5 / NFR-5: 15 contract tests (5 per port) — `issubclass(port, ABC)`, method abstract, `pytest.raises(TypeError)` on instantiation, `pytest.raises(NotImplementedError)` on the unimplemented method, and a fully-typed fake subclass satisfying the interface.
- Layering guard activated: the two forward-compatible ports tests now execute and pass; only `test_adapters_import_no_application` remains skipped until `adapters/` exists (Story 1.5).
- No new dependencies; scope respected — ports ABCs and their contract tests only, no adapters/use cases (later stories).
- Tests: 72 passed / 1 skipped; `ruff check` + `ruff format --check` clean; `mypy src tests` strict clean (17 files); standalone `python tests/architecture/test_layering.py` exits 0 ("OK: 10 source files checked").

### File List

- `src/provisioning/src/provisioning/ports/__init__.py` (new)
- `src/provisioning/src/provisioning/ports/provision_executor.py` (new)
- `src/provisioning/src/provisioning/ports/manifest_reader.py` (new)
- `src/provisioning/src/provisioning/ports/fact_reader.py` (new)
- `src/provisioning/tests/unit/ports/__init__.py` (new)
- `src/provisioning/tests/unit/ports/test_provision_executor.py` (new)
- `src/provisioning/tests/unit/ports/test_manifest_reader.py` (new)
- `src/provisioning/tests/unit/ports/test_fact_reader.py` (new)
