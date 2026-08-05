---
baseline_commit: f104f0aa4be0a58c193e67234d9a1e6677d400ae
---

# Story 1.3: Hexagonal Boundary Lock

Status: review

## Change Log

- 2026-08-04: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-04: Story implemented — `tests/architecture/test_layering.py` created (mirrors the oci-runtime hexagon guard): in-package layering (domain ← ports ← adapters ← application ← cli), domain stdlib allowlist + banned-stdlib, ports-ABC rule, Path-FS-method ban, and Rule 5 cross-package §11 boundary with pyproject-derived allowed roots; 19 tests green (3 forward-compatible skips), full suite 47 passed, ruff + mypy clean. Status → review.

## Story

As an architect,
I want a mechanical test enforcing the provisioning package boundary,
so that `src/provisioning` can never silently import forbidden packages.

## Acceptance Criteria

1. `tests/architecture/test_layering.py` exists at `src/provisioning/tests/architecture/test_layering.py` and asserts the in-package dependency order domain ← ports ← adapters ← application ← cli (AC 1, FR-24)
2. The test asserts the domain stdlib allowlist and bans `subprocess`, `os`, `shutil`, and Path FS calls in domain (AC 2, FR-24, NFR-5)
3. The test asserts ports are ABCs (AC 3, FR-24, NFR-5)
4. The test asserts the Rule 5 cross-package forbidden set (`core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`) is never imported (AC 4, FR-24, NFR-4)
5. Only `provisioning` and `cli_output` are allowed cross-package (AC 5, FR-24, NFR-4)
6. A deliberately-violating import fails the test (AC 6, FR-24, SM-5)

## Tasks / Subtasks

- [x] Create `src/provisioning/tests/architecture/test_layering.py` (AC: 1)
  - [x] `_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "provisioning"` (package root)
  - [x] `_LAYERS = ("domain", "ports", "adapters", "application", "cli")`
  - [x] `_ALLOWED_TARGETS` mapping — each layer may import itself + all inner layers; `cli` is the composition root and may import everything; root `__init__.py` may import everything
  - [x] `_classify_layer()`, `_layer_of_imported_module()`, `_extract_import_modules()` helpers (AST-based)
  - [x] `test_no_layering_violations` — parametrized over every `*.py` under `_SRC_ROOT`
  - [x] Layer-specific guards: `test_domain_imports_only_domain`, `test_ports_import_no_adapters`, `test_adapters_import_no_application` (and mirror the oci-runtime per-layer assertions)
- [x] Domain stdlib rules (AC: 2)
  - [x] `_DOMAIN_ALLOWED_STDLIB` — the pure, zero-I/O set (see Dev Notes — differs from oci-runtime mirror)
  - [x] `_DOMAIN_BANNED_STDLIB` — `subprocess`, `os`, `shutil` (+ oci-runtime extras `select`, `selectors`, `socket`)
  - [x] `test_domain_stdlib_imports_are_allowlisted`
  - [x] `test_domain_imports_no_banned_stdlib`
  - [x] `_BANNED_PATH_FS_METHODS` scan + `test_domain_no_path_fs_method_calls` (mirror oci-runtime's method list)
  - [x] Self-tests for each rule using `ast.parse("import os")` etc. (AC: 6)
- [x] Ports ABC rule (AC: 3)
  - [x] `_classify_ports_class()` — abc / dataclass-aggregate / concrete (mirror oci-runtime)
  - [x] `test_ports_files_are_abstract_only`
  - [x] Self-test for classification (AC: 6)
- [x] Rule 5 cross-package check (AC: 4, 5)
  - [x] `_FORBIDDEN_CROSS_PACKAGE = {"core", "infrastructure", "color_scheme_generator", "wallpaper_effects_generator", "icon_templates_renderer", "config_assembler_engine", "oci_runtime"}`
  - [x] `test_no_forbidden_cross_package_imports` — scan all source files, flag any import whose top-level root is in the set
  - [x] `test_only_allowed_cross_package_roots` — non-stdlib, non-`provisioning` roots must be `cli_output` or a dependency declared in `pyproject.toml` (see Dev Notes for the robust derivation)
  - [x] Self-tests: `import core` flagged; `import cli_output` allowed; `import provisioning.domain.models` allowed (AC: 6)
- [x] Verify against current tree (domain + cli exist; ports/adapters/application do NOT yet)
  - [x] Run `uv run pytest tests/architecture/test_layering.py` — must pass on the current tree (AC: 1-6)
  - [x] Run full suite `uv run pytest` — no regressions (28 tests exist today)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] Optional mirror nicety: standalone `python tests/architecture/test_layering.py` exits 0

## Dev Notes

