## Context

`tests/architecture/test_layering.py` is the only mechanical guard against hexagonal-layering drift in `oci-runtime`. Today it is a 166-LOC AST-based importer that walks `oci_runtime.*` import statements across the package and asserts direction (domain → ports → adapters → factory). It does NOT inspect stdlib imports, does NOT verify that `ports/` contains only abstract interfaces, and has a stale allowlist inconsistency between its docstring (`:8-10`) and `_ALLOWED_TARGETS` (`:35-41`).

Two artifacts currently sit in the wrong layer undetected:

1. `domain/build_tar.py:2` imports `os` (environment-coupled dispatch via `os.path`) — flagged for fix by the gated change `oci-build-tar-posixpath`.
2. `ports/cancellation.py:16,30,58` and `ports/pipe_reader.py:21` define concrete classes that do `os.read` and `threading.Timer` — flagged for fix by the gated change `oci-cancellation-adapter-relocation`. v3 commit `1953540` relocated these from `adapters/` into `ports/` "for testability," which is empirically false: tests patch the adapter module's binding (`"oci_runtime.adapters.transport.cli.ProcessPipeReader"`), not the class's source location.

This change (`oci-strict-hexagonal-layering-v2`) strengthens the test to detect both classes of violations. It is purely additive to `tests/architecture/test_layering.py`. No production code is touched. It replaces the xfail/mark model: the new rules land first (red), then the gated changes make them green.

The same `oci-runtime-audit-remediation-v5` series uses this as the architectural foundation — without it, A1 and A3 are judgment calls that loop (v2 extracted build_tar to adapters, v3 reverted it; this change makes the swap to `posixpath` the only mechanically valid resolution).

## Goals / Non-Goals

**Goals:**
- Make the layering test mechanically enforce: domain stdlib allowlist, domain banned-stdlib, ports-must-be-ABC-or-typed-dataclass-aggregate, Path FS-method-call ban.
- Fix `_ALLOWED_TARGETS["adapters"]` docstring inconsistency (add `"adapters"` so the rule matches the docstring, allowing shared adapter utilities like the proposed `_SubprocessRunner`).
- The test MUST go red on the current HEAD for the two artifacts above, so the gated wave-2 changes go green by satisfying the new rules.
- Each rule is testable in isolation via a small targeted self-test.
- The xfail/mark strategy preserves CI signal between this change and the gated wave-2 changes merging.

