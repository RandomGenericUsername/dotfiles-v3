---
baseline_commit: feaf28e5f5cdd601489127e861410cf21bcd6148
---

# Story 1.5: Adapters

Status: review

## Change Log

- 2026-08-05: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-05: Implemented all three adapters (YamlManifestReader, AnsibleFactReader, AnsibleExecutor) + 20 unit tests with injected fake runners; PyYAML>=6.0 declared in pyproject.toml; layering guard `test_adapters_import_no_application` live (no skips); full suite 97 passed / 0 skipped; ruff + mypy clean.

## Story

As an operator,
I want concrete adapters implementing the provisioning ports,
So that the orchestrator can read manifests, detect OS family, and drive `ansible-playbook`.

## Acceptance Criteria

1. `YamlManifestReader` parses `dotfiles/provisioning/*.yaml` into domain `ProvisionManifest` objects (AC 1, FR-10)
2. `AnsibleFactReader` parses `ansible -m setup` output for `ansible_os_family` (AC 2, FR-10)
3. `AnsibleExecutor` shells to `ansible-playbook` with `-i`, `--tags`, `--check`, and `--extra-vars`, surfacing per-task changed/ok results (AC 3, FR-10)
4. A seam contract test asserts `AnsibleExecutor` passes exactly the extra-var keys `install_dir` and `os_family` (AC 4, FR-10, hardening: seam contract lock)
5. An unknown/unexpected `os_family` value fails loudly with a clear error rather than defaulting silently — no silent fallback (AC 5, hardening)
6. All adapters are unit-tested with fakes — no real `ansible-playbook` invocation (AC 6, FR-10, NFR-5)

## Tasks / Subtasks

- [x] Add `PyYAML` to `[project].dependencies` in `pyproject.toml` (see Dev Notes — REQUIRED or the layering guard fails on `yaml` imports) (AC: 1)
- [x] Create `src/provisioning/src/provisioning/adapters/` package (AC: 1, 2, 3)
  - [x] `yaml_manifest_reader.py` — `class YamlManifestReader(IManifestReader)` parsing one manifest file → `ProvisionManifest` (AC 1)
  - [x] `ansible_fact_reader.py` — `class AnsibleFactReader(IFactReader)` parsing `ansible -m setup` output for `ansible_os_family` → group_vars basename (AC 2, 5)
  - [x] `ansible_executor.py` — `class AnsibleExecutor(IProvisionExecutor)` shelling to `ansible-playbook` (AC 3, 4)
  - [x] `__init__.py` — re-export all three adapters (mirror `ports/__init__.py` pattern)
- [x] Unit tests for each adapter with fakes (AC: 6, NFR-5)
  - [x] `tests/unit/adapters/__init__.py`
  - [x] `tests/unit/adapters/test_yaml_manifest_reader.py`
  - [x] `tests/unit/adapters/test_ansible_fact_reader.py`
  - [x] `tests/unit/adapters/test_ansible_executor.py` — including the seam contract test (AC 4)
- [x] Verify against layering guard + full suite
  - [x] `uv run pytest tests/architecture/test_layering.py` — `test_adapters_import_no_application` now RUNS (adapters/ exists; previously the last remaining skip) — 34 passed, no skips
  - [x] `uv run pytest` — full suite green, no regressions (97 passed / 0 skipped; 20 new adapter tests + previously skipped guard now live)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean

## Dev Notes

### File layout — match the plan §11 step 3 exactly

