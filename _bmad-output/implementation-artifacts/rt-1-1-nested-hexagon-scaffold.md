# Story 1.1: Nested-Hexagon Scaffold with Layering Test

Status: ready-for-dev

## Story

As a developer,
I want the `dotfiles-runtime` package scaffolded as a nested hexagon,
so that Phase 2 code lands in the right layers from day one and the §11 boundary is enforced mechanically.

## Acceptance Criteria

1. `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` exist with `__init__.py` files (AC 1, AD-13)
2. `tests/architecture/test_layering.py` mirrors provisioning's layering test (domain stdlib allowlist, banned stdlib, no Path FS calls, ports-as-ABCs, cross-package forbidden set) (AC 2, AD-1, AD-14, AD-15)
3. A deliberately-violating import fails the layering test (AC 3)
4. `uv run --directory src/runtime pytest` passes on the scaffold (AC 4)
5. `uv lock` resolves without errors (AC 5)

## Tasks / Subtasks

- [ ] Create `src/runtime/pyproject.toml` (AC: 1, 5)
  - [ ] `[project]` name = `dotfiles-runtime`, version, description, `requires-python = ">=3.14"`
  - [ ] Runtime deps: `typer`, `cli-output` (via `uv.sources`)
  - [ ] `[project.scripts]` → `dotfiles-runtime = "runtime.cli.main:app"`
  - [ ] Dev deps (`[dependency-groups]`): `pytest`, `ruff`, `mypy`
  - [ ] `[tool.hatch.build.targets.wheel] packages = ["src/runtime"]`
  - [ ] `[tool.uv.sources]` → `cli-output = { path = "../shared/cli-output", editable = true }`
  - [ ] `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["src", "."]`
  - [ ] `[tool.ruff]` matching repo convention (`target-version`, `line-length = 100`, `select`, `quote-style = "double"`)
- [ ] Create package skeleton `src/runtime/src/runtime/` (AC: 1)
  - [ ] `__init__.py` with `__version__`
  - [ ] `domain/__init__.py` (empty — domain models arrive in Story 1.2)
  - [ ] `ports/__init__.py` (empty — ports arrive in Story 1.3)
  - [ ] `adapters/__init__.py` (empty — adapters arrive later)
  - [ ] `application/__init__.py` (empty — use cases arrive later)
  - [ ] `cli/__init__.py` (empty)
  - [ ] `cli/main.py` — stub Typer app with a `version` command rendering via `cli-output`
- [ ] Create `src/runtime/tests/` (AC: 2, 3, 4)
  - [ ] `tests/architecture/test_layering.py` — mechanical layering enforcement mirroring `src/provisioning/tests/architecture/test_layering.py`
  - [ ] `tests/test_cli.py` — stub CLI test exercising version command via Typer `CliRunner`
- [ ] Run `uv lock` in `src/runtime/` and confirm it resolves (AC: 5)
- [ ] Run `uv run --directory src/runtime pytest` and confirm all tests pass (AC: 4)
- [ ] Verify layering test catches a deliberately-violating import (AC: 3)

## Dev Notes

### Scope boundary — this story is the SCAFFOLD ONLY

Story 1.1 creates the empty uv package that every later story fills. It does **NOT** implement:
- Domain models/enums (Story 1.2)
- Ports (Story 1.3)
- Adapters, use cases, CLI commands (later stories)

Resist the urge to scaffold more than this story needs — domain/ports/adapters/application/cli folders contain only `__init__.py` until their respective stories land.

### Package layout (locked in Architecture Spine AD-13)

```
src/runtime/                          ← new uv package (Phase 2)
├── pyproject.toml
├── uv.lock
├── src/runtime/                      ← import package (underscored dir)
│   ├── __init__.py                   ← __version__
│   ├── domain/
│   │   └── __init__.py
│   ├── ports/
│   │   └── __init__.py
│   ├── adapters/
│   │   └── __init__.py
│   ├── application/
│   │   └── __init__.py
│   └── cli/
│       ├── __init__.py
│       └── main.py                   ← stub Typer app (this story)
├── tests/
│   ├── architecture/
│   │   └── test_layering.py          ← mechanical enforcement
│   └── test_cli.py
```

### Mirror reference: `src/provisioning/` scaffold (Story 1.1)

