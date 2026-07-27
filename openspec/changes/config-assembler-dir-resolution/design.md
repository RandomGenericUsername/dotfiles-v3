## Context

The `config-assembler-engine` is a strictly hexagonal shared library providing a config resolution pipeline: resolve path → parse → validate → apply overrides → re-validate. All 5 strategies use `.exists()`, which matches both files and directories — but the only use case (`AssembleConfiguration`) assumes a parseable file for its downstream pipeline. CSG needs directory resolution for its templates directory but had to hand-roll 4 strategy classes outside the engine, duplicating logic and bypassing the engine's `OsEnvironmentReader`.

The change introduces directory as a first-class resource kind alongside file, at both the domain model and use-case layers.

## Goals / Non-Goals

**Goals:**
- Add `ResourceKind` to the domain model (`FILE` / `DIRECTORY`) and a `kind` field to `ResolvedPath`
- Make every strategy explicitly declare which kind it resolves (required `kind` parameter)
- Add thin directory subclasses for every strategy (`DefaultDirStrategy`, `XdgDirStrategy`, etc.)
- Create `AssembleDir` use case: resolve directory → list files matching a glob
- Add `create_directory_assembler()` factory
- Rewrite CSG's `TemplateDirResolver` to use engine directory strategies
- Update every existing strategy construction site across WEG, CSG, engine tests, and docs

**Non-Goals:**
- No changes to the `AssembleConfiguration` use case pipeline (parse/validate/override/merge is file-only by design)
- No directory-of-YAML-effects capability for WEG (out of scope; enabled for future by the directory strategies)
- No config file parsing within directories (e.g., parsing all `.yaml` files in a directory)
- No performance optimization for large directories

## Decisions

### D1: `kind` is keyword-only on every strategy

All strategies gain `*, kind: ResourceKind` as a keyword-only parameter. This avoids Python's "non-default after default" constraint (since `EnvPathStrategy` has a default `var` and `DirectoryTraversalStrategy` has a default `max_levels`), and makes the intent explicit at every construction site.

**Alternatives considered:**
- *Pre-`kind` as first positional param* → awkward ordering for strategies with other required params
- *Pre-`kind` as last positional param* → illegal after optional params in Python
- *Default value of `FILE`* → rejected for explicitness; every caller must declare intent

### D2: `is_file()` / `is_dir()` replaces `.exists()`

Strategies now enforce the declared resource kind at resolution time. A `DefaultFileStrategy(path=some_dir, kind=ResourceKind.FILE)` returns `None` instead of silently accepting the directory. This catches misconfiguration early.

**Risk**: existing strategies were lenient (accepted anything existing). The change is strictly more restrictive, which could surface latent bugs.

### D3: Directory subclasses are thin inheritance, not composition

```python
class DefaultDirStrategy(DefaultFileStrategy):
    def __init__(self, path: Path):
        super().__init__(path, kind=ResourceKind.DIRECTORY)
```

Each subclass fixes `kind=DIRECTORY` and provides an alias with no surprises. The alternative — parameterized factory functions — was rejected because subclasses are discoverable via `isinstance()` and IDE autocompletion.

### D4: `AssembleDir` is a standalone use case, not an `AssembleConfiguration` mode

```python
class AssembleDir:
    def execute(self, policy, *, explicit_path=None):
        resolved = self._resolver.resolve(policy, explicit_path)
        if not resolved.path.is_dir():
            raise NotADirectoryError(...)
        files = sorted(resolved.path.glob(self._file_pattern))
        return DirAssemblyResult(directory=..., source=..., files=...)
```

No shared base class with `AssembleConfiguration` — they share `CompositePathResolver` and strategies, but the pipelines diverge immediately after resolution. A shared abstract base would add abstraction without reuse.

### D5: `ResolvedPath.kind` retains a default of `ResourceKind.FILE`

Backward compatibility: existing code inspecting `ResolvedPath` objects doesn't need updating. New code should read `kind` explicitly.

## Risks / Trade-offs

- **[Breaking change] Every strategy caller must update 48 construction sites across 3 projects.** Mitigation: the change is mechanical (`kind=ResourceKind.FILE` appended), caught at compile time by the type checker, and every site is documented in tasks.md.
- **[Coercion risk] `DirectoryTraversalStrategy` with `kind=DIRECTORY` searches for a directory by name in CWD/parents.** This differs from the original behavior which searched for a filename. Callers using this strategy for directories (like template dirs via CWD traversal) must ensure the directory name, not file name, is passed. Mitigated by dedicated `DirTraversalStrategy` subclass with explicit `dirname` parameter.
- **[Accidental misuse] `DefaultFileStrategy` with a directory path and `kind=FILE` returns `None` instead of error.** This could cause silent fallthrough to the next strategy or raise `PathResolutionError`. Mitigation: explicitly documented in strategy docstrings.
- **[No XDG fallback for templates dir in CSG] XDG subdir changed from `color-scheme-generator` to `color-scheme`.** Mitigation: confirmed via the `TemplateDirResolver` code that this was already the XDG path used.
