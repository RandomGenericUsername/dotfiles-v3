---
baseline_commit: 1180ee73cb16611b65d27120f245698325768e8f
---

# Story 1.6: Provision Use Case

Status: ready-for-dev

## Change Log

- 2026-08-05: Story created — ultimate context engine analysis completed; comprehensive developer guide created.

## Story

As an operator,
I want a `ProvisionMachineUseCase` that plans or applies machine state,
So that I can diff desired-vs-actual state before mutating the machine.

## Acceptance Criteria

1. Running the use case with `check=True` executes the executor in plan mode and makes no system changes (AC 1, FR-1)
2. Running it with `check=False` executes the executor in apply mode (AC 2, FR-2)
3. The use case resolves `os_family` via `IFactReader` to select `group_vars/{arch,debian-family}.yml` (AC 3, FR-9)
4. It resolves the install dir (`$XDG_DATA_HOME/dotfiles/`, default `~/.local/share/dotfiles/`) at plan time and passes it via the seam extra-vars (AC 4, FR-9)
5. Unit tests verify plan/apply behavior with fake ports (AC 5, FR-9, FR-1, FR-2, NFR-1, NFR-5)

## Tasks / Subtasks

- [ ] Create `src/provisioning/src/provisioning/application/` package (AC: 1-4)
  - [ ] `use_cases.py` — `class ProvisionMachineUseCase` with injectable ports + `provision(check: bool) -> ProvisionResult` (AC 1, 2, 3, 4)
  - [ ] `__init__.py` — re-export `ProvisionMachineUseCase` (mirror `ports/__init__.py` pattern)
- [ ] Unit tests with fake ports (AC: 5, NFR-5)
  - [ ] `tests/unit/application/__init__.py`
  - [ ] `tests/unit/application/test_provision_machine_use_case.py` — fake executor records `(playbook, check, extra_vars)`; fake fact reader returns canned family
- [ ] Verify against layering guard + full suite
  - [ ] `uv run pytest tests/architecture/test_layering.py` — application/ files scanned; `application` layer may import only `domain`/`ports`/`adapters`/`application`
  - [ ] `uv run pytest` — full suite green, no regressions (118 passing before this story)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean

## Dev Notes

### Use case contract — the AC-mandated wiring

`ProvisionMachineUseCase` is the application-layer orchestrator that wires the locked ports from Story 1.4:

- **Constructor injection** of both ports plus the playbook path (mirroring how `AnsibleExecutor` takes `inventory`/`tags` as constructor config — the ports only carry per-run data):
  ```python
  class ProvisionMachineUseCase:
      def __init__(
          self,
          executor: IProvisionExecutor,
          fact_reader: IFactReader,
          playbook: Path,
      ) -> None: ...
  ```
- **`provision(check: bool) -> ProvisionResult`** — the single entry point. With `check=True` it is plan mode; `check=False` is apply mode (AC 1, 2). The `check` value is passed straight through to `IProvisionExecutor.run(playbook, check, extra_vars)`.
- **Resolution order inside `provision`** (AC 3, 4):
  1. `os_family = self._fact_reader.os_family()` — returns `"arch"` or `"debian-family"` (the `group_vars` basename). This is the ONLY distro information the Python side ever reads (NFR-3 — never branch on distro beyond this seam).
  2. `install_dir = resolve_install_dir()` — `$XDG_DATA_HOME/dotfiles/`, default `~/.local/share/dotfiles/`.
  3. `return self._executor.run(self._playbook, check, {"install_dir": str(install_dir), "os_family": os_family})` — passes **exactly** the two seam extra-var keys Story 1.5's `test_extra_vars_carry_exactly_install_dir_and_os_family` locks. No other keys, no additions (seam contract lock, hardening note).
- Return the executor's `ProvisionResult` unchanged (it now carries `success`/`tasks`/`returncode`/`stderr` after Story 1.5's review hardening).

### Install dir resolution — exactly the SPEC/chaining-spine contract

