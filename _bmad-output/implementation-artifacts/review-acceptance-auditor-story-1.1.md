# Acceptance Audit — Story 1.1: Scaffold the Provisioning Package

Reviewer: Acceptance Auditor
Baseline: `2028d51` → `1bf2934` (diff: `src/`)
Spec: `_bmad-output/implementation-artifacts/1-1-scaffold-the-provisioning-package.md`

## Verdict per AC

| AC | Status | Evidence |
|----|--------|----------|
| AC 1 — pyproject at `src/provisioning/pyproject.toml`, name `dotfiles-provision`, entry point `dotfiles-provision`, runtime deps `typer`, `pydantic`, `cli-output` (via `uv.sources`), `ansible-core` | **PASS** | `name = "dotfiles-provision"`, `[project.scripts] dotfiles-provision = "provisioning.cli.main:app"`, `dependencies = ["typer>=0.12", "pydantic>=2.0", "cli-output", "ansible-core>=2.16"]`, `[tool.uv.sources] cli-output = { path = "../shared/cli-output", editable = true }` |
| AC 2 — dev deps `pytest`, `ruff`, `mypy` | **PASS** | `[dependency-groups] dev = ["pytest>=8.0", "ruff>=0.15.17", "mypy>=1.10"]` |
| AC 3 — stub CLI invoking `cli-output` renders a version string and exits 0 | **PASS** | `uv run python -m provisioning.cli.main version` → `{"version": "0.1.0"}`, `exit=0`; rendered via `create_renderer(OutputFormat.JSON).custom(CustomView(...))` from `cli_output`; 4 tests pass |
| AC 4 — layout mirrors `src/shared/cli-output/` | **PASS** | `src/provisioning/{pyproject.toml, uv.lock, README.md, src/provisioning/, tests/}`; wheel `packages = ["src/provisioning"]`; pytest/ruff config mirror `cli-output` conventions |
| AC 5 — `uv lock` resolves without errors | **PASS** | `uv lock --check` → "Resolved 33 packages in 2ms" |
| §11 boundary — only `cli-output` cross-package | **PASS** | Lock shows `dotfiles-provision` deps = {`ansible-core` (PyPI), `cli-output` (editable path), `pydantic`, `typer`}; source imports only `cli_output` modules; no `core`/`infrastructure`/CLI-tool packages |
| Scope — no domain/ports/adapters/application pre-scaffolded | **PASS** | Tracked package tree contains only `cli/` under `src/provisioning/src/provisioning/`; no `ansible/`, no hexagon layers |

## Findings

- **LOW — Spec `File List` references `.python-version` that was never created/committed**
  - Constraint: none (not an AC), but the story's completion record claims the file.
  - Evidence: `git diff 2028d51..1bf2934 -- src/` adds only 7 files (README, pyproject.toml, `__init__.py`, `cli/__init__.py`, `cli/main.py`, `tests/test_cli.py`, `uv.lock`); `ls src/provisioning/.python-version` → "No such file or directory".

- **LOW — Error path in `version` command bypasses `cli-output`**
  - Constraint: §Dev Notes "Stub CLI via `cli-output`" — must render via `cli-output`, "not print to stdout directly".
  - Evidence: `src/provisioning/src/provisioning/cli/main.py:139-140` — `msg = json.dumps({"error": ...}); print(msg, file=sys.stderr)` on `PackageNotFoundError`. Success path renders via `cli-output`; the failure path emits directly. Strictly a letter-of-spec deviation, defensible as an edge path (stderr, not stdout).

- **INFO — Duplicate version source: `__version__` constant is dead code**
  - Constraint: none.
  - Evidence: `__init__.py` defines `__version__ = "0.1.0"` (exported in `__all__`) but the CLI resolves the version via `importlib.metadata.version("dotfiles-provision")` (`cli/main.py:137`), not the constant — two sources can drift.

## Verification commands run

- `uv run pytest -q` in `src/provisioning` → 4 passed.
- `uv run python -m provisioning.cli.main version; echo $?` → JSON `{"version": "0.1.0"}`, exit 0.
- `uv lock --check` → Resolved 33 packages, no errors.
- `uv run ruff check .` → All checks passed; `uv run mypy src` → Success (3 files).
- `git diff --name-status 2028d51..1bf2934 -- src/` → 7 added files only.
