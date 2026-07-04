## 1. Fix the adapters allowlist inconsistency

- [ ] 1.1 In `tests/architecture/test_layering.py:38` change `_ALLOWED_TARGETS["adapters"]` from `{"domain", "ports"}` to `{"domain", "ports", "adapters"}`. Verify the docstring at `:8-10` ("adapters -> ... + oci_runtime.adapters.*") now matches.
- [ ] 1.2 Add a scenario to `test_adapters_import_no_factory` (or extend the parametrized `test_no_layering_violations` self-check) covering "adapter importing another adapter passes" (synthetic violation temp-file or test fixture if needed; if the AST-walk approach doesn't naturally support a synthetic test, add an inline `test_adapters_allowed_targets_includes_adapters` that reads the `_ALLOWED_TARGETS["adapters"]` dict directly).
- [ ] 1.3 Run `uv run pytest -q tests/architecture` — must still be green on HEAD (no real adapter cross-imports exist today; the change is to the rule, not to existing-code behavior).
- [ ] 1.4 Run `uv run ruff check tests/architecture/test_layering.py` — green.

## 2. Add the domain stdlib allowlist requirement

- [ ] 2.1 Near the top of `tests/architecture/test_layering.py`, define `_DOMAIN_ALLOWED_STDLIB = {"posixpath", "io", "tarfile", "pathlib", "json", "re", "dataclasses", "collections", "collections.abc", "types", "enum"}` as a module-level frozenset with a comment pointing at `oci-strict-hexagonal-layering-v2/specs/oci-strict-hexagonal-layering/spec.md`.
- [ ] 2.2 Extend `_extract_oci_runtime_imports` (or add a sibling `_extract_stdlib_imports(tree) -> list[str]`) that walks `ast.Import`/`ast.ImportFrom` and returns the top-level stdlib module name for each import. Handle dotted stdlib (`from collections.abc import Mapping` → `"collections.abc"`; `import json` → `"json"`).
- [ ] 2.3 Add `test_domain_stdlib_imports_are_allowlisted` to `TestHexagonalLayering`: for each file in `_SRC_ROOT / "domain"`, parse AST; for each stdlib import, assert membership in `_DOMAIN_ALLOWED_STDLIB`. Failure message format: `domain layer imports non-allowlisted stdlib: <module> in <file_relative_path>`.
- [ ] 2.4 Add a self-test `test_domain_stdlib_allowlist_self_test` covering: (a) a synthetic AST with `ast.parse("import json")` passes; (b) `ast.parse("import os")` fails; (c) `ast.parse("from collections.abc import Mapping")` passes (top-level `collections.abc` is allowlisted); (d) `ast.parse("import base64")` fails (NOT in allowlist). Add synthetic-via-in-memory-source tests rather than on-disk tempfiles to keep the test fast and side-effect-free.
- [ ] 2.5 Run `uv run pytest -q tests/architecture/test_layering.py` — `test_domain_stdlib_imports_are_allowlisted` MUST fail on HEAD because `domain/build_tar.py:2` imports `os` (not in allowlist). This is the expected red state until `oci-build-tar-posixpath` lands. Apply `pytest.mark.xfail(reason="pending oci-build-tar-posixpath wave-2 change")` to ONE specific failure case (the os import in build_tar) — the test should still fail loudly on any OTHER unlisted stdlib.
- [ ] 2.6 Run `uv run ruff check tests/architecture` — green.

## 3. Add the domain banned-stdlib requirement

- [ ] 3.1 Define `_DOMAIN_BANNED_STDLIB = {"subprocess", "os", "shutil", "select", "selectors", "socket"}` as a module-level frozenset with a comment pointing at the spec.
- [ ] 3.2 Add `test_domain_imports_no_banned_stdlib` to `TestHexagonalLayering`: for each file in `_SRC_ROOT / "domain"`, parse AST; for each stdlib import, assert the top-level module is NOT in `_DOMAIN_BANNED_STDLIB`. Failure message format: `domain layer imports banned stdlib: <module> in <file_relative_path>`.
- [ ] 3.3 Add a self-test `test_domain_banned_stdlib_self_test` covering: `import subprocess` fails, `import os` fails, `from os import path` fails (top-level `os`), `import json` passes (not banned), `import posixpath` passes (not banned).
- [ ] 3.4 The same `os` import in `domain/build_tar.py` triggers BOTH this rule and the allowlist rule (#2). Apply `pytest.mark.xfail(reason="pending oci-build-tar-posixpath wave-2 change")` only at the build_tar-specific granularity (e.g. `pytest.param(..., marks=pytest.mark.xfail(...))` inside the parametrized list) so the rule still fails loudly on a *new* `subprocess` import anywhere else.
- [ ] 3.5 Run `uv run pytest -q tests/architecture` — only the xfail-marked cases are xfailed; everything else green.
- [ ] 3.6 Run `uv run ruff check tests/architecture` — green.

## 4. Add the ports-ABC-or-@dataclass-aggregate requirement

- [ ] 4.1 Define `_PORTS_ALLOWED_AGGREGATES = {(ports/aggregates.py, Parsers), (ports/capabilities.py, RuntimeCapabilities)}` — note: with A3's re-extraction not yet landed, `ProcessPipeReader`, `ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken` are NOT in this set (they are violations that this rule will catch).
- [ ] 4.2 Add a helper `_classify_ports_class(node: ast.ClassDef) -> str` that returns one of `"abc"`, `"dataclass-aggregate"`, or `"concrete"`. Detection logic per design Decision 3:
  - Has `@abstractmethod`-decorated method AND inherits (directly or via `Subscript`/`Attribute`) `ABC` → `"abc"`.
  - Has `@dataclass` decorator AND has only dunder methods (no `@abstractmethod`, no non-dunder non-aggregate methods with side-effecting calls like `os.read`, `threading.Timer`, `subprocess.Popen`) → `"dataclass-aggregate"`.
  - Otherwise → `"concrete"`.
- [ ] 4.3 Add `test_ports_files_are_abstract_only` to `TestHexagonalLayering`: for each `.py` file in `_SRC_ROOT / "ports"`, parse AST; for each top-level `ast.ClassDef`, classify via `_classify_ports_class`; assert the classification is `"abc"` OR the class name is in `_PORTS_ALLOWED_AGGREGATES` for that file. Failure message: `<file>:<line> declares concrete class '<name>' which is neither an ABC nor a @dataclass aggregate; relocate to adapters/`.
- [ ] 4.4 Add a self-test `test_ports_classification_self_test` covering: synthetic `class Foo(ABC): @abstractmethod def m(self): ...` → `"abc"`; synthetic `@dataclass(frozen=True) class Bar: x: int` → `"dataclass-aggregate"`; synthetic `class Baz: def m(self): import os; os.read(...)` → `"concrete"`.
- [ ] 4.5 Apply `pytest.mark.xfail(reason="pending oci-cancellation-adapter-relocation wave-2 change")` to the four expected-failing cases: `ports/cancellation.py` × 3 (ThreadCancellationToken, DeadlineCancellationToken, CompositeCancellationToken) and `ports/pipe_reader.py` × 1 (ProcessPipeReader). The rule still fails loudly on any new concrete class.
- [ ] 4.6 Run `uv run pytest -q tests/architecture` — only the four xfailed cases are xfailed; everything else green.
- [ ] 4.7 Run `uv run ruff check tests/architecture` — green.

## 5. Add the pathlib FS-method-call ban requirement

- [ ] 5.1 Define `_BANNED_PATH_FS_METHODS = frozenset({"exists", "read_text", "read_bytes", "write_text", "write_bytes", "glob", "rglob", "iterdir", "mkdir", "rmdir", "unlink", "chmod", "chown", "stat", "lstat", "touch", "resolve"})` as a module-level constant with a comment pointing at the spec. (`resolve` is included because `Path.resolve()` calls `os.path.realpath` under the hood — environment coupling.)
- [ ] 5.2 Add a helper `_scan_for_banned_method_calls(tree) -> list[tuple[int, str]]` that walks the AST, finds every `ast.Call` whose `func` is `ast.Attribute(attr=<name>)` with `name` in `_BANNED_PATH_FS_METHODS`, and returns `(lineno, name)` tuples.
- [ ] 5.3 Add `test_domain_no_path_fs_method_calls` to `TestHexagonalLayering`: for each `.py` file in `_SRC_ROOT / "domain"`, parse AST; scan via the helper; assert the returned list is empty. Failure message: `<file>:<line> calls Path.<method>() — FS methods on Path are forbidden in domain; delegate to an adapter`.
- [ ] 5.4 Add a self-test `test_path_method_ban_self_test` covering: synthetic `ast.parse("if p.exists(): pass")` → flagged on `exists`; synthetic `ast.parse("text = p.read_text()")` → flagged on `read_text`; synthetic `ast.parse("text = bytes(b'x').decode()")` → NOT flagged; synthetic `ast.parse("data = bytes(b'x')")` → NOT flagged.
- [ ] 5.5 Run `uv run pytest -q tests/architecture` — must be green on HEAD (no domain code currently calls any banned method name on any receiver). If a surprise fail appears, investigate and either (a) the call is genuinely an I/O leak — report and fix as a new finding, or (b) the method-name match is too broad — restrict the rule per design Open Question (e.g. exclude dunder methods already filtered elsewhere).
- [ ] 5.6 Run `uv run ruff check tests/architecture` — green.

## 6. Verification & docs

- [ ] 6.1 Run the full linter self-check: `python tests/architecture/test_layering.py` (the `if __name__ == "__main__"` block at `:155-166`). Update the final print line to reflect the new rule count: `OK: N source files checked across 4 architectural rules (layering, allowlist, ports-ABC, path-FS-ban).` (exact wording — verify it's accurate).
- [ ] 6.2 Run `uv run pytest -q tests/architecture` — full green with the documented xfails only. xfails MUST be limited to: 1 in §2/§3 (build_tar os import — counted once across both rules because xfail is per-test, not per-violation), 3 in §4 (the three cancellation classes), 1 in §4 (ProcessPipeReader). Total ≤ 5 xfails. Adjust if rules share xfails differently.
- [ ] 6.3 Run `uv run pytest -q` (full suite) — no regressions in unrelated tests.
- [ ] 6.4 Run `uv run ruff check .` and `uv run --with mypy --with pathspec mypy tests/architecture/test_layering.py` — green (mypy on tests may be optional per repo conventions; if mypy isn't configured for tests/, skip).
- [ ] 6.5 Commit message: `test(oci-runtime): strengthen layering linter — stdlib allowlist, banned-stdlib, ports-ABC, path-FS-method ban`. Document the gated wave-2 changes in the commit body: `xfail markers on domain/build_tar.py (banned os import → oci-build-tar-posixpath) and on ports/cancellation.py + ports/pipe_reader.py (concrete classes in ports → oci-cancellation-adapter-relocation) are removed when those changes land.`
- [ ] 6.6 Verify the gates: confirm via `git log --oneline openspec/changes/oci-strict-hexagonal-layering-v2/` that this change commits proposals + design + specs + tasks as a unit (per repo convention) before opening the merge.