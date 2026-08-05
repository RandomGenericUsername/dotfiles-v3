# Blind Hunter Review — Story 1.1: Scaffold the Provisioning Package

**Reviewer role:** Cynical adversarial reviewer (bmad-review-adversarial-general).
**Target:** `git diff 2028d51..1bf2934 -- src/` (the Story 1.1 scaffold commit).
**Date:** 2026-08-03
**Verdict:** Conditional pass — ACs 1–5 and the §11 boundary are met, but the story's own quality claims ("mypy clean", "renders through cli-output") are overstated, and the error path breaks the package's stated output contract. No security defects, no §11 violation.

---

## Verified claims (honest accounting)

What I actually ran in `src/provisioning/` (repo venv):

- `pytest tests/` → **4 passed**. ✓
- `ruff check src tests` → clean; `ruff format --check` → clean. ✓
- `mypy src` → "Success: no issues found in 3 source files". ✓ (but see Finding 1)
- `mypy src tests` → **2 errors** (tests not strict-clean). ✗
- `.venv/bin/dotfiles-provision version` → `{"version": "0.1.0"}` exit 0. ✓
- Simulated not-installed path → exit 1, stderr `{"error": "dotfiles-provision package not installed"}`. ✓ but see Finding 2.
- `git ls-files src/provisioning/` → 7 files; no `.python-version` despite story File List claiming it (Finding 10).
- §11 boundary: only cross-package import is `cli_output`; pyproject cross-deps limited to `cli-output` (+ third-party typer/pydantic/ansible-core). No violation. ✓
- No domain/ports/adapters/application folders prematurely created. ✓ (scope discipline held)

---

## Findings

### 1. [MEDIUM] The "mypy clean (strict)" completion claim is false — tests are not type-safe and no gate covers them

Story change-log and completion notes state "mypy clean (strict, `import-untyped` disabled)". This only holds for `mypy src`. Running the configured strict mypy over the package's own test suite fails:

```
tests/test_cli.py:20: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]
tests/test_cli.py:23: error: Function is missing a type annotation  [no-untyped-def]
```

`tests/test_cli.py:20` — `def test_version_exits_nonzero_when_package_not_installed(self, monkeypatch) -> None:` — `monkeypatch` is untyped (strict requires a `pytest.MonkeyPatch` annotation). `tests/test_cli.py:23` — `def _raise(*args, **kwargs):` has no return annotation and no params, which `disallow_untyped_defs` (strict) rejects.

The `[tool.mypy]` block has no `exclude`/`files`, so a repo-wide `mypy .` or a future CI gate that checks everything fails today. Because the tests were evidently checked by running `mypy src` only, strictness is not actually protecting the tests, and the "clean" claim in the story record is misleading.

### 2. [MEDIUM] Error path bypasses the cli-output renderer and emits a divergent JSON contract

`src/provisioning/src/provisioning/cli/main.py:42-44`:

```python
msg = json.dumps({"error": "dotfiles-provision package not installed"})
print(msg, file=sys.stderr)
raise typer.Exit(code=1) from None
```

The story requirement is "the stub must render a version string through `cli-output` (not print to stdout directly)" and the package docstring promises "Renders structured output through the shared `cli-output` package." The error branch violates this twice:

1. It hand-rolls JSON with `json.dumps` + `print` instead of the renderer — the same bypass the story explicitly prohibits for the success path.
2. The emitted schema `{"error": "..."}` (compact separators, no indent) is inconsistent with the renderer's error contract `ErrorView` → `{"kind": ..., "message": ...}` and its indented serialization (`json_renderer.py:74-87`). Any downstream consumer parsing stderr gets a different shape and formatting than the stdout contract — the exact inconsistency cli-output exists to eliminate.

This will also silently ignore the output-format flag when Story 1.8 adds one: the success path respects format via the renderer, the error path is hard-wired.

### 3. [MEDIUM] `_renderer()` is annotated `-> object` — type erasure that hides the dependency direction

