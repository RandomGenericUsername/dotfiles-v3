## Why

The existing `tests/architecture/test_layering.py` linter (`oci-strict-hexagonal-layering`) is decorative in three concrete ways:

1. It only inspects `oci_runtime.*` imports — never stdlib. So the domain layer importing `os`, `subprocess`, or `shutil` (the open A1 circle: `domain/build_tar.py` uses `os.path`) is invisible to the test.
2. It does not constrain what may live in `ports/` — so when v3 commit `1953540` relocated `ProcessPipeReader` (does `os.read`), `ThreadCancellationToken`, and `DeadlineCancellationToken` (manages `threading.Timer`) from `adapters/` into `ports/`, the test silently accepted the violation. Worse, that relocation contradicts the existing spec at `oci-strict-hexagonal-layering/spec.md:86` which states `ThreadCancellationToken` and `DeadlineCancellationToken` "remain in `adapters/_cancellation.py`" — the v3 commit introduced both a code violation and a spec drift that no test caught.
3. `_ALLOWED_TARGETS["adapters"]` at `test_layering.py:38` omits `"adapters"`, contradicting the docstring at `:8` ("adapters -> ... + oci_runtime.adapters.*") — the rule's text and the docstring's text disagree.

Self-run today prints `OK: 58 source files, no layering violations` despite all of the above. A passing test that proves nothing is worse than no test — it gives false confidence. This change makes the three gaps mechanically enforced.

This change is foundational for the v5 audit cycle: it gates `oci-build-tar-posixpath` (A1) and `oci-cancellation-adapter-relocation` (A3) via TDD red→green — the layering rules here are what make those later changes verifiable rather than judgment-call-driven.

## What Changes

- **MODIFY** the existing architecture-linter requirement to fix the adapters-allowlist/docstring inconsistency: `_ALLOWED_TARGETS["adapters"]` MUST include `"adapters"` (matching the docstring).
- **ADD** a new requirement: domain stdlib imports MUST be in an explicit allowlist. The allowlist is opt-in (`{posixpath, io, tarfile, pathlib, json, re, dataclasses, collections, collections.abc, types, enum}`); adding any new stdlib to the domain layer requires editing the allowlist *and* amending this spec.
- **ADD** a new requirement: domain MUST NOT import banned stdlib (`subprocess`, `os`, `shutil`, `select`, `selectors`, `socket`). Separate from the allowlist — the allowlist is opt-in per-module, the banned-list is opt-out cross-cutting.
- **ADD** a new requirement: every `class` declaration in `ports/*.py` MUST either (a) inherit from `abc.ABC` with at least one `@abstractmethod`, or (b) be a `@dataclass`-typed aggregate container. No carve-out — combos like `ProcessPipeReader` and `*CancellationToken` are banned from `ports/` by this rule (their relocation is reversed by the separately-tracked `oci-cancellation-adapter-relocation` change).
- **ADD** a new requirement: `pathlib.Path` is allowed in `domain/` (it is in the allowlist), but FS-method calls on `Path` instances inside `domain/` (`Path.exists`, `Path.read_text`, `Path.read_bytes`, `Path.write_text`, `Path.glob`, `Path.rglob`, `Path.iterdir`, `Path.mkdir`) are forbidden. Enforced via AST attribute-call inspection. This makes the pathlib decision honest — `Path` as a value object is allowed, `Path` as an I/O handle is not.

No public-API changes. No production-code changes outside `tests/architecture/test_layering.py`. The strengthened test MAY go red on the current HEAD (specifically `domain/build_tar.py`'s `os` import and the `ports/` concrete classes from the v3 relocation); those become green again when the gated wave-2 changes (`oci-build-tar-posixpath`, `oci-cancellation-adapter-relocation`) land. The test is committed with the new rules active; the wave-2 changes must land to restore green.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `oci-strict-hexagonal-layering`: Three new requirements added (domain-stdlib-allowlist, domain-banned-stdlib, ports-must-be-ABC-or-typed-dataclass-aggregate, pathlib-FS-method-ban-in-domain). One requirement modified (`adapters` allowed-target fix + docstring consistency).
- `oci-test-contracts`: No spec change — but the strengthened linter is itself tested by the linter's own self-tests added in `test_layering.py`.

## Impact

- **Code**: `tests/architecture/test_layering.py` is extended by ~150 LOC (four new rule checks + supporting AST walking for stdlib imports, banned-stdlib assertions, ports-ABC verification, and pathlib FS-method-call inspection). Self-tests for each rule are added in the same file.
- **CI**: The strengthened test will fail on the current HEAD because (a) `domain/build_tar.py:2` imports `os` (banned) and (b) `ports/cancellation.py:16,30,58` + `ports/pipe_reader.py:21` define concrete classes that fail the ports-ABC-only rule. This is *intentional* — those violations are addressed by the gated wave-2 changes (`oci-build-tar-posixpath`, `oci-cancellation-adapter-relocation`).
- **Workflow**: This change MUST merge before the wave-2 changes; the wave-2 changes go green by satisfying the new rules this change introduces. Sequencing matters: landing this change alone leaves CI red until wave-2; land all three together or land this with `pytest --xfail` markers on the known-red rules that flag pending wave-2 work, removed once wave-2 merges.
- **Dependencies**: None. Pure test-layer change.
- **Risk**: Low. No production code is touched. The xfail/mark strategy preserves CI signal during the brief window between this change and the gated wave-2 changes.