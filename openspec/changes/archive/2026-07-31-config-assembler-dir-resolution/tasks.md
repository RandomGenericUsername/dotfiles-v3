## 1. Domain Model Changes (config-assembler-engine)

- [x] 1.1 Add `ResourceKind` enum (`FILE`, `DIRECTORY`) to `domain/models.py`
- [x] 1.2 Add optional `kind: ResourceKind = ResourceKind.FILE` field to `ResolvedPath.__init__`
- [x] 1.3 Add `DirAssemblyResult` dataclass to `domain/models.py`
- [x] 1.4 Export `ResourceKind`, `DirAssemblyResult` from `domain/__init__.py` and `engine/__init__.py`

## 2. Strategy Refactoring (config-assembler-engine)

- [x] 2.1 `CliPathStrategy`: add `*, kind: ResourceKind`; use `is_file()`/`is_dir()` based on kind
- [x] 2.2 `EnvPathStrategy`: add `*, kind: ResourceKind`; use `is_file()`/`is_dir()` based on kind
- [x] 2.3 `DirectoryTraversalStrategy`: add `*, kind: ResourceKind`; use `is_file()`/`is_dir()` based on kind
- [x] 2.4 `XdgStrategy`: add `*, kind: ResourceKind`; use `is_file()`/`is_dir()` based on kind
- [x] 2.5 `DefaultFileStrategy`: add `*, kind: ResourceKind`; use `is_file()`/`is_dir()` based on kind

## 3. Directory Strategy Subclasses (config-assembler-engine)

- [x] 3.1 Add `CliDirStrategy(CliPathStrategy)` — presets `kind=DIRECTORY`, no extra params
- [x] 3.2 Add `EnvDirStrategy(EnvPathStrategy)` — presets `kind=DIRECTORY`, default `var="CONFIG_DIR_PATH"`
- [x] 3.3 Add `DirTraversalStrategy(DirectoryTraversalStrategy)` — presets `kind=DIRECTORY`
- [x] 3.4 Add `XdgDirStrategy(XdgStrategy)` — presets `kind=DIRECTORY`
- [x] 3.5 Add `DefaultDirStrategy(DefaultFileStrategy)` — presets `kind=DIRECTORY`

## 4. New Use Case: AssembleDir (config-assembler-engine)

- [x] 4.1 Implement `AssembleDir` class in `application/use_cases.py`
- [x] 4.2 Implement `create_directory_assembler()` factory in `adapters/factories.py`
- [x] 4.3 Export `AssembleDir`, `create_directory_assembler` from `__init__.py`
- [x] 4.4 Add `NotADirectoryError` handling to `errors.py`

## 5. Update Engine's Own Callers

- [x] 5.1 Update `_DEFAULT_STRATEGIES` in `factories.py` with `kind=ResourceKind.FILE`
- [x] 5.2 Update unit tests in `test_strategies.py` — add kind to all 18 constructions
- [x] 5.3 Update `test_full_pipeline.py` — add kind to 5 strategy constructions
- [x] 5.4 Add unit tests for directory strategy subclasses
- [x] 5.5 Add unit tests for `AssembleDir` use case
- [x] 5.6 Add unit test for kind enforcement (FILE rejects DIR, DIR rejects FILE)

## 6. Update WEG Callers

- [x] 6.1 `assembled_config_resolver.py`: add `kind=ResourceKind.FILE` to all 5 strategy constructions
- [x] 6.2 `yaml_effect_loader.py`: add `kind=ResourceKind.FILE` to all 5 strategy constructions
- [x] 6.3 Update imports in both files if needed
- [x] 6.4 Run WEG test suite to verify no regressions

## 7. Update CSG Callers

- [x] 7.1 `settings/config_resolver.py`: add `kind=ResourceKind.FILE` to all 5 strategy constructions
- [x] 7.2 `yaml_backend_catalog_loader.py`: add `kind=ResourceKind.FILE` to all 5 strategy constructions
- [x] 7.3 Run CSG test suite to verify no regressions

## 8. Rewrite CSG TemplateDirResolver

- [x] 8.1 Delete hand-rolled `_EnvDirStrategy`, `_XdgDirStrategy`, `_DefaultDirStrategy`, `_SettingsDirStrategy` from `template_dir_resolver.py`
- [x] 8.2 Rewrite `TemplateDirResolver` using `CliDirStrategy`, `EnvdDirStrategy`, `XdgDirStrategy`, `DefaultDirStrategy` from engine
- [x] 8.3 Update `ports/template_dir_resolver.py` or delete if no longer needed
- [x] 8.4 Update tests in `test_template_dir_resolver.py`
- [x] 8.5 Run full CSG test suite

## 9. Documentation

- [x] 9.1 Update engine `README.md` — add `kind` to all strategy construction examples
- [x] 9.2 Update engine `PROTOTYPE.md` — add `kind` to all examples
- [x] 9.3 Update CSG `ARCHITECTURE_PLAN.md` — reflect new TemplateDirResolver implementation
- [x] 9.4 Update WEG `ARCHITECTURE_PLAN.md` — reflect `kind` parameter