`src/provisioning/src/provisioning/cli/main.py:28-29`:

```python
def _renderer() -> object:
    return create_renderer(OutputFormat.JSON)
```

`create_renderer` returns `Renderer` (`cli_output.adapters.factory.py:12`). Declaring the return as `object` throws that information away; the subsequent `ctx.obj["renderer"].custom(...)` (`main.py:46`) only type-checks because `ctx.obj` is `Optional[Any]` in Typer, so the call is entirely unchecked. A typo such as `.cutom(...)` would pass mypy and fail at runtime.

The correct signature is `-> Renderer` (imported from `cli_output.ports.renderer`), which would also express the intended boundary: provisioning should depend on the renderer *port*, not reach into the shared package's adapter internals (`cli_output.adapters.factory`). The hexagon ordering convention (ports are the inter-package seam) is being violated at the type level.

### 4. [LOW-MEDIUM] `version` hard-fails from a source checkout instead of reporting the in-repo version

`src/provisioning/src/provisioning/cli/main.py:40-44`: `version` reads `importlib.metadata.version("dotfiles-provision")` and exits 1 on `PackageNotFoundError`. Run the CLI from a source checkout where the distribution isn't installed (e.g., `python -m provisioning.cli.main` or a bare CI checkout before `uv sync`), and a tool whose sole job is to report its own version refuses to run — even though `provisioning.__version__` (`__init__.py:6`) is sitting right there.

This also makes `tests/test_cli.py:14-18` silently environment-dependent: `test_version_renders_version_string` passes only because the project happens to be installed in the venv; in any environment where the metadata lookup fails, the test flips to asserting exit 0 against an exit-1 result and fails in a way that is easy to misdiagnose. A fallback to `provisioning.__version__` would make the command (and the test) robust.

### 5. [LOW] Three sources of truth for the version; the `__version__` constant is dead code

`pyproject.toml:20` (`version = "0.1.0"`), `src/provisioning/src/provisioning/__init__.py:6` (`__version__ = "0.1.0"`), and the installed distribution metadata (read by `main.py:40`). The CLI never imports `provisioning.__version__`, so the constant is decorative. When the package version is bumped (pyproject + metadata), the `__init__` constant will silently drift unless someone remembers it — and nothing enforces agreement. Either the command should source `provisioning.__version__` or the constant should be dropped.

### 6. [LOW] `--help` advertises commands that do not exist in this build

`src/provisioning/src/provisioning/cli/main.py:19-23` — the app help enumerates `plan`, `apply`, `verify`, `bootstrap`. None of these commands exist (they arrive in Story 1.8). A user of the current build runs `dotfiles-provision --help` and sees four commands that error out as unknown. Forward-documentation is defensible, but it makes the shipped artifact lie about its own surface; at minimum the help should say "planned" or defer the command list to Story 1.8.

### 7. [LOW] Weak test assertions that would not catch real regressions

`tests/test_cli.py:18` — `assert "version" in data` passes if the value is `"garbage"`, `""`, or `null`; it never pins the value to `__version__`/pyproject version, so the test that is the story's only behavioral proof cannot detect version drift or a broken metadata path returning junk. `tests/test_cli.py:29-30` — the not-installed test asserts only `exit_code != 0`; it does not assert the stderr schema, so Finding 2's contract divergence is invisible to the suite. The mypy errors in Finding 1 are also uncaught because no gate runs mypy over `tests/`.

### 8. [LOW] `disable_error_code = ["import-untyped"]` is a global hole that will mask more than intended

`src/provisioning/pyproject.toml:61`. The workaround exists because the local `cli-output` package ships no `py.typed` marker. But the global disable applies to the entire package for all time — including Story 1.5, when adapters begin importing `ansible-core` (which has no type hints). Every future genuinely-untyped import will be silently swallowed, and strictness for provisioning's own imports of untyped third parties is permanently disabled. Scoping the suppression (a targeted `# type: ignore[import-untyped]` at each call site, or adding `py.typed` to `cli-output`) preserves strictness without the blanket amnesty.