- Per [Source: SPEC.md#7, chaining-spine.md#7, plan §3]:
  ```
  $XDG_DATA_HOME/dotfiles/  (default ~/.local/share/dotfiles/)
  ```
- Implement as a module-level helper so tests can assert it directly:
  ```python
  def resolve_install_dir() -> Path:
      data_home = os.environ.get("XDG_DATA_HOME")
      base = Path(data_home) if data_home else Path.home() / ".local" / "share"
      return base / "dotfiles"
  ```
- `os.environ`/`pathlib` are **allowed in the application layer** — the domain-only stdlib ban (`_DOMAIN_ALLOWED_STDLIB`, `_DOMAIN_BANNED_STDLIB`) applies to `domain/` alone; application is the next ring and may use `os`, `pathlib`, `subprocess`-adjacent stdlib. Do NOT put this helper in domain.
- The resolved path must be **absolute** (resolve `~` and any relative `$XDG_DATA_HOME`). `Path.home()` is absolute; `$XDG_DATA_HOME` may be relative — normalize with `.expanduser().resolve()` if needed.

### Which playbook? — `bootstrap.yaml` is the aggregate, but keep it injectable

- Plan §7 reconciliation shape: `dotfiles-provision plan` runs `ansible-playbook bootstrap.yaml --check`; `apply` runs `IProvisionExecutor.run(playbook, check=False)`. The aggregate `bootstrap.yaml` (Story 2.12) is the end-to-end playbook.
- The playbook path is **constructor config**, not a literal — Story 1.8's CLI supplies the real path (e.g. `ansible/playbooks/bootstrap.yaml`), and tests pass any `Path`. Default it to `Path("bootstrap.yaml")` in the constructor for convenience if a caller doesn't care.
- The use case does **NOT** glob manifests — `YamlManifestReader` (Story 1.5) reads one file; manifest content is consumed by the Ansible roles (Epic 2). The Python orchestrator reads only `ansible_os_family` (SPEC §Constraints, "reads only `ansible_os_family` (IFactReader)").

### CRITICAL — Story 1.3's layering guard activates for application/

Creating `application/` makes the last forward-compatible skip scenarios converge; the guard already knows the layer (no skip to delete, but the new files are now scanned):

1. **`test_no_layering_violations`** — `application/*.py` may import only `domain`, `ports`, `adapters`, `application` (`_ALLOWED_TARGETS["application"] = {"domain", "ports", "adapters", "application"}`). No `cli` imports.
2. **`test_adapters_import_no_application`** — adapters may NOT import application. Existing adapters don't; do not add such imports.
3. **`_classify_layer`** must resolve `application/use_cases.py` as `"application"` (layer by directory — same mechanism as adapters). Stdlib (`os`, `pathlib`) is fine; third-party roots derive from `pyproject.toml` (only `yaml` + declared deps are allowed — the use case needs none).
4. **Rule 5 cross-package** — never import `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`. Only `cli_output` + declared deps allowed (the use case imports neither).

### Style / tooling (repo conventions, from Stories 1.1–1.5)

- `from __future__ import annotations`, `requires-python >= 3.12`, ruff `line-length = 100`, double quotes, ruff selects `E F I N W UP B`.
- `mypy src tests` runs strict (`import-untyped` disabled) — **annotate every helper, fixture param, and test method**. Fully-typed fake bodies (no `...` stubs).
- `uv run pytest` from `src/provisioning/`.
- Standalone runner parity: `python tests/architecture/test_layering.py` must still exit 0 after `application/` exists.
- Re-export pattern from `ports/__init__.py`: `from provisioning.application.use_cases import ProvisionMachineUseCase` + `__all__ = ["ProvisionMachineUseCase"]`.

### What this story is NOT (scope guard)

- No `VerifyCapabilityUseCase` / `BootstrapUseCase` (Story 1.7), no `cli/` changes (Story 1.8), no manifests (`dotfiles/provisioning/*.yaml`, Story 2.1), no Ansible content (Epic 2).
- The use case does NOT construct adapters (no `AnsibleExecutor`/`YamlManifestReader`/`AnsibleFactReader` instantiation here) — it receives ports via the constructor. Composition (wiring real adapters) happens in Story 1.8's CLI.
- No distro branching beyond reading `IFactReader.os_family()`.

## Previous Story Intelligence

### Story 1.5 — Adapters (learnings that apply here)

- `AnsibleExecutor(inventory, tags, timeout=None, runner=None)` and `AnsibleFactReader(host="localhost", timeout=None, runner=None)` take operational config in the constructor; the ports carry only per-run data. Mirror this: the use case takes ports + playbook in the constructor, per-run input is just `check`.
- `ProvisionResult` is now `(success: bool, tasks: tuple[tuple[str, str], ...], returncode: int = 0, stderr: str = "")` — the seam contract test (`test_extra_vars_carry_exactly_install_dir_and_os_family`) asserts `--extra-vars` carries **exactly** `install_dir` + `os_family`. The use case is the caller that fills those two keys — get it right and the seam holds end-to-end.
- Adapters raise domain errors (`ManifestReadError`, `UnknownOsFamilyError`, `InvalidFactOutputError`, `ProvisionExecutorError`, `ProvisionTimeoutError`) — the use case does not need to catch them; let them propagate to the CLI (Story 1.8) which renders them.
- `YamlManifestReader.read(manifest_path)` parses ONE file — the use case does not glob manifests (that is not this story's job).

### Story 1.4 — Ports (learnings that apply here)

- Locked signatures the use case consumes:
  - `IProvisionExecutor.run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult` — `extra_vars` exists specifically so this use case can pass `install_dir` + `os_family`.
  - `IFactReader.os_family() -> str` — returns `"arch"` | `"debian-family"` (the `group_vars` basename, matching `Distro` values).
  - `IManifestReader.read(manifest_path: Path) -> ProvisionManifest` — NOT consumed by this use case.
- The 1.4 dev note: "Story 1.6's use case resolves both [install dir and os_family] and passes them through" — this story is where that promise lands.

### Story 1.3 — Hexagonal Boundary Lock (learnings that apply here)

- The layering guard is **fail-closed**: `_ALLOWED_TARGETS["application"]` is already defined; creating the dir turns on scanning of its files. Any `cli` import in `application/` will fail the guard.
- `_classify_layer` resolves by directory; `application/use_cases.py` classifies as `application` automatically. No guard edits expected.

### Story 1.2 — Domain Models and Enums (learnings that apply here)

- `Distro.ARCH = "arch"`, `Distro.DEBIAN_FAMILY = "debian-family"` — the values `IFactReader.os_family()` returns and the group_vars filenames. The use case treats them as opaque strings; it does not need to validate them (Story 1.5's `AnsibleFactReader` already fails loudly on unknown families).
- `ProvisionResult` shape from `provisioning/domain/models.py`.

### Story 1.1 — Scaffold (learnings that apply here)

- Package root: `src/provisioning/src/provisioning/`; tests live in `src/provisioning/tests/` (outside the scanned `_SRC_ROOT`).
- Only cross-package dep is `cli-output`; the application layer adds no dependencies.

## Architecture Compliance

- **In-package hexagon (plan §11 step 4):** application is the fourth ring — use cases wiring ports. `_ALLOWED_TARGETS["application"] = {"domain", "ports", "adapters", "application"}`; may NOT import `cli`.
- **FR-9 Use Cases:** `ProvisionMachineUseCase` per the PRD — plan=`check:True` / apply=`check:False`, resolving `os_family` via `IFactReader` and the install dir at plan time, passing both via the seam extra-vars — [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#177-182].
- **NFR-1 Idempotency / FR-2:** apply mode re-runs cleanly because Ansible is the state authority; the use case adds no state persistence (no `provisioning-state.json`).
- **NFR-3 Distro isolation:** the Python side reads only `ansible_os_family` to select `group_vars/{arch,debian-family}.yml`; `ProvisionMachineUseCase` is exactly that seam — [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#21, #44].
- **NFR-5 Testability:** use cases are testable with fake ports — no real `ansible-playbook`. This is the AC 5 requirement.
- **Seam contract lock (hardening):** the use case must pass exactly `install_dir` + `os_family` extra-vars — the keys Story 1.5's seam contract test and Story 1.6's PRD pin.

## Testing Requirements

- **`tests/unit/application/test_provision_machine_use_case.py`** — fake `IProvisionExecutor` records `(playbook, check, extra_vars)` and returns a fixed `ProvisionResult`; fake `IFactReader` returns a canned family. Assert:
  - `check=True` → executor called with `check=True` (plan mode, no system changes).
  - `check=False` → executor called with `check=False` (apply mode).
  - `extra_vars == {"install_dir": <resolved>, "os_family": <family>}` — exactly those two keys (seam contract).
  - The playbook passed is the one injected at construction.
  - The `ProvisionResult` from the executor is returned unchanged.
  - `resolve_install_dir()`: with `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))` → `tmp_path/dotfiles`; with `monkeypatch.delenv("XDG_DATA_HOME")` → `Path.home()/".local"/"share"/"dotfiles"` (use `monkeypatch` for `Path.home` too if needed to keep the test hermetic).
- `uv run pytest tests/unit/application/` — new tests green.
- `uv run pytest tests/architecture/test_layering.py` — application files scanned, no violations.
- `uv run pytest` — full suite green (was 118 passed / 0 skipped).
- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean.
- Standalone nicety: `python tests/architecture/test_layering.py` still exits 0.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-9 (§4.3), NFR-1/NFR-3/NFR-5 (§5)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — install dir, "reads only `ansible_os_family` (IFactReader)", §11 boundary
- Chaining spine: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md` — install dir = `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`)
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §7 reconciliation shape (plan → `bootstrap.yaml --check`), §11 step 4 (use cases), §3 (install-dir decision)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.6 ACs, FR-9, hardening (seam contract lock)
- Ports (locked contracts): `src/provisioning/src/provisioning/ports/{provision_executor,fact_reader,manifest_reader}.py`
- Domain: `src/provisioning/src/provisioning/domain/{models,enums}.py`
- Layering guard: `src/provisioning/tests/architecture/test_layering.py` — `_ALLOWED_TARGETS["application"]`
- Adapter seam test: `src/provisioning/tests/unit/adapters/test_ansible_executor.py` — `test_extra_vars_carry_exactly_install_dir_and_os_family`
- Port test shape (fake-port pattern): `src/provisioning/tests/unit/ports/`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#176-177] — `application/use_cases.py` file location
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#280] — plan §11 step 4: `application/use_cases.py` wiring ports → use cases
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#217-226] — plan §7 reconciliation shape (plan → `bootstrap.yaml --check`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#58] — locked decision: install dir = `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#233-247] — Story 1.6 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#177-182] — FR-9: use cases
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#7] — install dir `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#44] — Python orchestrator never branches on distro
- [Source: src/provisioning/src/provisioning/ports/provision_executor.py] — `run(playbook, check, extra_vars)` locked signature
- [Source: src/provisioning/src/provisioning/ports/fact_reader.py] — `os_family() -> str` locked signature
- [Source: src/provisioning/src/provisioning/domain/models.py] — `ProvisionResult(success, tasks, returncode, stderr)` shape
- [Source: src/provisioning/src/provisioning/domain/enums.py] — `Distro` values = group_vars filenames
- [Source: src/provisioning/tests/architecture/test_layering.py] — `_ALLOWED_TARGETS["application"]`, `test_no_layering_violations`
- [Source: src/provisioning/tests/unit/adapters/test_ansible_executor.py] — seam contract test (extra-var keys `install_dir`/`os_family`)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-05: Story created via create-story workflow — context loaded from PRD FR-9, SPEC, chaining-spine, plan §3/§7/§11, epics Story 1.6, prior stories 1.1–1.5, layering guard `_ALLOWED_TARGETS["application"]`.

### Completion Notes List

- (pending implementation)

### File List

- (pending implementation)