[Source: _bmad-output/implementation-artifacts/1-1-scaffold-the-provisioning-package.md]

Follow the same conventions established by provisioning's scaffold:

- `[build-system]` = `hatchling` / `hatchling.build`
- `[tool.hatch.build.targets.wheel] packages = ["src/runtime"]`
- `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["src", "."]`
- `[tool.ruff] target-version` + `line-length = 100`, `[tool.ruff.lint] select`, `[tool.ruff.format] quote-style = "double"`
- `[dependency-groups] dev = [...]`

### `uv.sources` pattern

```toml
[tool.uv.sources]
cli-output = { path = "../shared/cli-output", editable = true }
```

Relative path from `src/runtime/` → `../shared/cli-output`. `cli-output` is the ONLY cross-package dependency permitted (§11 boundary, AD-15). Do NOT add `provisioning`, `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, or `oci_runtime`.

### Python version

Architecture spine AD-13 and repo convention: `requires-python = ">=3.14"` (matches CSG, not the older `>=3.12` in cli-output/provisioning). Confirm before locking.

### Stub CLI via `cli-output`

The stub must render a version string through `cli-output` (not print to stdout directly). Inspect `src/shared/cli-output/src/cli_output/` — it exposes an output factory with json/plain/rich renderers. For a scaffold, render a simple version object. The `dotfiles-runtime` Typer app only needs the version surface; `wallpaper`, `status`, `history`, `cache` commands arrive in later stories.

### Layering test — mirror provisioning's exactly

[Source: src/provisioning/tests/architecture/test_layering.py]

The runtime layering test must enforce the same rules as provisioning, adapted for the `runtime` package name:

**Layer ordering:** `domain → ports → adapters → application → cli`

**Allowed import directions:**
- `domain` → `runtime.domain.*` + stdlib allowlist only
- `ports` → `runtime.domain.*` + `runtime.ports.*`
- `adapters` → `runtime.domain/ports/adapters.*`
- `application` → `runtime.domain/ports/adapters/application.*`
- `cli` → everything (outer shell / composition root)

**Domain stdlib allowlist (AD-14):**
```python
_DOMAIN_ALLOWED_STDLIB = frozenset({
    "__future__",
    "dataclasses",
    "enum",
    "typing",
    "collections",
    "collections.abc",
    "functools",
    "re",
})
```

**Domain banned stdlib:**
```python
_DOMAIN_BANNED_STDLIB = frozenset({
    "subprocess",
    "os",
    "shutil",
    "select",
    "selectors",
    "socket",
})
```

**Banned Path FS methods in domain:**
```python
_BANNED_PATH_FS_METHODS = frozenset({
    "exists", "read_text", "read_bytes", "write_text", "write_bytes",
    "glob", "rglob", "iterdir", "mkdir", "rmdir", "unlink",
    "chmod", "chown", "stat", "lstat", "touch", "resolve",
})
```

**Rule 5 cross-package forbidden set (AD-15):**
```python
_FORBIDDEN_CROSS_PACKAGE = frozenset({
    "provisioning",    # NEW: runtime must never import provisioning
    "core",
    "infrastructure",
    "color_scheme_generator",
    "wallpaper_effects_generator",
    "icon_templates_renderer",
    "config_assembler_engine",
    "oci_runtime",
})
```

**Key difference from provisioning:** the forbidden set adds `"provisioning"` — runtime reads provisioning OUTPUT (files/settings), never provisioning code (AD-15).

### Architecture compliance checklist

- [ ] **AD-1 (hexagonal):** layer order domain ← ports ← adapters ← application ← cli, enforced by test
- [ ] **AD-13 (nested hexagon):** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}`
- [ ] **AD-14 (domain purity):** domain imports only stdlib allowlist; no `os`/`subprocess`/`shutil`/`pathlib`; no Path FS calls
- [ ] **AD-15 (cross-package boundary):** runtime imports only `cli_output` (and declared deps); forbidden set includes `provisioning`

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1, AD-13, AD-14, AD-15
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 1.1 ACs
- Provisioning scaffold (mirror): `_bmad-output/implementation-artifacts/1-1-scaffold-the-provisioning-package.md`
- Provisioning layering test (mirror): `src/provisioning/tests/architecture/test_layering.py`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