### Scope boundary — this story creates ONLY the architecture test

Story 1.3 creates ONLY `tests/architecture/test_layering.py`. It does **NOT** implement:
- Ports (Story 1.4), adapters (Story 1.5), use cases (Stories 1.6–1.7), CLI commands (Story 1.8)
- Ansible content, manifests, roles (Epic 2)

The ports/adapters/application layers do not exist yet. The test MUST be forward-compatible:
it enforces rules for all five layers now so those later stories cannot silently violate them.
Empty layers (ports/adapters/application today) make their checks pass vacuously.

### Mirror reference: `src/shared/oci-runtime/tests/architecture/test_layering.py` — READ IT FIRST

[Source: src/shared/oci-runtime/tests/architecture/test_layering.py] is the exact pattern to
mirror (504 lines, all stdlib `ast` + `pathlib`, zero third-party deps). Reuse its structure
verbatim for: helper functions (`_classify_layer`, `_layer_of_imported_module`,
`_extract_stdlib_imports`, `_scan_for_banned_method_calls`, `_classify_ports_class`),
the parametrized scan, the self-tests, the standalone `__main__` runner, and the module docstring
documenting the layering contract.

### CRITICAL — do NOT copy the oci-runtime stdlib allowlist wholesale

The oci-runtime domain does I/O (tarfile, pathlib, json, io, posixpath) so its
`_DOMAIN_ALLOWED_STDLIB` is broad. The provisioning domain is **pure data** (Story 1.2 AC 3:
no `os`, `subprocess`, `shutil`, `pathlib`, or any I/O library). The provisioning
`_DOMAIN_ALLOWED_STDLIB` MUST be the minimal pure set:

```python
_DOMAIN_ALLOWED_STDLIB = frozenset({
    "dataclasses", "enum", "typing", "collections", "collections.abc", "functools", "re",
})
```

Do **NOT** include `pathlib`, `os`, `io`, `posixpath`, `tarfile`, `json`, `types`, or `sys` —
the domain must stay zero-I/O. (Today `domain/enums.py` imports only `enum`; `domain/models.py`
only `dataclasses` — both inside the set.) If a later domain feature needs a stdlib module,
it must be justified and added to the allowlist explicitly.

`_DOMAIN_BANNED_STDLIB` mirrors oci-runtime: `subprocess`, `os`, `shutil`, `select`,
`selectors`, `socket`. `pathlib` is excluded by the allowlist already; the Path-FS-method
scan (`.exists()`, `.read_text()`, `.glob()`, `.resolve()`, …) covers direct calls.

### Layer set and allowed targets — provisioning differs from oci-runtime

The provisioning hexagon is `domain ← ports ← adapters ← application ← cli`
(plan §11 step 2, epics Story 1.3). There is **no** `factory` layer; `cli` is the outer shell /
composition root. `_ALLOWED_TARGETS`:

```python
_ALLOWED_TARGETS = {
    "domain":      {"domain"},
    "ports":       {"domain", "ports"},
    "adapters":    {"domain", "ports", "adapters"},
    "application": {"domain", "ports", "adapters", "application"},
    "cli":         {"domain", "ports", "adapters", "application", "cli"},
    "root":        {"domain", "ports", "adapters", "application", "cli"},
}
```

