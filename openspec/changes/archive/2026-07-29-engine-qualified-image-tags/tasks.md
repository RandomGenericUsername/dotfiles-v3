## 1. Shared naming helper (oci-runtime)

- [x] 1.1 Create `src/shared/oci-runtime/src/oci_runtime/domain/naming.py` with `engine_qualified_image(name, engine, tag, registry=None) -> str`
- [x] 1.2 Export `engine_qualified_image` from `src/shared/oci-runtime/src/oci_runtime/__init__.py` (add to `__all__`)
- [x] 1.3 Add unit tests under `src/shared/oci-runtime/tests/` covering: no registry, with registry, docker/podman variants, empty engine raises ValueError
- [x] 1.4 Run `pytest` on oci-runtime to confirm passing

## 2. WEG — wire helper into all three image-name sites

- [x] 2.1 Replace `cli/install.py` `_build_image_name` (lines 72-79) with `engine_qualified_image(cs.image_name, cs.engine, cs.image_tag, cs.image_registry)`
- [x] 2.2 Replace `cli/uninstall.py` `_build_image_name` (lines 51-58) with same call
- [x] 2.3 Replace `adapters/container_processor.py` `_resolve_image` (lines 250-257) with `engine_qualified_image(cs.image_name, cs.engine, cs.image_tag, cs.image_registry)`
- [x] 2.4 Verify no signature changes needed — all callers pass `settings.container` which has `.engine` populated by existing override plumbing

## 3. CSG — normalize naming and wire helper

- [x] 3.1 Update `cli/_helpers.py` `build_image_name(settings, backend, engine)` to produce `f"{prefix}-color-scheme-{backend.image_suffix}"` then call `engine_qualified_image(base, engine, tag)`
- [x] 3.2 In `cli/install_cmd.py` `install()`: capture `engine_value = engine.value` before line 52 shadow. Use it for base image (`engine_qualified_image(f"{prefix}-color-scheme-base", engine_value, tag)`) and pass it to `build_image_name(settings, b, engine_value)` at line 78
- [x] 3.3 In `cli/uninstall_cmd.py` `uninstall()`: resolve `engine_value` same way, pass to `build_image_name(settings, b, engine_value)` at line 41
- [x] 3.4 Update `adapters/container_processor.py` `_select_image` to use `engine_qualified_image(f"{prefix}-color-scheme-{backend_value}", settings.container.engine, tag)`
- [x] 3.5 Update `adapters/dry_run_processor.py` `_build_image_name` to use `engine_qualified_image(..., settings.container.engine, tag)`
- [x] 3.6 In `cli/main.py` `generate()` body (~line 249): pass `engine_obj.value` into the container processor/processor construction so the runtime path uses the same engine value
- [x] 3.7 Check `main.py` `install`/`uninstall` leaf registration — the import from `install_cmd` / `uninstall_cmd` should pass through `--container-engine` as before (already working, verified in investigation)

## 4. CSG — backend Dockerfiles use ARG BASE_IMAGE

- [x] 4.1 Edit `Dockerfile.custom` line 1: `FROM color-scheme-base:latest` → `ARG BASE_IMAGE=csg-color-scheme-base-docker:latest` + `FROM ${BASE_IMAGE}`
- [x] 4.2 Edit `Dockerfile.pywal` line 1: same change
- [x] 4.3 Edit `Dockerfile.wallust` line 1: same change
- [x] 4.4 In `cli/install_cmd.py` backend loop (line 91-96): add `build_args={"BASE_IMAGE": base_image}` to `BuildContext`; reorder `kwargs` so `build_args` is set after `context_path` (not before, to avoid mutation-by-immutability issues)
- [x] 4.5 Verify `Dockerfile.base` is unchanged (FROM `python:3.14-slim`)

## 5. Update tests

### 5.1 Shared layer tests
- [x] 5.1.1 Create `src/shared/oci-runtime/tests/unit/domain/test_naming.py` — cover happy paths, edge cases (empty engine, registry slashes, tag params)

### 5.2 WEG tests
- [x] 5.2.1 `tests/test_cli.py`: update `test_install_command` mock assertions (`ghcr.io/weg-managed:latest` → `ghcr.io/weg-managed-docker:latest`); add assertions that `build`/`remove`/`exists` are called with engine-qualified names
- [x] 5.2.2 `tests/test_cli.py`: update `test_uninstall_command` same pattern
- [x] 5.2.3 Run WEG tests — `pytest src/cli-tools/wallpaper-effects-generator/tests/`

### 5.3 CSG tests
- [x] 5.3.1 `tests/unit/cli/test_install_command.py`: `test_install_engine_podman` — replace `call_count == 4` with explicit `call_args_list` assertions on `build_image` for base + 3 backends, including `--build-arg BASE_IMAGE=...` check on backend `BuildContext`
- [x] 5.3.2 `tests/unit/cli/test_install_command.py`: add `test_install_engine_docker` variant with docker assertions
- [x] 5.3.3 `tests/unit/cli/test_install_command.py` and `tests/unit/cli/test_uninstall_command.py`: update `image="csg-color-scheme-custom:latest"` exception literals → `csg-color-scheme-custom-docker:latest`
- [x] 5.3.4 `tests/unit/adapters/test_image_lifecycle.py`: update pass-through test strings from `"test-image:latest"` → `"test-image-docker:latest"` (the adapter is generic, but strings must reflect engine-qualified convention)
- [x] 5.3.5 `tests/test_user_journey.sh`: check for any hardcoded image-name references; update to new names
- [x] 5.3.6 Run CSG tests — `pytest src/cli-tools/color-scheme-generator/tests/`

## 6. Lint and typecheck

- [x] 6.1 Run `ruff check` on changed packages (oci-runtime, both cli-tools)
- [x] 6.2 Run `ruff format --check` (or reformat) on changed files
- [x] 6.3 Run `mypy` on changed packages (skipped — mypy not available in environment; ruff + pytest pass)

## 7. Manual verification (requires container runtime)

- [ ] 7.1 `weg install --container-engine podman --dump-config --dump-effects` — confirm output shows `weg-podman:latest`
- [ ] 7.2 `weg install --container-engine docker` — confirm output shows `weg-docker:latest`
- [ ] 7.3 `csg install --container-engine podman` — confirm output shows `csg-color-scheme-*-podman:latest`
- [ ] 7.4 `csg install --container-engine docker` — confirm output shows `csg-color-scheme-*-docker:latest`

## 8. Update spec documentation

- [x] 8.1 Create `openspec/changes/engine-qualified-image-tags/specs/container-image-engine-tagging/spec.md` with ADDED requirements
- [x] 8.2 Create `openspec/changes/engine-qualified-image-tags/specs/csg-image-naming/spec.md` with MODIFIED requirements for the naming normalization
