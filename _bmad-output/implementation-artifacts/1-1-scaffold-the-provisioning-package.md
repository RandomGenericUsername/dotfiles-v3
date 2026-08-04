# Story 1.1: Scaffold the Provisioning Package

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want a `src/provisioning` uv package with a `dotfiles-provision` entry point,
so that the provisioning tool can be built, installed, and extended incrementally.

## Acceptance Criteria

1. `pyproject.toml` exists at `src/provisioning/pyproject.toml` with package name `dotfiles-provision`, entry point `dotfiles-provision`, and runtime dependencies `typer`, `pydantic`, `cli-output` (via `uv.sources`), `ansible-core` (AC 1, FR-6)
2. Dev dependencies include `pytest`, `ruff`, `mypy` (AC 2, FR-6)
3. A stub CLI invoking `cli-output` renders a version string and exits 0 (AC 3, FR-6)
4. Package layout mirrors `src/shared/cli-output/` structure with `src/provisioning/src/`, `src/provisioning/tests/`, and `pyproject.toml` (AC 4, FR-6)
5. `uv lock` resolves without errors (AC 5, FR-6)

## Tasks / Subtasks

- [ ] Create `src/provisioning/pyproject.toml` (AC: 1, 2)
  - [ ] `[project]` name = `dotfiles-provision`, version, description, `requires-python`
  - [ ] Runtime deps: `typer`, `pydantic`, `cli-output`, `ansible-core`
  - [ ] `[project.scripts]` → `dotfiles-provision = "provisioning.cli.main:app"`
  - [ ] Dev deps (`[dependency-groups]`): `pytest`, `ruff`, `mypy`
  - [ ] `[tool.hatch.build.targets.wheel]` packages = `["src/provisioning"]`
  - [ ] `[tool.uv.sources]` → `cli-output = { path = "../../shared/cli-output", editable = true }`
  - [ ] `[tool.pytest.ini_options]`, `[tool.ruff]` matching repo convention
- [ ] Create package skeleton `src/provisioning/src/provisioning/` (AC: 4)
  - [ ] `__init__.py` with `__version__`
  - [ ] `cli/main.py` — stub Typer app with a `version` command rendering via `cli-output`
- [ ] Create `src/provisioning/tests/` with a stub CLI test (AC: 4)
- [ ] Run `uv lock` in `src/provisioning/` and confirm it resolves (AC: 5)
- [ ] Run the stub CLI and confirm exit 0 (AC: 3)

## Dev Notes

### Scope boundary — this story is the SCAFFOLD ONLY

Story 1.1 creates the empty uv package that every later story fills. It does **NOT** implement:
- Domain models/enums (Story 1.2)
- Ports (Story 1.4), adapters (Story 1.5), use cases (Stories 1.6–1.7), CLI commands (Story 1.8)
- `tests/architecture/test_layering.py` (Story 1.3)
- Ansible content, manifests, roles (Epic 2)

Resist the urge to scaffold more than this story needs — domain/ports/adapters/application/cli folders are created as their stories land, keeping each story independently completable.

### Package layout (locked in plan §6)

```
src/provisioning/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/provisioning/          ← import package (underscored dir)
│   ├── __init__.py            ← __version__
│   └── cli/
│       ├── __init__.py
│       └── main.py            ← stub Typer app (this story)
├── tests/
```

Note: the `ansible/` tree shown in plan §6 lives at `src/provisioning/ansible/` (sibling of `src/provisioning/src/`), NOT inside the import package. It is **NOT** created in this story — it arrives in Story 2.2.

### Mirror reference: `src/shared/cli-output/pyproject.toml`

[Source: docs/01-dotfiles-provisioning-phase1-plan.md#277 — "Mirror `src/shared/cli-output/pyproject.toml`"]. Follow its conventions:

- `[build-system]` = `hatchling` / `hatchling.build`
- `[tool.hatch.build.targets.wheel] packages = ["src/provisioning"]`
- `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["src", "."]`
- `[tool.ruff] target-version` + `line-length = 100`, `[tool.ruff.lint] select`, `[tool.ruff.format] quote-style = "double"`
- `[dependency-groups] dev = [...]`

### `uv.sources` pattern (from `src/cli-tools/color-scheme-generator/pyproject.toml`)

```toml
[tool.uv.sources]
cli-output = { path = "../../shared/cli-output", editable = true }
```

Relative path is from `src/provisioning/` → `../../shared/cli-output`. `cli-output` is the ONLY cross-package dependency permitted (§11 boundary). Do NOT add `config-assembler-engine`, `oci-runtime`, or any CLI-tool package here.

### Python version

Repo convention varies: `cli-output` uses `requires-python = ">=3.12"`, CSG uses `">=3.14"`. Default to `>=3.12` (matches the shared packages and the oci-runtime hexagon) unless a root convention dictates otherwise. Confirm before locking.

### Stub CLI via `cli-output`

The stub must render a version string through `cli-output` (not print to stdout directly). Inspect `src/shared/cli-output/src/cli_output/` — it exposes an output factory with json/plain/rich renderers. For a scaffold, render a simple version object. The `dotfiles-provision` Typer app in this story only needs the version surface; `plan`/`apply`/`verify`/`bootstrap` commands arrive in Story 1.8.

### ansible-core as a runtime dependency

`ansible-core` is a runtime dep (not dev) per plan §3 locked decision — resolved by `uv` from the lockfile, no system-wide install. It is declared in `pyproject.toml` here even though no Ansible code exists yet; later stories shell to `ansible-playbook` via the adapters.

## Architecture Compliance

- **§11 boundary (plan §3 / architecture §11):** `src/provisioning` imports `cli-output` only — never `core`, `infrastructure`, or the CLI-tool packages (`color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`). The mechanical enforcement test arrives in Story 1.3; the scaffold must not pre-violate it.
- **In-package hexagon ordering** (domain ← ports ← adapters ← application ← cli) is established as folders are created by later stories; only `cli/` exists in this story.
- **Package name vs import name:** `[project] name = "dotfiles-provision"` (the CLI product), import package `provisioning`. Do not name the import package `dotfiles_provision`.

## Testing Requirements

- Create at least one stub test (`tests/test_cli.py` or similar) exercising the Typer app via `Typer CliRunner` — assert the version command exits 0. This validates the scaffold end-to-end before later stories build on it.
- `uv lock` must resolve without errors.
- Follow repo test conventions: `testpaths = ["tests"]`, `pythonpath = ["src", "."]`.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-6 (§4.2)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — CAP-4, §11 constraint
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §3 locked decisions (Ansible backend, §11 boundary, install dir), §6 repo layout, §11 implementation order step 1
- Architecture: `docs/99-dotfiles-hexagonal-architecture.md` — §9 repo tree, §11 bounded context
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.1, FR-6
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#277] — "Scaffold `src/provisioning/pyproject.toml` ... Mirror `src/shared/cli-output/pyproject.toml`"
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#137-188] — repo layout
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#56] — ansible-core as runtime dep
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#61] — §11 boundary
- [Source: src/shared/cli-output/pyproject.toml] — mirror reference
- [Source: src/cli-tools/color-scheme-generator/pyproject.toml] — `uv.sources` + scripts pattern
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#152-166] — Story 1.1 ACs

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created

### File List