### 9. [LOW] Output format is hard-wired with no selection surface

`src/provisioning/src/provisioning/cli/main.py:29` — `create_renderer(OutputFormat.JSON)` is fixed at callback construction time and stored in `ctx.obj`. There is no `--output`/`--format` flag (Story 1.8 may add one), but the design already makes retrofitting awkward: the renderer is chosen before any command sees the invocation options, so threading a format choice in will require restructuring the callback rather than a flag parse. Acceptable for a scaffold, but worth a deliberate decision now.

### 10. [LOW] Story record inaccuracy: `.python-version` is listed as created but does not exist

The story File List (`_bmad-output/implementation-artifacts/1-1-scaffold-the-provisioning-package.md:164`) documents `src/provisioning/.python-version (new)`. It is absent from the diff, from `git ls-files`, and from the working tree. Consequences: (a) the artifact record misrepresents what was delivered; (b) nothing pins the package to a concrete interpreter — version selection relies solely on `requires-python = ">=3.12"` while the rest of the repo mixes 3.12/3.14 conventions. Either add the file (and a `.gitignore` entry if it is meant to be local) or correct the record.

### 11. [LOW/INFO] `pydantic>=2.0` is declared but completely unused

`src/provisioning/pyproject.toml:26`. It is required by AC 1, so this is not a scope violation — but it is a dependency with zero code, and `uv.lock` resolves it into every install. Fine for now; flag it so it isn't silently carried if later stories turn out not to need it.

### 12. [INFO] Renderer carried through `ctx.obj` as a plain dict — unchecked runtime plumbing

`src/provisioning/src/provisioning/cli/main.py:34,46`: `ctx.obj = {"renderer": ...}` then `ctx.obj["renderer"].custom(...)`. Typer types `ctx.obj` as `Optional[Any]`, so a wrong key (`ctx.obj["renderers"]`) or a command invoked without the callback produces a `KeyError`/`AttributeError` at runtime with zero static coverage. It works, but it is the weakest seam in an otherwise type-strict package.

---

## Non-findings (checked, no issue)

- **§11 boundary:** only `cli_output` is imported from repo packages; `core`, `infrastructure`, and all CLI-tool packages are absent. Clean.
- **`uv.sources` path:** `../shared/cli-output` is correct for `src/provisioning/` (the CSG `../../` copy would have been wrong — the story's own debug log documents this).
- **Hatchling packaging config:** `packages = ["src/provisioning"]` is consistent with the `cli-output`/CSG convention; the entry point `provisioning.cli.main:app` resolves and the console script works (verified).
- **Metadata lookup normalization:** `importlib.metadata.version("dotfiles-provision")` correctly normalizes the dash/underscore and resolves against the editable install (verified at runtime).
- **Security:** no secrets, no shell/subprocess, no file I/O, no untrusted input in the scaffold. No security issues.
- **Lockfile:** resolves 33 packages; `cli-output` editable source and `requires-dist` metadata in `uv.lock` match `pyproject.toml`.

---

## Suggested remediation (highest value first)

1. Annotate `monkeypatch: pytest.MonkeyPatch` and `_raise` (or add a return annotation) so `mypy src tests` passes; then run mypy over both in the completion check. (Finding 1)
2. Route the not-installed error through the renderer's `ErrorView` (stderr) or at minimum match `json_renderer`'s indentation/schema. (Finding 2)
3. Change `_renderer() -> object` to `-> Renderer` imported from `cli_output.ports.renderer`. (Finding 3)
4. Fall back to `provisioning.__version__` when the distribution isn't installed; have the test assert the exact version value. (Findings 4, 5, 7)
5. Fix the story record (drop or add `.python-version`) and scope the `import-untyped` disable. (Findings 10, 8)