From [Source: docs/01-dotfiles-provisioning-phase1-plan.md#178-181]:
```
src/provisioning/src/provisioning/adapters/
├── __init__.py              # re-export the three adapters
├── ansible_executor.py      # shells to `ansible-playbook` (-i, --tags, --check, --extra-vars); surfaces per-task changed/ok
├── yaml_manifest_reader.py  # reads dotfiles/provisioning/*.yaml
└── ansible_fact_reader.py   # parses `ansible -m setup` for ansible_os_family
```
Re-export pattern from `ports/__init__.py`: import each adapter and list it in `__all__`.

### CRITICAL — declare `PyYAML` before importing `yaml`

The layering guard derives **allowed third-party roots from `pyproject.toml` `[project].dependencies`** (`_allowed_third_party_roots()` in `test_layering.py`). `yaml` is installed transitively (via `ansible-core`) but is **NOT declared**, so `test_only_allowed_cross_package_roots` will fail on any `import yaml` in `adapters/`.

- Add `"PyYAML>=6.0"` to `[project].dependencies` in `pyproject.toml`. The guard normalizes the dist name via `_DIST_TO_IMPORT_ROOT` (`PyYAML -> yaml`), so declaring it makes `yaml` an allowed root. `uv lock` will already have it resolved (6.0.3 present in venv).
- Do NOT touch the forbidden set or `_DOMAIN_*` lists — this is a pure dependency declaration.

### Port contracts — the adapters implement exactly these (locked in Story 1.4)

- **`IProvisionExecutor.run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult`** — `AnsibleExecutor.run` constructs the command and returns `ProvisionResult(success, tasks=tuple of (task, status))`.
  - `check=True` → add `--check` (plan mode); `check=False` → omit it (apply mode).
  - `extra_vars` is the seam: pass **exactly** the keys `install_dir` and `os_family` into `--extra-vars`. No other keys, no additions, no removal. (AC 4 seam contract test asserts this.)
- **`IManifestReader.read(manifest_path: Path) -> ProvisionManifest`** — `YamlManifestReader.read` loads ONE file. The use case (Story 1.6) globs `dotfiles/provisioning/*.yaml` itself; the adapter never globs.
- **`IFactReader.os_family() -> str`** — `AnsibleFactReader.os_family()` returns the `group_vars` basename: `"arch"` or `"debian-family"` (must match `Distro` values / group_vars filenames).

### Domain shapes the adapters produce (Story 1.2)

- `ProvisionManifest(kind: str, entries: tuple[Spec, ...])` — `Spec(name: str, version: str | None)`.
- `ProvisionResult(success: bool, tasks: tuple[tuple[str, str], ...])` — tasks are `(task_label, status)` pairs (e.g. `("packages : TASK", "ok")`).
- `Distro.ARCH = "arch"`, `Distro.DEBIAN_FAMILY = "debian-family"` — the values `AnsibleFactReader` must return.

### Design guidance per adapter

**`YamlManifestReader`** — use `yaml.safe_load` (NEVER `yaml.load`). Manifest shape maps 1:1 onto the domain model:
```yaml
kind: packages
entries:
  - name: hyprland
    version: "0.40.2"
  - name: waybar
```
Return `ProvisionManifest(kind=..., entries=tuple(Spec(...) for ...))`. Malformed YAML or a missing `kind`/`entries` key → raise a clear error (a `yaml.YAMLError`/`ValueError` subclass with the offending path) rather than producing a half-built manifest. Handle `version: null` → `None`.

**`AnsibleFactReader`** — parses the JSON output of `ansible -m setup`:
- Inject the command runner (constructor arg, default shells out) so tests never run real `ansible`. Signature example: `AnsibleFactReader(runner: Callable[..., str] | None = None)` where the default runner executes `ansible -m setup` (host from config) and returns stdout text; tests pass a fake runner returning canned JSON.
- Extract `ansible_os_family` (e.g. `Archlinux`, `Debian`, `Ubuntu`) and map it to the group_vars basename. The mapping must be **explicit and exhaustive** — Arch → `arch`; Debian-family values → `debian-family`.
- **AC 5 (fail loud):** an unrecognized `ansible_os_family` value must raise a clear, descriptive error (name the received value and the supported set). No silent default, no fallback to a distro.

**`AnsibleExecutor`** — shells to `ansible-playbook`:
- Inject the command runner (constructor arg, default `subprocess.run`) so the seam contract test and all unit tests never invoke a real playbook.
- Build the command with: `-i <inventory>`, `--tags <tags>`, `--check` (when `check=True`), `--extra-vars install_dir=... os_family=...`, then the playbook path. Inventory and tags come from constructor config (the port only passes `playbook`/`check`/`extra_vars`).
- Parse stdout to surface per-task `changed`/`ok` results into `ProvisionResult.tasks`; set `success` from the process exit code / recap.

### Runner injection — the testability pattern (NFR-5)

The three adapters are I/O adapters; Story 1.4's port tests proved fakes satisfy the interfaces. The adapter unit tests must use **fake runners**, not real subprocesses. Inject a callable that produces canned output per test; the seam contract test asserts the runner received a command whose `--extra-vars` carry exactly `install_dir` and `os_family`. Mirror the oci-runtime "transport injection" idea ([Source: src/shared/oci-runtime/tests/unit/adapters/test_cli_runtime.py]) without copying its port structure — provisioning adapters stay lean.

### Style / tooling (repo conventions, from Stories 1.1–1.4)

- `from __future__ import annotations`, `requires-python >= 3.12`, ruff `line-length = 100`, double quotes, ruff selects `E F I N W UP B`.
- `mypy src tests` runs strict (`import-untyped` disabled) — **annotate every helper, fixture param, and test method**. Fully-typed fake bodies (no `...` stubs) or `mypy --strict` fails.
- `uv run pytest` from `src/provisioning/`.
- Standalone runner parity: `python tests/architecture/test_layering.py` must still exit 0 after `adapters/` exists.

### CRITICAL — Story 1.3's layering guard activates for adapters/

Creating `adapters/` turns the **last forward-compatible skip** (`test_adapters_import_no_application`) into a live assertion:

1. **`test_adapters_import_no_application`** — `adapters/` may import only `domain`, `ports`, and `adapters` (`_ALLOWED_TARGETS["adapters"] = {"domain", "ports", "adapters"}`). No `application`/`cli` imports — those layers must not even be referenced yet.
2. **`test_no_layering_violations`** — adapters files are now scanned. `yaml` is third-party and must be declared (see CRITICAL above). Stdlib (`json`, `subprocess`, `pathlib`, `collections.abc`, `typing`) is fine in adapters.
3. **Rule 5 cross-package** — never import `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`. Only `cli_output` + declared deps allowed.
4. The ports ABC-only rule does NOT apply to adapters — adapters hold concrete classes.

### What this story is NOT (scope guard)

- No `application/` layer (Story 1.6), no `cli/` changes (Story 1.8), no manifests (`dotfiles/provisioning/*.yaml`, Story 2.1), no Ansible content (Story 2.2).
- Adapters receive their inputs via the port signatures; the use case (1.6) supplies `install_dir`/`os_family`. Do not add resolution logic here.

## Previous Story Intelligence

### Story 1.4 — Ports (learnings that apply here)

- The three port signatures above are **locked**. `IProvisionExecutor.run` carries `extra_vars` specifically so this story's seam contract test can assert the exact `install_dir` + `os_family` keys and Story 1.6 can pass them through. Do not modify the ports.
- Port tests are the contract-test shape: `issubclass(port, ABC)`, abstractness, cannot-instantiate, `NotImplementedError`, fake satisfies contract. Adapter tests are a different shape — they exercise real parsing/command-building with injected runners.
- `ProvisionResult` = `(success: bool, tasks: tuple[tuple[str, str], ...])`; `ProvisionManifest` = `(kind: str, entries: tuple[Spec, ...])` — the exact shapes this story's adapters must produce.

### Story 1.3 — Hexagonal Boundary Lock (learnings that apply here)

- The layering guard is **fail-closed**: unknown dirs are violations, imports resolve to real files, `from provisioning import <name>` expands to the layer. `adapters/` is a known layer.
- Suite was 72 passed / 1 skipped after Story 1.4; the single skip is `test_adapters_import_no_application`, gated on `adapters/` existing. Creating `adapters/` turns it live — it must pass on the first run.
- `_allowed_third_party_roots()` derives from `pyproject.toml`; this is why PyYAML must be declared (see Dev Notes).

### Story 1.2 — Domain Models and Enums (learnings that apply here)

- `ProvisionManifest`, `ProvisionResult`, `Spec` from `provisioning/domain/models.py`; `Distro` from `provisioning/domain/enums.py`.
- `Distro` values ARE the group_vars filenames: `arch`, `debian-family`. `AnsibleFactReader.os_family()` returns exactly one of these.

### Story 1.1 — Scaffold (learnings that apply here)

- Package root: `src/provisioning/src/provisioning/`; tests live in `src/provisioning/tests/` (outside the scanned `_SRC_ROOT`).
- `ansible-core` and `typer` are already declared deps; `PyYAML` is NOT (see CRITICAL). Only cross-package allowed: `cli_output` + declared deps.

## Architecture Compliance

- **In-package hexagon (plan §11 step 3):** adapters is the third ring — the concrete implementations behind the ports. `_ALLOWED_TARGETS["adapters"] = {"domain", "ports", "adapters"}`; may NOT import `application`/`cli`.
- **NFR-5 Testability:** adapters are I/O-heavy but fully unit-testable via injected fake runners — no real `ansible`/`ansible-playbook`/filesystem needed. This is the AC 6 requirement.
- **FR-10 Adapters:** the three concrete adapters per the PRD — [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#169-175].
- **Seam contract lock:** `AnsibleExecutor` must pass exactly `install_dir` + `os_family` extra-vars. This is the contract Story 1.6's `ProvisionMachineUseCase` fills in and the PRD pins by test — [Source: prd.md#174].
- **Distro isolation (NFR-3):** the Python side never branches on distro beyond reading `ansible_os_family` to select `group_vars/{arch,debian-family}.yml` — [Source: prd.md#78]. `AnsibleFactReader` IS that seam.

## Testing Requirements

- **`tests/unit/adapters/test_yaml_manifest_reader.py`** — real `tmp_path` YAML files (the adapter does read files): happy path (`kind`/`entries` parse, `version: null` → `None`), malformed YAML raises, missing `kind`/`entries` raises, empty `entries` → `()`.
- **`tests/unit/adapters/test_ansible_fact_reader.py`** — fake runner returning canned `ansible -m setup` JSON: `Archlinux` → `arch`, `Debian`/`Ubuntu` → `debian-family`, unrecognized value → raises clear error (AC 5). Assert the runner was invoked with the expected command.
- **`tests/unit/adapters/test_ansible_executor.py`** — fake runner capturing the command list: `--check` present when `check=True` and absent when `check=False`; `-i`/`--tags`/playbook path present; **seam contract test**: `--extra-vars` contains exactly `install_dir` and `os_family` and nothing else (AC 4); parsed `tasks`/`success` correct from canned stdout; non-zero exit → `success=False`.
- `uv run pytest tests/unit/adapters/` — new tests green.
- `uv run pytest tests/architecture/test_layering.py` — `test_adapters_import_no_application` runs (not skipped) and passes; no other guard regressions.
- `uv run pytest` — full suite green (was 72 passed / 1 skipped; now 0 skips + new adapter tests).
- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean.
- Standalone nicety: `python tests/architecture/test_layering.py` still exits 0.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-10 (§4.3), NFR-3/NFR-5 (§5)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — §11 boundary, "reads only `ansible_os_family` (IFactReader)"
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §6 file structure (adapters layout), §11 step 3, reconciliation shape §7
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.5 ACs, FR-10, hardening (seam contract lock)
- Ports (locked contracts): `src/provisioning/src/provisioning/ports/{provision_executor,manifest_reader,fact_reader}.py`
- Domain: `src/provisioning/src/provisioning/domain/{models,enums}.py`
- Layering guard: `src/provisioning/tests/architecture/test_layering.py`
- Port test shape (for the fake-runners contrast): `src/provisioning/tests/unit/ports/`
- Mirror for runner injection style: `src/shared/oci-runtime/tests/unit/adapters/test_cli_runtime.py`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#178-181] — adapters file structure (`ansible_executor.py`, `yaml_manifest_reader.py`, `ansible_fact_reader.py`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#279] — plan §11 step 3: adapters + unit tests with fakes
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#216-232] — Story 1.5 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#169-175] — FR-10 + seam contract pin (extra-var keys `install_dir`/`os_family`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#21] — plan reads only `ansible_os_family` to select group_vars
- [Source: src/provisioning/tests/architecture/test_layering.py] — `_ALLOWED_TARGETS["adapters"]`, `_allowed_third_party_roots`, `test_adapters_import_no_application`
- [Source: src/provisioning/src/provisioning/ports/provision_executor.py] — `run(playbook, check, extra_vars)` locked signature
- [Source: src/provisioning/src/provisioning/ports/manifest_reader.py] — `read(manifest_path)` locked signature
- [Source: src/provisioning/src/provisioning/ports/fact_reader.py] — `os_family() -> str` locked signature

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-05: RED — adapter tests written first (20 tests) failed on collection (`No module named 'provisioning.adapters'`), confirming test correctness.
- 2026-08-05: GREEN — three adapters + `__init__.py` implemented; 20 adapter tests passed.
- 2026-08-05: ruff flagged unused `Callable` import in `test_ansible_executor.py`; removed.
- 2026-08-05: ruff format rewrote 4 files; re-run clean.
- 2026-08-05: mypy strict caught `no-any-return` in `ansible_fact_reader._extract_os_family`; rewrote with `isinstance` narrowing to `str`; resolved.
- 2026-08-05: Standalone `python tests/architecture/test_layering.py` exits 0 (14 source files, 6 rules).

### Completion Notes List

- ✅ Implemented `YamlManifestReader` (AC 1): `yaml.safe_load`, missing/invalid `kind`/`entries`/entry `name` raise `ManifestReadError` (ValueError) naming the offending path; `version: null` → `None`; empty `entries` → `()`.
- ✅ Implemented `AnsibleFactReader` (AC 2, 5): injectable runner (default shells `ansible -m setup <host>`); robust JSON extraction (handles `host | SUCCESS => {...}` prefix); exhaustive explicit mapping Archlinux→arch, Debian/Ubuntu→debian-family; unknown family raises `UnknownOsFamilyError` naming the value + supported set — no silent fallback.
- ✅ Implemented `AnsibleExecutor` (AC 3, 4): command `ansible-playbook -i <inventory> --tags <tags> [--check] --extra-vars <k=v ...> <playbook>`; parses per-task changed/ok from TASK headers into `ProvisionResult.tasks`; `success` from exit code.
- ✅ Seam contract lock (AC 4): `test_extra_vars_carry_exactly_install_dir_and_os_family` asserts `--extra-vars` carries exactly `install_dir` + `os_family` and nothing else.
- ✅ AC 6 / NFR-5: all adapter tests use injected fake runners / `tmp_path` files — no real `ansible`/`ansible-playbook`/filesystem-side I/O.
- ✅ Declared `PyYAML>=6.0` in `[project].dependencies`; layering guard now treats `yaml` as an allowed third-party root (dist normalization PyYAML→yaml).
- ✅ Created `adapters/` turns `test_adapters_import_no_application` live — 34 layering tests pass, 0 skips. Full suite: 97 passed / 0 skipped. ruff check/format + mypy strict clean.

### File List

- `src/provisioning/pyproject.toml` (edit — add `PyYAML>=6.0` to `[project].dependencies`)
- `src/provisioning/src/provisioning/adapters/__init__.py` (new)
- `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py` (new)
- `src/provisioning/src/provisioning/adapters/ansible_fact_reader.py` (new)
- `src/provisioning/src/provisioning/adapters/ansible_executor.py` (new)
- `src/provisioning/tests/unit/adapters/__init__.py` (new)
- `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` (new)
- `src/provisioning/tests/unit/adapters/test_ansible_fact_reader.py` (new)
- `src/provisioning/tests/unit/adapters/test_ansible_executor.py` (new)
