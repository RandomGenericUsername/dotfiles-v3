# Implementation Handoff Notes — `csg/weg install` container-image fix

**Commit:** `e18ecfe` on `master` ("fix: csg/weg install builds container images from uv-tool installs"), 18 files, +830/−48. **Branch:** `master`. **Environment:** Linux, podman 6.0.1 (rootless), uv, python 3.14. Monorepo at `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`.

---

## 1. Problem (what was broken)

`csg install` and `weg install` build container images whose build **context is the monorepo source tree** (`src/cli-tools/...`, `src/shared/...`). Both CLIs located that source tree purely by walking the filesystem from `__file__`/`importlib.resources` — which only works when running from a **source checkout**. When the CLI is installed as a `uv tool` (`uv tool install 'src/cli-tools/color-scheme-generator'`, exactly what the ansible `cli_tools` role does), the package files resolve into the tool venv (`~/.local/share/uv/tools/.../site-packages/...`), the walk finds nothing, and:

- **CSG** (`install_cmd.py`): `_find_project_root()` returned `None` → the **base image build was silently skipped**; backend builds ran with the Dockerfile's own dir as context (site-packages) → `FROM ${BASE_IMAGE}` cache-hit the stale base → reported `{"status":"built"}` while doing nothing. On a fresh machine (no images) `FROM csg-base-podman:latest` resolved nothing → hard failure. This is the "silent no-op" defect.
- **WEG** (`install.py:54`): `Path(__file__).resolve().parent*7` (hardcoded 7 parents) lands on the repo root from a checkout but somewhere wrong from an installed tool → built against a wrong/missing directory (loud failure, wrong behavior).

Secondary facts that mattered:
- `Dockerfile.base` (CSG) used `COPY cli-tools/...` / `COPY shared/...` → context must be **`<repo>/src`**. `Dockerfile.imagemagick` (WEG) used `COPY src/shared/...` → context must be **`<repo>` root**. Two divergent conventions.
- CSG backend Dockerfiles (`pywal/custom/wallust`) have **no `COPY`** — only `FROM ${BASE_IMAGE}` + apt/pip — so they can never refresh the csg code; they're stale iff the base is stale.
- The `default_palette` role ran `csg generate` in **local** mode (no container env) and no role ran `csg install` at all — the container-mode product decision (2026-08-12) was not wired into provisioning.
- ITR has no container mode — out of scope.

## 2. Key discovery that shaped the fix

`uv` (and `pip`) write **PEP 610 `direct_url.json`** into the installed package's `.dist-info`. For a local-path install it records the original source dir, e.g. `{"url":"file:///.../dotfiles-repo-v3/src/cli-tools/color-scheme-generator","dir_info":{}}` (editable installs add `"editable":true`, same `url`). So an installed CLI **can** rediscover its source repo. This refuted the original framing ("no link back to source exists") and enabled a thin-launcher fix with no source shipped in the wheel.

## 3. Architecture of the fix

### Layer 1 — shared source-root locator (new, in `oci-runtime`)

**Files:**
- `src/shared/oci-runtime/src/oci_runtime/source_locator.py` (NEW)
- `src/shared/oci-runtime/src/oci_runtime/domain/exceptions.py` (added `SourceRootNotFoundError`)
- `src/shared/oci-runtime/src/oci_runtime/__init__.py` (exported `SourceRoot`, `resolve_source_root`, `SourceRootNotFoundError`)
- `src/shared/oci-runtime/tests/unit/domain/test_source_locator.py` (NEW, 16 tests)

**`resolve_source_root(*, package, override, env_var, env=None)`** priority chain (first match wins):
1. `override` (CLI `--source-root` Path)
2. `env_var` (e.g. `CSG_SOURCE_ROOT`, read from `os.environ` unless `env` injected)
3. PEP 610 `direct_url.json` via `importlib.metadata.distribution(package).read_text("direct_url.json")` → parse `url`, accept `file://` scheme only, `url2pathname` → package dir
4. legacy `importlib.resources.files(package)` walk (source checkout / editable)

Each candidate dir is validated by `_repo_root_from_candidate()`: walk up to the first ancestor containing **both** `src/cli-tools` and `src/shared` directories (the monorepo marker). Returns `SourceRoot(root=Path, source="override"|"env"|"direct_url"|"package")`. If nothing resolves → `SourceRootNotFoundError` (subclass of `OciError`) with an actionable message ("reinstall from a source checkout ... or set <ENV>=").