`_classify_layer` maps a file to its layer by its first path segment under the package root:
`__init__.py` at the root → `root`; `domain/…` → `domain`; any other top-level segment →
`root` (same shape as oci-runtime's helper). The root `__init__.py` may re-export anything
(public API), like `provisioning/domain/__init__.py` already does.

### Rule 5 — cross-package boundary (the §11 mechanical lock)

[Source: docs/01-dotfiles-provisioning-phase1-plan.md#278 — plan §11 step 2] and
[Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#50 — "§11 enforced mechanically"].

Two checks, applied to every `*.py` under `_SRC_ROOT`:

1. **Forbidden set (AC 4):** any import whose top-level root is in
   `{"core", "infrastructure", "color_scheme_generator", "wallpaper_effects_generator",
   "icon_templates_renderer", "config_assembler_engine", "oci_runtime"}` is a violation.
2. **Allowed roots (AC 5):** any non-stdlib import whose top-level root is not `provisioning`
   must be either `cli_output` (the one allowed dotfiles-sibling) or a dependency declared in
   `pyproject.toml`. Do NOT blanket-allow all third-party — `core`, `infrastructure`, and the
   CLI-tool packages are repo siblings that must be caught. `typer` and `pydantic` ARE declared
   runtime deps (Story 1.1) and `cli/main.py` already imports `typer`/`cli_output` — the test
   must not fail on them.

Robust way to keep (2) in sync with declared deps: parse `src/provisioning/pyproject.toml`
`[project].dependencies` + `[tool.uv.sources]` keys and normalize each to an import root
(`cli-output` → `cli_output`, dash → underscore). Note `ansible-core` normalizes to
`ansible_core` but its real import root is `ansible` — provisioning shells to the
`ansible-playbook` binary rather than importing `ansible`, so this is only relevant if a later
story actually imports it. If you prefer a simpler hard-coded set, keep it
`{"cli_output", "typer", "pydantic"}` and document the assumption; the pyproject-derived
approach is preferred to avoid false failures when later stories add imports.

### Scan only the package, never `tests/`

`_all_source_files()` = `sorted(_SRC_ROOT.rglob("*.py"))` — mirrors oci-runtime. The
`tests/` tree is deliberately NOT scanned (tests may import anything). The test file itself
lives at `tests/architecture/test_layering.py`, outside `_SRC_ROOT`, so it is not self-checked.

### Existing tree today (what the test must accept)

- `src/provisioning/src/provisioning/__init__.py` — root layer, imports nothing
- `src/provisioning/src/provisioning/cli/main.py` — `cli` layer; imports `typer`,
  `cli_output.*` (allowed) and stdlib `importlib.metadata`; no in-package imports
- `src/provisioning/src/provisioning/domain/{__init__.py,enums.py,models.py}` — domain layer;
  `__init__.py` imports `provisioning.domain.*` (in-package, allowed); `enums.py` imports `enum`;
  `models.py` imports `dataclasses` + `provisioning.domain.enums`
- No `ports/`, `adapters/`, `application/` yet — their tests pass vacuously

### Zero third-party deps in the test itself

The test must use only stdlib `ast`, `sys`, `pathlib` (+ `pytest` for the runner), exactly like
the oci-runtime mirror. This is what makes the boundary a hard mechanical gate — it runs in CI
without a dependency install.

### Python version / style

Mirror existing conventions: `from __future__ import annotations`, `requires-python >=3.12`,
ruff line-length 100, double quotes. `mypy src tests` runs strict (`import-untyped` disabled),
so type-annotate the helper functions and test methods (see Story 1.1 review finding on
untyped test params).

## Previous Story Intelligence

### Story 1.1 — Scaffold (learnings that apply here)

- `uv.sources` relative path from `src/provisioning/` is `../shared/cli-output` (not
  `../../shared/cli-output`) — already correct in pyproject; don't touch it.
- `mypy` strict requires annotated test params — annotate `monkeypatch`, fixtures, and helpers
  in the new test or `mypy src tests` fails.
- §11 already holds today: only cross-package dep is `cli-output`; the test formalizes it.

### Story 1.2 — Domain Models and Enums (learnings that apply here)

- Domain files are already zero-I/O and clean; the allowlist/banned-scan must pass on them as-is.
- `Distro` values are the group_vars filenames (`arch`, `debian-family`); `Capability` values are
  real on-PATH names; `Capability.kind()` maps to `CapabilityKind`. Domain uses only
  `dataclasses` + `enum` today.
- `ProvisionManifest.entries`/`ProvisionResult.tasks` are `tuple`-typed (hashable frozen
  dataclasses) — an AST-level layering test is unaffected, but don't let the test's own AST scan
  false-positive on these modules.

## Architecture Compliance

- **§11 boundary / NFR-4:** `src/provisioning` imports `cli-output` only among dotfiles-sibling
  packages; the forbidden set is enforced mechanically. This story delivers that enforcement.
- **NFR-5 Testability:** the domain stays pure zero-I/O (allowlist + banned-scan + Path-FS-call
  scan); ports stay ABCs (ports rule).
- **In-package hexagon (plan §11 step 2 / epics Story 1.3):** domain ← ports ← adapters ←
  application ← cli, mechanically locked from day one.
- [Source: docs/99-dotfiles-hexagonal-architecture.md#279-299] — dependencies point inward.
- [Source: docs/99-dotfiles-hexagonal-architecture.md#399-445] — bounded contexts: provisioning
  must never know runtime concerns; mirrored by the cross-package ban on `core`/`infrastructure`.

## Testing Requirements

- The test IS the deliverable. It must pass on the current tree (domain + cli) and be
  forward-compatible with ports/adapters/application.
- Include self-tests for EVERY rule using synthetic `ast.parse(...)` snippets (deliberately
  violating imports) so AC 6 is continuously proven — mirror oci-runtime's `test_*_self_test`
  methods.
- Run from `src/provisioning/`:
  - `uv run pytest tests/architecture/test_layering.py` — new test green
  - `uv run pytest` — full suite green (28 tests before this story; expect 40+ after)
  - `uv run ruff check . && uv run ruff format --check .` — clean
  - `uv run mypy src tests` — clean
- Optional: `python tests/architecture/test_layering.py` runs standalone (oci-runtime parity).

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-24 (§4.2), NFR-4 (§5), SM-5 (§8)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — §11 constraint, "§11 enforced mechanically" line
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §3 (locked decision §11), §6 (tests/architecture layout), §11 step 2 (exact enforcement list)
- Architecture: `docs/99-dotfiles-hexagonal-architecture.md` — §8 (hexagonal style), §11 (bounded contexts)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.3, FR-24, NFR-4
- Mirror: `src/shared/oci-runtime/tests/architecture/test_layering.py`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#278] — plan §11 step 2: "in-package hexagon (domain ← ports ← adapters ← application ← cli; domain stdlib allowlist; banned subprocess/os/shutil in domain; ports must be ABCs; no Path FS calls in domain) plus Rule 5: cross-package forbidden set …; only provisioning + cli_output allowed"
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#187] — `tests/architecture/test_layering.py` location
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#183-198] — Story 1.3 ACs
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#50] — "§11 enforced mechanically"
- [Source: src/shared/oci-runtime/tests/architecture/test_layering.py] — mirror reference (read fully before implementing)
- [Source: src/provisioning/src/provisioning/domain/enums.py] — current domain imports (only `enum`)
- [Source: src/provisioning/src/provisioning/domain/models.py] — current domain imports (`dataclasses`, `provisioning.domain.enums`)
- [Source: src/provisioning/src/provisioning/cli/main.py] — current cli imports (`typer`, `cli_output.*`, `importlib.metadata`)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- First run failed 5 tests (RED): (1) `_DOMAIN_ALLOWED_STDLIB` missing `__future__` (every domain file uses `from __future__ import annotations`, which is in `sys.stdlib_module_names`); (2) per-layer tests (`test_domain_imports_only_domain` etc.) flagged `__future__` because `_extract_import_modules` returns all imports — fixed by skipping `None`-layer (non-in-package) targets; (3) `_layer_of_imported_module("provisioning")` returned `None` — added explicit bare-package → `root` handling; (4) `_import_root` didn't strip version specifiers (`typer>=0.12` stayed whole) — added `re.split(r"[\s<>=!~]+", ...)[0]`.
- `ruff format` reformatted 1 file (line-wrapping) — re-ran; still green.

### Completion Notes List

- Created `src/provisioning/tests/architecture/test_layering.py` (mirrors `src/shared/oci-runtime/tests/architecture/test_layering.py`), a pure-stdlib AST guard with zero third-party deps (`ast`, `sys`, `pathlib`, `tomllib`, `re`).
- In-package hexagon locked: `_ALLOWED_TARGETS` encodes domain ← ports ← adapters ← application ← cli (cli = composition root); parametrized `test_no_layering_violations` over every `*.py` under `_SRC_ROOT`, plus per-layer guards (domain/ports/adapters).
- Domain purity (AC 2): minimal allowlist `{__future__, dataclasses, enum, typing, collections, collections.abc, functools, re}` — deliberately EXCLUDES pathlib/io/posixpath/tarfile/json (differs from oci-runtime mirror because the provisioning domain is zero-I/O); banned set `{subprocess, os, shutil, select, selectors, socket}`; Path-FS-method-call ban (17 methods).
- Ports ABC rule (AC 3): `_classify_ports_class` (abc / dataclass-aggregate / concrete); `test_ports_files_are_abstract_only` is forward-compatible (skips while ports/ is empty).
- Rule 5 cross-package (AC 4, 5): `_FORBIDDEN_CROSS_PACKAGE` = the 7 dotfiles siblings; `test_only_allowed_cross_package_roots` derives the allowed set from `pyproject.toml` deps (`_import_root` normalizes `cli-output`→`cli_output`, `ansible-core`→`ansible`, strips versions) so typer/pydantic pass and the test stays in sync with declared deps.
- AC 6 proven by self-tests for every rule: `ast.parse("import os")`, `import core`, `import provisioning.adapters...`, `p.exists()`, ports classification, and pyproject-derivation assertions.
- Tests: 19 new pass (3 skips = forward-compatible ports/adapters checks); full suite 47 passed (28 pre-existing + 19 new); `ruff check` + `ruff format --check` clean; `mypy src tests` clean (strict); standalone `python tests/architecture/test_layering.py` exits 0 ("OK: 6 source files checked").
- Scope respected: only the architecture test added; no production code, no ports/adapters/application (later stories).

### File List

- `src/provisioning/tests/architecture/test_layering.py` (new)