**Non-Goals:**
- Moving any concrete classes out of `ports/` (that's `oci-cancellation-adapter-relocation`).
- Swapping `os.path` → `posixpath` in `domain/build_tar.py` (that's `oci-build-tar-posixpath`).
- The `RuntimeFactoryConfig` builder pattern (that's `oci-factory-builder-pattern`).
- Any `src/` or production-code change of any kind.
- Verifying that domain modules don't *call* methods on imports from `adapters` — only imports are checked. Behavioral-purity analysis is out of scope.
- Enforcing architectural rules for `tests/` itself — the test suite is not hexagonal; conventions there are tracked separately under `oci-test-contracts`.

## Decisions

### Decision 1: Allowlist rather than blocklist for domain stdlib imports

A blocklist ("domain must not import these") is brittle — every new stdlib module not yet imagined would be implicitly allowed. An allowlist (`_DOMAIN_ALLOWED_STDLIB = {posixpath, io, tarfile, pathlib, json, re, dataclasses, collections, collections.abc, types, enum}`) is opt-in: any new stdlib import in `domain/` requires both a code edit (adding to the set) and a spec edit (amending `oci-strict-hexagonal-layering-v2`'s allowlist requirement). This makes the addition a deliberate, reviewed decision rather than a silent allow.

**Alternative considered**: blocklist of `subprocess`, `os`, `shutil` etc. Rejected — version-bump stdlib additions would slip in silently; the audit's stated goal is to make decisions reviewable.

### Decision 2: Banned-stdlib is a SEPARATE requirement from the allowlist

The allowlist says "x is in the allowlist" (opt-in). The banned-list says "x must not appear" (opt-out). Combining them into one set operation (`allowed := allowlist - banned`) loses the audit distinction: A1's `os` import would fail the allowlist check AND the banned check, but they are different classes of issue (allowlist: "you didn't explicitly allow this"; banned: "this module is forbidden regardless"). Keeping them separate makes the failure message actionable. Both rules fail independently; a future audit can cite either or both.

### Decision 3: Ports-must-be-ABC-or-@dataclass-aggregate uses static AST analysis, not runtime introspection

The rule is enforced by walking each `ports/*.py` AST and classifying each top-level `ClassDef`:

- If it has `bases` containing an `ast.Attribute` access of `ABC` (or `Subscript`/`Name` pointing to `ABC`) AND has at least one method with the `@abstractmethod` decorator → pass (branch 1).
- If it has `@dataclass` in `decorator_list` AND no non-dunder method bodies (only `__init__`/`__post_init__`/`__repr__`/etc.) → pass (branch 2, typed aggregate).
- Otherwise → fail with the message `ports/<file> declares concrete class '<name>'; relocate to adapters/`.

**Why static, not runtime introspection (`issubclass(X, ABC)`)**. `issubclass` requires importing the file, which means a layering violation in `ports/` would silently pass if the import itself raises (e.g. circular import). AST is import-free; the rule holds even if the code under analysis is broken. Static also catches the case where the file's *only* concrete class is the violation — runtime introspection would import the wrong thing first.

**Why not `typing.Protocol` membership / structural typing**. The codebase uses ABCs throughout; changing the structural-conformance model is out of scope (would belong in a `oci-protocol-typing` change). This change locks the current `ports/` composition rule under the present type system.

### Decision 4: Path FS-method ban uses conservative name-based AST inspection

The rule walks each `domain/*.py` AST and flags any `ast.Call` node whose `func` is an `ast.Attribute(attr=<banned_method_name>)`. The method name is checked against `_BANNED_PATH_FS_METHODS = {"exists", "read_text", "read_bytes", "write_text", "write_bytes", "glob", "rglob", "iterdir", "mkdir", "rmdir", "unlink", "chmod", "chown", "stat", "lstat", "touch"}`.

**Why conservative** (flag by name, even when the receiver is not statically known to be a `Path`). Type inference at AST level is brittle; safety by name catches `.read_text()` on a `bytes` object too (which is not a Path method). False positives are rare and caught at code review; false negatives (a real `Path.read_text()` slipping through) are worse. The conservative rule sacrifices ~zero ergonomics — no domain module currently calls any banned method name on any receiver.

**Alternative considered**. Annotate each `ast.Call` with the inferred receiver type via `mypy --follow-imports` output. Rejected — too brittle, too slow for a unit-test layer, mismatched with the AST-only philosophy of the existing linter.

### Decision 5: xfail/mark strategy for the window between merge and wave-2

If this change merges before `oci-build-tar-posixpath` and `oci-cancellation-adapter-relocation`, the linter will be red on `domain/build_tar.py` (`os` banned) and on `ports/cancellation.py`/`ports/pipe_reader.py` (concrete classes in ports). Strategy:

- The new rules commit *without* xfail; the test fails on HEAD.
- **Commit policy**: this change is merged together with the two gated wave-2 changes in a single PR/trainsaction (preferred), OR
- The new rules commit `with pytest.mark.xfail` on the specific failing subtests (named: `test_no_layering_violations[domain/build_tar.py]`, `test_no_layering_violations[ports/cancellation.py]`, `test_no_layering_violations[ports/pipe_reader.py]`, `test_ports_files_are_abstract_only`) AND the wave-2 changes land within the same PR series. xfail markers are removed when wave-2 lands.

The preferred path is to land this change + the two gated wave-2 changes together. The xfail path is documented here as the fallback for unavoidable split-PR situations.

## Risks / Trade-offs

- **[Risk] Conservative Path FS-method ban flags `.read_text()` on non-Path receivers** → Mitigation: false positives are caught at code review during the same change that introduces the call; no current code is affected. If a real need arises, the spec is amended to add an exemption rule.
- **[Risk] Adding new stdlib to the allowlist becomes friction-heavy (spec amendment required)** → Mitigation: this is the explicit goal. Any friction is the audit signal; if v6 audit wants to add a stdlib in domain, the spec amendment is the artifact that captures the decision.
- **[Risk] `pathlib.Path` as a field-type annotation opens methods (`.resolve()`, `.with_suffix()`) that are pure** → Mitigation: `.resolve()` (which calls `os.path.realpath` under the hood) IS in the banned list (any method called `.resolve` is flagged conservatively). `.with_suffix` is NOT called in domain today; if it's needed, add it to the allowlist-of-methods after spec amendment. The conservative stance wins.
- **[Risk] The ports-ABC rule uses class-level `bases`/`decorators` detection that misses metaclass-based ABCs** → Mitigation: scan via `ast.walk` for `metaclass=ABCMeta` argument too; include it in branch 1. (If encountered; none exist today.)
- **[Risk] New rules introduce test runtime > 500ms** → Mitigation: AST parsing of ~60 files is well under 100ms; no concern.
- **[Risk] xfail markers leak past wave-2 merge** → Mitigation: the `oci-v5-remediation-doc-sync` verification change (the last in the series) explicitly checks for residual xfail markers; leaving them blocks the v5 series from declaring done.

## Open Questions

- Do we want to also inspect `typing.TYPE_CHECKING` guarded imports for the stdlib-allowlist rule (a `if TYPE_CHECKING: import os` could smuggle stdlib via type-only imports used at runtime — though with type-only imports this is impossible since the body never runs)? Current answer: no — `TYPE_CHECKING`-guarded imports are never executed at runtime and therefore cannot violate purity; the rule only inspects runtime-imports. If ambiguity arises during implementation, this can be tightened.

- Should the banned FS-method list be shared with future `pathlib`-purity checks in `adapters/` (adapters should arguably be *allowed* to call `Path.exists()` — that's their job)? Current answer: the banned-list rule is explicitly scoped to `domain/`; adapters are unaffected. If a future change wants to extend the rule to other layers, it would need its own spec.