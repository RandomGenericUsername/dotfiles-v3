## Why

The `config-assembler-engine` shared library can only resolve files — its `AssembleConfiguration` use case wraps resolution with parsing, validation, and override-merge, all of which assume file content. The Color Scheme Generator (CSG) needs to resolve a *directory* of templates (priority chain: CLI → env → XDG → package default), but the engine has no concept of directory resolution. CSG hacked around this with a hand-rolled `TemplateDirResolver` that duplicates strategy logic, bypasses the engine's `OsEnvironmentReader`, and introduces mutable state (`set_dir()`). The Wallpaper Effects Generator (WEG) could benefit from directory-of-effects in the future. The engine needs a sibling use case for directories.

## What Changes

- **BREAKING**: Every strategy constructor (`CliPathStrategy`, `EnvPathStrategy`, `DirectoryTraversalStrategy`, `XdgStrategy`, `DefaultFileStrategy`) gains a required keyword-only `kind: ResourceKind` parameter — callers must explicitly declare `FILE` or `DIRECTORY`
- Strategies validate with `is_file()` or `is_dir()` instead of the ambiguous `.exists()`
- New directory strategy subclasses: `CliDirStrategy`, `EnvDirStrategy`, `DirTraversalStrategy`, `XdgDirStrategy`, `DefaultDirStrategy` — each is a thin subclass that presets `kind=DIRECTORY`
- New domain types: `ResourceKind` enum, `kind` field on `ResolvedPath`
- New use case: `AssembleDir` — resolves a directory path via `CompositePathResolver`, lists files matching a glob pattern
- New factory: `create_directory_assembler()`
- CSG: rewrite `TemplateDirResolver` to use engine's directory strategies (delete 4 hand-rolled strategy classes, ~84 lines of custom code)
- CSG: delete `ports/template_dir_resolver.py` — replaced by engine's `CompositePathResolver` directly
- WEG: update ~10 strategy construction sites with `kind=ResourceKind.FILE`
- Engine: update `factories.py` defaults, tests, and docs with explicit `kind`

## Capabilities

### New Capabilities

- `directory-resolution`: Engine support for resolving directories via strategy chains, listing directory contents, and distinguishing file vs directory resources at the type level.

### Modified Capabilities

*(None — no existing spec covers the config-assembler-engine. This is the first.)*

## Impact

- **engine** `config-assembler-engine`: 5
  strategy classes change signature (add `kind`); 5 thin subclasses added; `AssembleDir` use case added; `DirAssemblyResult` domain model added
- **CSG** `color-scheme-generator`: ~109 lines of custom `TemplateDirResolver` deleted; ~5 strategy construction sites updated
- **WEG** `wallpaper-effects-generator`: ~10 strategy construction sites updated; 0 functional changes
- **engine tests**: ~18 strategy constructions updated in `test_strategies.py`; new tests for `AssembleDir`, directory strategies, kind enforcement
- **engine docs**: `README.md` and `PROTOTYPE.md` updated