Notes:
- `_REPO_MARKER_DIRS = (("src","cli-tools"), ("src","shared"))` and check via `(parent.joinpath(*part)).is_dir()` — beware `parent / tuple` is a TypeError.
- `_direct_url_package_dir` uses `urlparse`; only `scheme == "file"` accepted; guards `PackageNotFoundError`, bad JSON, missing file → `None`.
- The `env` param exists so tests don't mutate real environment.
- Bad override does NOT hard-fail — it falls through to the next candidate (documented intent).

### Layer 2 — CSG install

**Files:**
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/install_cmd.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/options.py` (new `SOURCE_ROOT_OPT`)
- `src/cli-tools/color-scheme-generator/tests/unit/cli/test_install_command.py` (+3 tests)

Changes:
- Deleted `_find_project_root(docker_dir)` entirely.
- Added `source_root: Path | None = SOURCE_ROOT_OPT` (module-level typer Option, `envvar="CSG_SOURCE_ROOT"`, `exists=True`). `_SOURCE_ROOT_ENV = "CSG_SOURCE_ROOT"` kept for the resolver call.
- Before building (and only when NOT `--dry-run`): `project_root = resolve_source_root(package="color_scheme_generator", override=source_root, env_var=_SOURCE_ROOT_ENV).root`; `SourceRootNotFoundError` → `raise ColorSchemeError(str(exc))`.
- Base build guard changed from `if not dry_run and project_root is not None:` → `if not dry_run:` with a `FileNotFoundError` if `Dockerfile.base` is missing. **Base is always built now**; `context_path=project_root` always set (both base and backend).
- `--dry-run` never resolves the source root (introspection without needing a repo).

### Layer 3 — WEG install

**Files:**
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/install.py`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/options.py` (new `SOURCE_ROOT_OPT`)
- `src/cli-tools/wallpaper-effects-generator/tests/test_cli.py` (+2 tests)

Changes:
- Deleted the hardcoded `repo_root = Path(__file__).resolve().parent.parent...` (7 parents).
- `install_command(...)` gained trailing kwarg `source_root: str | None = None`; resolves via `resolve_source_root(package="wallpaper_effects_generator", override=Path(source_root) if source_root else None, env_var="WEG_SOURCE_ROOT")`; on `SourceRootNotFoundError` → `raise WallpaperEffectsError(str(exc))`.
- `main.py` `install` command: added `source_root: Path | None = SOURCE_ROOT_OPT` and wrapped `install_command(...)` in `try/except WallpaperEffectsError → raise typer.BadParameter(str(exc))` so the failure is a clean `Error:` message + non-zero exit (WEG's other commands use this pattern; the un-caught exception path produced a bare traceback).
- `SOURCE_ROOT_OPT` in WEG `options.py` uses `envvar="WEG_SOURCE_ROOT"`.

### Layer 4 — Dockerfile context normalization

**File:** `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base`
- `COPY cli-tools/color-scheme-generator` → `COPY src/cli-tools/color-scheme-generator`
- `COPY shared/config-assembler-engine` → `COPY src/shared/config-assembler-engine`, same for `oci-runtime`, `cli-output`.
- Result: **both** CLIs now use context = **repo root** (WEG's `Dockerfile.imagemagick` already used `src/...`). One convention, so the resolver returns the same root for both. Requires a one-time rebuild of existing `csg-base-podman` images.

### Layer 5 — Provisioning wiring (folded into the same fix, NOT deferred)

**Files:**
- `src/provisioning/ansible/roles/cli_tools/vars/main.yml` — added `cli_tools_container_engine: podman` and a documented `cli_tools_image_builds` list (currently only `csg`; weg intentionally absent because no provisioning role runs it in container mode yet).
- `src/provisioning/ansible/roles/cli_tools/tasks/main.yml` — appended a `Build csg container images` task:
  ```yaml
  ansible.builtin.command:
    argv: [csg, install, --container-engine, "{{ cli_tools_container_engine }}",
           --source-root, "{{ cli_tools_repo_root }}"]
  environment:
    PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"
  when: not ansible_check_mode
  ```
  **No `creates:`** (image existence ≠ freshness; stale images must rebuild; mirrors the default_palette generate task's accepted-by-design "changed every apply" semantics). Check-mode gated (command module executes under `--check`). `cli_tools_repo_root` (`{{ playbook_dir }}/../../../..`) is reused as `--source-root` — deterministic on the provisioning path, no PEP 610 reliance.
- `src/provisioning/ansible/roles/default_palette/vars/main.yml` — added `default_palette_container_engine: podman` (role-local, mirror-and-adapt).
- `src/provisioning/ansible/roles/default_palette/tasks/main.yml` — generate task `environment:` now sets `COLORSCHEME__RUNTIME__MODE: "container"` and `COLORSCHEME__CONTAINER__ENGINE: "{{ default_palette_container_engine }}"` (kept OUTPUT_DIRECTORY/OVERWRITE + PATH); updated `Ensure csg is available` fail_msg and header comments to document the image-build precondition and container-mode decision.

### Layer 6 — Tests

- **oci-runtime:** `test_source_locator.py` — override wins; override-as-package-dir; env var; direct_url fallback; package-walk fallback; nothing-resolves raises (message mentions env var); bad override falls back to direct_url; direct_url parsing (file://, editable, non-file, missing pkg, bad JSON); `_repo_root_from_candidate` (root, package dir, deep-nested, no marker).
- **CSG:** `test_install_fails_loudly_when_no_source_root` (monkeypatch `install_cmd.resolve_source_root` to raise → exit 1, no `"status":"built"`, message present in stdout+stderr); `test_install_uses_source_root_override`; `test_install_uses_source_root_env_var` (assert every build `context.context_path == root`); `test_install_help_shows_expected_usage` extended to assert `--source-root` in help.
- **WEG:** `test_install_command_uses_source_root_override` (assert `context.context_path == repo`); `test_install_command_fails_loudly_when_no_source_root` (assert `source repo` in output, no builds recorded).
- **Provisioning:** `test_cli_tools_role.py` — new `TestCliToolsImageBuildTasks` (argv-form `csg install` task exists; passes `--container-engine {{ cli_tools_container_engine }}`; passes `--source-root {{ cli_tools_repo_root }}`; gated `not ansible_check_mode`; **no `creates:`**; no `become`) + vars tests (`cli_tools_container_engine == "podman"`, `cli_tools_image_builds` contains only `csg`). New helpers: `_argv_of()` returns `list[str] | None` for argv-form command tasks, `_image_build_tasks()` matches `argv[:2] == ["csg","install"]` (prefix, NOT `==`). `test_default_palette_role.py` — env contract now requires `COLORSCHEME__RUNTIME__MODE == "container"` and `COLORSCHEME__CONTAINER__ENGINE`; vars required-keys + podman default test.

### Layer 7 — Docs
- `csg/weg install --help` now shows `--source-root ... [env var: CSG_SOURCE_ROOT / WEG_SOURCE_ROOT]`.
- Comment blocks in `cli_tools`/`default_palette` tasks document the image-build design, the no-`creates:` freshness rationale, and the container-mode env contract (so the Story 2.12 bootstrap aggregator author orders `cli_tools → assets → default_palette`).

## 4. API impact (verified — additive only)

- **CLI surface:** `--source-root` flag added to `csg install` and `weg install` (optional). No flags removed/retyped. `csg generate`/`weg batch` untouched.
- **Env:** new `CSG_SOURCE_ROOT` / `WEG_SOURCE_ROOT` (single-underscore family, mirrors `*_CONFIG_FILE_PATH`; NOT the `COLORSCHEME__SECTION__KEY` nesting scheme). `COLORSCHEME__RUNTIME__MODE`/`COLORSCHEME__CONTAINER__ENGINE` were already supported resolver keys — provisioning only starts *using* them.
- **Image names:** unchanged (`csg-base-podman:latest`, `csg-pywal-podman:latest`, `weg-podman:latest`). `engine_qualified_image`, `BuildContext` untouched.
- **Output JSON:** `install` still emits `[{"backend","image","status"}]`; no new status values (content-hash "fresh"/"skipped" was intentionally deferred).
- **Behavior break (the bug itself):** installed-tool `csg install` with no resolvable source now exits 1 with a clear message instead of silently reporting `{"status":"built"}`. No consumer relied on the old silent path (verified: no provisioning task called `csg install` before this change).
- **`install_command(...)` Python signature:** trailing kwarg `source_root=None` added; only caller is `main.py`.

## 5. How to verify (all run on this machine, all passed)

```
# provisioning-path install, from scratch (removed images first)
podman rmi -f csg-base-podman:latest csg-pywal-podman:latest 2>/dev/null; true
uv tool install --force --refresh 'src/cli-tools/color-scheme-generator'
~/.local/bin/csg install --container-engine podman --source-root <repo>   # base + 3 backends, exit 0
podman image history csg-base-podman:latest | rg 'COPY'   # recent src/... layers (fresh source baked in)

