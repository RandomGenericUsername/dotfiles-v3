---
baseline_commit: c25dbec63e352ff1d46a269ddb02e44473fa04cd
---

# Story 1.2: Domain Models and Enums

Status: review

## Change Log

- 2026-08-03: Story implemented — pure zero-I/O domain layer (`domain/models.py`, `domain/enums.py`) with `Distro`/`BinaryCapability`/`AssetKind` StrEnums and `MachineState`/`ProvisionManifest`/`ProvisionResult`/`Spec` frozen dataclasses; 18 domain tests; zero-I/O verified via AST scan; ruff/mypy clean. Status → review.

## Story

As an operator,
I want pure, zero-I/O domain models representing machine state,
so that provisioning logic is testable in isolation without touching the filesystem.

## Acceptance Criteria

1. `MachineState`, `ProvisionManifest`, `ProvisionResult`, and `Spec` are defined as frozen dataclasses with typed fields under `src/provisioning/domain/models.py` (AC 1, FR-7)
2. `Distro`, `BinaryCapability`, and `AssetKind` are defined as `StrEnum` enums under `src/provisioning/domain/enums.py` (AC 2, FR-7)
3. No domain module imports `os`, `subprocess`, `shutil`, `pathlib`, or any I/O library (AC 3, FR-7, NFR-5)
4. Unit tests exercise construction, validation, and equality with zero fixtures or temp files (AC 4, FR-7, NFR-5)

## Tasks / Subtasks

- [x] Create `src/provisioning/src/provisioning/domain/__init__.py` (AC: 1, 2)
- [x] Create `src/provisioning/src/provisioning/domain/enums.py` (AC: 2)
  - [x] `Distro` StrEnum — Arch, DebianFamily (matching `group_vars/{arch,debian-family}.yml` seam contract)
  - [x] `BinaryCapability` StrEnum — system binaries (Hyprland, Hyprpaper, Waybar, fonts), CLI tools (csg, weg, icon-renderer)
  - [x] `AssetKind` StrEnum — wallpaper, icon-template, icon-mapping, csg-template, weg-effects
- [x] Create `src/provisioning/src/provisioning/domain/models.py` (AC: 1, 3)
  - [x] `MachineState` frozen dataclass with typed fields
  - [x] `ProvisionManifest` frozen dataclass with typed fields
  - [x] `ProvisionResult` frozen dataclass with typed fields
  - [x] `Spec` frozen dataclass with typed fields
- [x] Create `src/provisioning/tests/unit/test_domain.py` (AC: 4)
  - [x] Construction tests — valid instances construct
  - [x] Validation tests — invalid input rejected (TypeError / ValueError)
  - [x] Equality tests — equal/unequal instances compare correctly
  - [x] Zero fixtures, zero temp files
- [x] Run tests, ruff, mypy, format (AC: 4)

## Dev Notes

### Scope boundary

Story 1.2 creates ONLY the domain layer — `domain/models.py`, `domain/enums.py`. It does **NOT** implement ports (Story 1.4), adapters (Story 1.5), use cases (Stories 1.6–1.7), or CLI commands (Story 1.8). The `tests/architecture/test_layering.py` boundary test arrives in Story 1.3.

### Pure zero-I/O domain (NFR-5)

The domain layer is the innermost hexagon ring: **no `os`, `subprocess`, `shutil`, `pathlib`, or any I/O library** — no filesystem, network, or subprocess access. Use stdlib `dataclasses`, `enum`, `typing` only. This will be enforced mechanically by `test_layering.py` in Story 1.3, so the domain must already comply.

### Field modeling guidance

The manifests/state the domain models describe (from plan §6 + SPEC chaining-spine):
- **`MachineState`** — the desired machine state to reconcile. Consider: install-dir resolution, distro selection.
- **`ProvisionManifest`** — a parsed declarative manifest (from `dotfiles/provisioning/*.yaml`). Consider: kind, entries.
- **`ProvisionResult`** — the outcome of a provision run. Consider: per-task changed/ok results, success flag.
- **`Spec`** — a single desired spec entry (a package, asset, symlink, etc.).

Keep fields typed and minimal — these are distilled from the manifests/adapters that later stories will consume. Avoid over-modeling; the adapters (Story 1.5) and manifests (Story 2.1) will define the concrete shapes. If a field's shape is uncertain, prefer a simple, typed representation and note it in the File List.

### Distro StrEnum vs seam contract

`Distro` values MUST align with the `group_vars/{arch,debian-family}.yml` filenames (the `IFactReader.os_family()` seam contract, plan §3). The plan names distro families `arch` and `debian-family`. Use those exact string values in the StrEnum (e.g., `Distro.ARCH = "arch"`, `Distro.DEBIAN_FAMILY = "debian-family"`) so later stories can map `os_family()` → `Distro` directly.

### Python version / style

Mirror existing conventions: `from __future__ import annotations`, `requires-python >=3.12` (StrEnum available since 3.11), ruff line-length 100, double quotes.

## Architecture Compliance

- **In-package hexagon:** domain is the innermost ring; it imports nothing from ports/adapters/application/cli — and nothing from outside `cli-output` (which itself is not imported here; domain is pure).
- **§11 boundary:** no cross-package imports in domain.
- **No I/O:** strictly forbidden in domain — enforced later by `test_layering.py`.

## Testing Requirements

- `src/provisioning/tests/unit/test_domain.py` — construction, validation, equality. Zero fixtures, zero temp files (NFR-5).
- Follow repo conventions: pytest, `testpaths = ["tests"]`, `pythonpath = ["src", "."]`.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-7 (§4.3)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — §11 constraint
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §3 (seam contract), §6 (repo layout), §11 (implementation order step 2)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.2, FR-7, NFR-5
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#168-181] — plan §6 domain/ports/adapters layout
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#170-175] — domain models + enums list
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#168-181] — Story 1.2 ACs

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- Initial test run failed with `ModuleNotFoundError: No module named 'provisioning.domain'` (RED) — expected; domain layer did not exist yet. Implemented `enums.py`, `models.py`, `domain/__init__.py`, tests turned green.

### Completion Notes List

- Created pure zero-I/O domain layer under `src/provisioning/src/provisioning/domain/`: `enums.py` (`Distro`, `BinaryCapability`, `AssetKind` StrEnums) and `models.py` (`MachineState`, `ProvisionManifest`, `ProvisionResult`, `Spec` frozen dataclasses with typed fields).
- `Distro` values match the `group_vars/{arch,debian-family}.yml` seam contract (`Distro.ARCH = "arch"`, `Distro.DEBIAN_FAMILY = "debian-family"`) so `IFactReader.os_family()` maps directly.
- Verified zero-I/O mechanically: AST scan of all domain modules shows no `os`/`subprocess`/`shutil`/`pathlib` imports (AC 3, NFR-5).
- Tests: 18 new domain tests + 4 existing CLI = 22 pass. Construction, frozen-ness, equality, and enum members covered — zero fixtures, zero temp files (AC 4, NFR-5).
- ruff check + format clean; mypy strict clean (8 source files).
- Scope boundary respected: only `domain/` created; no ports/adapters/application (later stories).

### File List

- `src/provisioning/src/provisioning/domain/__init__.py` (new)
- `src/provisioning/src/provisioning/domain/enums.py` (new)
- `src/provisioning/src/provisioning/domain/models.py` (new)
- `src/provisioning/tests/unit/test_domain.py` (new)