# container-mode generate (exact default_palette env)
COLORSCHEME__RUNTIME__MODE=container COLORSCHEME__CONTAINER__ENGINE=podman \
COLORSCHEME__OUTPUT__DIRECTORY=/tmp/csg-out COLORSCHEME__OUTPUT__OVERWRITE=true \
~/.local/bin/csg generate <some.png> -f conf -f css -f yaml   # -> colors.conf/.css/.yaml, exit 0

# direct_url fallback (no flag): ~/.local/bin/csg install --container-engine podman --backend pywal  # 3s cache-hit, exit 0
# env escape hatch: CSG_SOURCE_ROOT=<repo> csg install --container-engine podman --backend pywal
# loud failure (resolver): break installed dist-info direct_url.json -> exit 1 "Cannot locate the 'color_scheme_generator' source repo..."
# loud failure (CLI): csg install --source-root /does/not/exist -> exit 2 "Directory ... does not exist."

# WEG symmetry
uv tool install --force --refresh 'src/cli-tools/wallpaper-effects-generator'
~/.local/bin/weg install --container-engine podman     # rebuilds weg-podman:latest fresh
~/.local/bin/weg install --source-root /does/not/exist # exit 2, clear error

# test suites (all green)
cd src/shared/oci-runtime && uv run pytest tests/unit -q            # 882 passed, 1 skipped
cd src/cli-tools/color-scheme-generator && uv run pytest tests/unit -q   # 555 passed
cd src/cli-tools/wallpaper-effects-generator && uv run pytest tests -q    # 324 passed
cd src/provisioning && uv run pytest tests/unit -q                        # 277 passed
# ruff: no NEW lint debt (remaining B008 errors are pre-existing; source-root moved to options.py to avoid adding more)
```

## 6. Gotchas / things the next agent must know

- **uv caches path-install builds.** `uv tool install --force 'src/cli-tools/color-scheme-generator'` may install a STALE wheel if the package source changed but version/pyproject didn't (observed: installed files kept old mtime, `--source-root` missing). Use `uv tool install --force --refresh` to force a rebuild. (In provisioning this doesn't bite — fresh machine.)
- **`_image_build_tasks()` matching** in the provisioning test uses prefix match `argv[:2] == ["csg","install"]` — `==` on the full list is a bug (argv has more elements).
- **The `default_palette` generate task and the `cli_tools` build task both report `changed` on every apply** — accepted by design (idempotency = no state drift; podman cache makes re-builds ~3s when fresh). Do NOT "fix" with a `creates:` existence gate — that reintroduces the staleness bug.
- **Rootless podman, no `become` anywhere** — images land in the user's storage; PATH for the build task keeps the system component (`{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}`) so `podman` resolves.
- Two `_bmad-output/implementation-artifacts/*.md` files were already dirty before this commit and were **left unstaged** — don't assume they're part of this work.
- The `uv tool install` of `csg` in this session ended pointing at the repo via `--refresh`; `direct_url.json` currently points at the repo (restored after the loud-failure test).

## 7. Deliberately deferred (explicit follow-ups, non-blocking)

1. Content-hash labels (`LABEL csg.source.sha256=...`) for truthful `changed`/freshness reporting — optional hardening; correctness already achieved via correct context + podman's content-addressed cache.
2. WEG provisioning container-mode task — deferred until a role runs `weg batch`/`weg process` in container mode (`assets` only uses local `weg dump-effects`). The WEG **CLI** fix is complete.
3. `bootstrap.yaml` aggregator (Story 2.12) — must set `gather_facts: true` and order `cli_tools → assets → default_palette`.
4. Orphan/dangling image cleanup (old `csgcolor-scheme-*`, `color-scheme-base`, `localhost/weg`, `<none>`) — operator runs `csg uninstall`/`weg uninstall` + `podman image prune`.

## 8. Decision recorded (product)

**Source repo is REQUIRED on the machine at `csg/weg install` time**; scenarios where it's missing (repo deleted after install, PyPI/sdist install with no `file://` direct_url) **fail loudly** with an actionable message. Explicitly rejected: bundling the source tree into the wheel (3× wheel size, version-skew risk, violates thin-launcher constraint).
