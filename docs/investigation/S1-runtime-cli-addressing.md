# S1 — How `src/runtime` addresses and connects to `csg` / `weg` / `itr`

> **Historical (2026-10-22):** evidence-only spike from before the assets/engine split; the
> `dotfiles/assets/icon-templates` path it records is now the pinned `dotfiles-assets` corpus.

**Type:** evidence-only spike (no recommendations).
**Scope:** `src/runtime` in worktree `/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit`.
**Branch:** `ticket/clirsplit-investigate-and-spine`.
**Commit at investigation time:** `fb94b64e87e992b87cd6b1d65d901e3ae45def34`.

**Path convention.** In the prose, `csg_adapter.py` / `weg_adapter.py` / `itr_adapter.py`
abbreviate `src/runtime/src/runtime/adapters/<name>.py`; `tests/...` abbreviates
`src/runtime/tests/...`; `hashing.py`, `env.py`, `cache.py`, `seeder.py`, etc. abbreviate the
same `adapters/` directory. Every Verify command below spells the full repository-relative
path.

Every claim below is followed by an `Evidence:` line containing either a command + observed
output, or a file path + line range that was read. Claims that could not be established are
listed under **Open questions** and marked `MISSING`.

---

## 0. Load-bearing facts (condensed)

| # | Fact | Evidence |
|---|---|---|
| 1 | The runtime never imports a CLI Python package; it only invokes the installed consoles via `subprocess.run`. | `rg -n '^(from\|import) (color_scheme_generator\|wallpaper_effects_generator\|icon_templates_renderer\|config_assembler_engine\|oci_runtime)' src/runtime --glob '*.py'` → exit 1, no matches; `src/runtime/src/runtime/adapters/csg_adapter.py:304`, `weg_adapter.py:364`, `itr_adapter.py:423` |
| 2 | The binary is a literal name (`csg` / `weg` / `itr`) unless the constructor is given an explicit `*_bin` path; invocation does not call `command -v` or `shutil.which`. | `csg_adapter.py:279-280`, `weg_adapter.py:353-354`, `itr_adapter.py:411-412`; `grep -rn "command -v" src/runtime/src` → exit 1; `shutil.which` appears only in `is_available()` (`csg_adapter.py:155-156`, `weg_adapter.py:220-221`, `itr_adapter.py:144-145`) |
| 3 | Exact argv: `csg generate <wallpaper> --format yaml --format conf --format gtk.css --format adw.css --format sequences --format rasi --format kitty --format btop.theme`; `weg batch all -- <wallpaper>`; `itr render [<mappings-file>]`. | `csg_adapter.py:280-300`; `weg_adapter.py:354-360`; `itr_adapter.py:412-419`; recording-probe log (section 1.3) |
| 4 | No `cwd=` and no stdin/input are supplied; the child inherits the caller's cwd and fd 0. Observed cwd was the runtime test cwd and fd 0 was `/dev/null`. | `grep -rn "cwd=\|stdin=\|input=" src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py` → exit 1; probe log: `"cwd": ".../src/runtime"`, `"stdin_fd0": "/dev/null"` |
| 5 | The subprocess env is an allowlist, not `dict(os.environ)`: `PATH`, `HOME`, `XDG_*`, locale/TLS/proxy vars, plus literal `COLORSCHEME__*`, `WALLPAPER__*`, `ICON_RENDERER__*` overrides; secrets are blocked. | `src/runtime/src/runtime/adapters/env.py:22-52`, `:64-70`, `:73-87`; probe shows `MY_SECRET_TOKEN` and single-underscore config vars absent (section 3.3) |
| 6 | The runtime does **not** parse CLI stdout/stderr as JSON or through `cli_output`; it checks exit status, then hashes artifact files on disk. Stdout/stderr are used only in truncated error messages. | `csg_adapter.py:331-350`; `weg_adapter.py:409-427`; `itr_adapter.py:467-485`; `grep -rn "cli_output" src/runtime/src/runtime/adapters src/runtime/src/runtime/application` → only a docstring mention; `cli_output` is imported only in `src/runtime/src/runtime/cli/main.py:20-22` |
| 7 | Every adapter computes an entry hash from inputs and rejects an `output_dir` whose basename differs before spawning the CLI. | `csg_adapter.py:242-244` + `_validate_output_dir` `:90-114`; `weg_adapter.py:318-320` + `:148-174`; `itr_adapter.py:316-318` + `:67-90` |
| 8 | The CLIs write into a per-run staging work dir (`<state_root>/cache/.staging-<pid>-<uuid>/<entry-hash>`) supplied by the runtime; the runtime later writes `meta.json` and atomically renames the staging dir into `cache/<layer>/<entry-hash>`. | `cache.py:188-196`, `:517-604`; `derive.py:717-719`, `:775-777`, `:1054-1057`; `seeder.py:288-451`, `:546-570` |
| 9 | No version pin or runtime capability probe exists. The only `csg` capability probe found is test-only (`csg dump-templates`). | `grep -rn -- "--version" src/runtime/src` → exit 1; `grep -rn --exclude-dir=__pycache__ "is_available" src/runtime/src src/runtime/tests` → methods/tests only, no production caller; `src/runtime/tests/integration/test_csg_adapter_integration.py:29-51`, `:90-99` |
| 10 | All three real binaries were exercised: `csg` XPASS, `weg` PASS, `itr` integration skipped by its own setup guard but a separate real-`itr` probe passed. | `cd src/runtime && uv run pytest tests/integration/test_{csg,itr,weg}_adapter_integration.py -v` → `1 passed, 1 skipped, 1 xpassed`; real-ITR probe → `OK ee4371bf... ['battery-0.svg']` |

---

## 1. Question 1 — adapter invocation contract

### 1.1 Adapter ↔ port map

**Finding.** There is one adapter class per CLI, each implementing a runtime port:

- `CsgAdapter(IColorSchemeGenerator)` — `csg_adapter.py:117`
- `WegAdapter(IEffectsGenerator)` — `weg_adapter.py:177`
- `ItrAdapter(IIconRenderer)` — `itr_adapter.py:93`

Evidence: headers above; ports are `src/runtime/src/runtime/ports/color_scheme_generator.py`,
`effects_generator.py`, `icon_renderer.py` (each declares only the operation, no `is_available`).

**Finding.** No runtime source imports the CLI packages. The coupling is subprocess-only.

Evidence:

```
$ rg -n '^(from|import) (color_scheme_generator|wallpaper_effects_generator|icon_templates_renderer|config_assembler_engine|oci_runtime)' src/runtime --glob '*.py'
EXIT=1   # no output
```

### 1.2 Binary name / path resolution

**Finding.** The constructor accepts `csg_bin: str | None`, `weg_bin: str | None`,
`itr_bin: str | None`. `None` means the literal name is used as `argv[0]`, so resolution is
delegated to the OS/PATH at `exec` time.

Evidence:

- `csg_adapter.py:125-137` (constructor), `:279-280` (`bin_name = self._csg_bin or "csg"`)
- `weg_adapter.py:190-204`, `:353-354`
- `itr_adapter.py:100-128`, `:411-412`

**Finding.** `is_available()` uses `shutil.which()` / `os.access()`, but it is not called by
production code. The only references outside the method definitions are unit tests.

Evidence:

```
$ grep -rn --exclude-dir=__pycache__ "is_available" src/runtime/src src/runtime/tests | grep -v "def is_available"
src/runtime/tests/unit/test_csg_adapter.py:410:    assert CsgAdapter().is_available() is True
src/runtime/tests/unit/test_csg_adapter.py:412:    assert CsgAdapter().is_available() is False
src/runtime/tests/unit/test_csg_adapter.py:417:    assert CsgAdapter(csg_bin="/nonexistent/csg").is_available() is False
src/runtime/tests/unit/test_weg_adapter.py:363:    assert WegAdapter().is_available() is True
src/runtime/tests/unit/test_weg_adapter.py:365:    assert WegAdapter().is_available() is False
src/runtime/tests/unit/test_weg_adapter.py:367:    assert WegAdapter(weg_bin="/nonexistent/weg").is_available() is False
src/runtime/tests/unit/test_itr_adapter.py:462:    assert ItrAdapter().is_available() is True
src/runtime/tests/unit/test_itr_adapter.py:464:    assert ItrAdapter().is_available() is False
src/runtime/tests/unit/test_itr_adapter.py:465:    assert ItrAdapter(itr_bin="/nonexistent/itr").is_available() is False
# no src/runtime/src/runtime/application or runtime/cli caller
```

`is_available()` bodies: `csg_adapter.py:139-163`, `weg_adapter.py:206-227`,
`itr_adapter.py:130-151`.

**Finding.** The runtime itself never invokes `command -v`.

Evidence:

```
$ grep -rn "command -v" src/runtime/src
EXIT=1   # no output
```

The provisioning role does use `command -v` to verify the installed names — but that is outside
the runtime:

Evidence: `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:124-130`
(`ansible.builtin.shell: "command -v {{ item.name }}"`), and `:98-122` installs/updates all
three with `uv tool install`.

**Finding.** Binary-name validation rejects empty strings and shell metacharacters before use
(defense in depth even though `shell=False`).

Evidence:

- CSG: `csg_adapter.py:79-87` (rejects `""` and `;|&\`$`).
- WEG: `weg_adapter.py:134-145` (rejects empty, NUL/CR/LF, whitespace and shell metacharacters).
- ITR: `itr_adapter.py:55-64` (same shape as WEG).

### 1.3 Exact argv construction

**Finding.** CSG argv is fixed. The adapter intentionally sends **no** `-o` / `--output`
flag; output redirection is exclusively the env var.

Evidence: `csg_adapter.py:278-300`:

```python
bin_name = self._csg_bin or "csg"
args = [
    bin_name, "generate", str(wallpaper_path),
    "--format", "yaml", "--format", "conf",
    "--format", "gtk.css", "--format", "adw.css",
    "--format", "sequences", "--format", "rasi",
    "--format", "kitty", "--format", "btop.theme",
]
```

Observed from the recording probe:

```
"/tmp/opencode/fake_cli.py", "generate", "/tmp/opencode/probe/wallpaper.png",
"--format", "yaml", "--format", "conf", "--format", "gtk.css", "--format", "adw.css",
"--format", "sequences", "--format", "rasi", "--format", "kitty", "--format", "btop.theme"
```

**Finding.** WEG argv is `weg batch all -- <wallpaper>`.

Evidence: `weg_adapter.py:351-360`:

```python
bin_name = self._weg_bin or "weg"
args = [bin_name, "batch", "all", "--", str(wallpaper_path)]
```

Observed: `"/tmp/opencode/fake_cli.py", "batch", "all", "--", ".../wallpaper.png"`.

**Finding.** ITR argv is `itr render` plus the mappings **file** when the resolved mappings
input is a regular file; when mappings is a directory, the argv is just `[itr, "render"]`.

Evidence: `itr_adapter.py:410-419`:

```python
bin_name = self._itr_bin or "itr"
args = [bin_name, "render"]
try:
    if effective_mappings.is_file():
        args.append(str(effective_mappings))
except OSError:
    pass
```

Observed file case: `"/tmp/opencode/fake_cli.py", "render", ".../icons.yaml"`.

**Finding.** A real `itr render` requires the `yaml_file` positional. Invoking it without one
exits 2.

Evidence:

```
$ itr render
Usage: itr render [OPTIONS] {yaml_file}
...
│ Missing argument 'yaml_file'. │
EXIT=2
```

CLI declaration: `src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/cli/render.py:21-23`
(`yaml_file: Path = typer.Argument(...)`). The runtime can resolve `icon_mappings` to a
directory (`derive.py:191-203`, candidate `install_spine / "icon-mappings"`), in which case
`ItrAdapter.render` supplies no `yaml_file`. On a provisioned spine, the first candidate
`<install>/icon-mappings/icons.yaml` is a file (`assets_copies` copies the repo manifest
directory containing `icons.yaml`: `src/provisioning/ansible/roles/assets/vars/main.yml:66-72`;
repo files include `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`), so the
file branch is the one used there. Whether every runtime environment has that file is an open
question (section 7).

### 1.4 cwd, stdin, subprocess kwargs

**Finding.** The subprocess is started with no `cwd=` and no stdin/input. The child inherits
the caller's cwd and fd 0.

Evidence:

```
$ grep -rn "cwd=\|stdin=\|input=" src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py
EXIT=1   # no output
```

Subprocess calls:

- CSG: `csg_adapter.py:303-310` — `subprocess.run(args, capture_output=True, text=True, env=env, timeout=self._timeout)`
- WEG: `weg_adapter.py:362-371` — same plus `errors="replace"`
- ITR: `itr_adapter.py:421-430` — same plus `errors="replace"`

Recording-probe observation for all three calls:

```
"cwd": "/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit/src/runtime",
"stdin_fd0": "/dev/null"
```

The cwd was the directory from which `uv run python ...` was executed; the adapter does not
change it. The WEG adapter's own catalog discovery explicitly consults `Path.cwd()` and up to
two parents (`weg_adapter.py:93-105`), so the inherited cwd is observable behavior for WEG.

### 1.5 Environment variables set

**Finding.** The exact per-adapter overrides are:

| Adapter | Env keys injected |
|---|---|
| CSG | `COLORSCHEME__OUTPUT__DIRECTORY=<output_dir>`, `COLORSCHEME__OUTPUT__OVERWRITE="true"` |
| WEG | `WALLPAPER__OUTPUT__DIRECTORY=<output_dir>` |
| ITR | `ICON_RENDERER__OUTPUT__OUTPUT_DIR=<output_dir>`, `ICON_RENDERER__COLOR_SCHEME__PATH=<palette colors.yaml>` |

Evidence:

- CSG: `csg_adapter.py:269-276`
- WEG: `weg_adapter.py:344-349`
- ITR: `itr_adapter.py:402-408`

**Finding.** These are added to an allowlisted copy of the host environment, not the full
environment. The allowlist is `PATH`, `HOME`, `XDG_*`, `TERM`, `LANG`, `LC_*`, TLS/proxy vars,
plus keys starting `COLORSCHEME__`, `WALLPAPER__`, `ICON_RENDERER__`, `XDG_`. Keys containing
`TOKEN`, `SECRET`, `PASSWORD`, `AWS_`, `GITHUB_` are blocked.

Evidence: `src/runtime/src/runtime/adapters/env.py:22-52`, `:64-70`, `:73-87`.

**Finding.** Observed child env for each adapter (recording probe):

- CSG: `COLORSCHEME__OUTPUT__DIRECTORY`, `COLORSCHEME__OUTPUT__OVERWRITE`, plus `PATH`, `HOME`,
  `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`.
- WEG: `WALLPAPER__OUTPUT__DIRECTORY`, plus the same host keys.
- ITR: `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH`, plus the same
  host keys.

Evidence: `/tmp/opencode/fake_cli_log.jsonl` (three lines), reproduced by
`docs/investigation/S1-probe/probe_adapters.py` (section 8, V9). Full first line reproduced in
section 3.3.

### 1.6 Timeouts

**Finding.** CSG and ITR default to 60 s; WEG defaults to 600 s.

Evidence:

- CSG constructor default `timeout: int = 60` — `csg_adapter.py:127`
- ITR constructor default `timeout: int = 60` — `itr_adapter.py:102`
- WEG `DEFAULT_TIMEOUT: int = 600` — `weg_adapter.py:188`; constructor uses it at `:192`
- Unit test asserts `WegAdapter.DEFAULT_TIMEOUT >= 300` and the instance default —
  `tests/unit/test_weg_adapter.py:269-274`

### 1.7 Production wiring

**Finding.** The production composition root constructs the adapters without `*_bin`
overrides, so the literal names are used.

Evidence:

- `src/runtime/src/runtime/cli/main.py:648-650` — `CsgAdapter(templates_dir=templates_dir)`,
  `WegAdapter()`, `ItrAdapter()`
- Repeated at `main.py:275-277`, `:1287-1289`, `:1518-1519`, `:1611-1612`

---

## 2. Question 2 — what output the runtime parses; error handling

### 2.1 No structured stdout parsing

**Finding.** The runtime does **not** parse CLI stdout as JSON, YAML, or `cli_output` views.
There is no `json.loads(result.stdout)` in any of the three adapters. Stdout is used only as a
truncated diagnostic when the return code is non-zero.

Evidence:

```
$ grep -rn "result\.stdout" src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py
csg_adapter.py:342,347,349
weg_adapter.py:386-398,419,424,426
itr_adapter.py:444-456,477,482,484
# all occurrences are error-message construction
```

```
$ grep -rn "json.loads\|loads(" src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py src/runtime/src/runtime/application/derive.py
EXIT=1   # no output
```

`cli_output` is used only to render the runtime's own CLI output, not to consume a CLI
subprocess:

Evidence: `src/runtime/src/runtime/cli/main.py:20-22` (`create_renderer`, `OutputFormat`,
`CustomView`, `ErrorView`), and `grep -rn "cli_output" src/runtime/src/runtime/adapters src/runtime/src/runtime/application`
returns only a docstring phrase in `src/runtime/src/runtime/application/regenerate.py:60`.

### 2.2 Success is exit status + artifact presence, not stdout

**Finding.** After a zero exit, each adapter verifies files in the supplied `output_dir` and
computes SHA-256 hashes of those files.

| CLI | Required artifacts after exit 0 | Hash source |
|---|---|---|
| CSG | exact names `colors.yaml`, `colors.conf`, `colors.gtk.css`, `colors.adw.css`, `colors.sequences`, `colors.rasi`, `colors.kitty`, `colors.btop.theme` | `hash_file()` on each |
| WEG | any file recursively under `output_dir` with suffix in `{.png,.jpg,.jpeg,.webp,.bmp,.tiff,.gif}` | `hash_file()` on each; key = basename if unique, else relative POSIX path |
| ITR | any file recursively under `output_dir` with suffix `.svg` | `hash_file()` on each; key = basename if unique, else relative POSIX path |

Evidence:

- CSG exact list and presence check: `csg_adapter.py:352-367`; hashes `:369-380`.
- WEG recursive image scan: `weg_adapter.py:429-444`; hashes/keys `:446-483`.
- ITR recursive SVG scan: `itr_adapter.py:487-497`; hashes/keys `:499-529`.

**Finding.** The adapter entry hash is computed from inputs, not from CLI output, and the
adapter rejects an output directory whose basename is not that hash before spawning.

Evidence:

- CSG `ph = palette_entry_hash(wallpaper_hash, template_set_hash)` at `csg_adapter.py:242-244`;
  output-dir validation `:90-114`; returned entry `:386-394`.
- WEG `eh = effects_entry_hash(wallpaper_hash, catalog_hash)` at `weg_adapter.py:318-320`;
  validation `:148-174`; returned entry `:487-495`.
- ITR `ih = icons_entry_hash(palette_hash, templates_hash, mappings_hash)` at
  `itr_adapter.py:316-318`; validation `:67-90`; returned entry `:533-542`.

The hash formulas themselves: `hashing.py:231-249` (palette), `:252-263` (effects),
`:266-280` (icons).

**Finding.** The application layer independently recomputes the same hash and cross-checks the
adapter's returned `entry_hash`; a mismatch raises `RuntimeError`.

Evidence: `derive.py:719-724` (palette), `:777-781` (effects), `:1056-1063` (icons):

```python
generated = self._csg.generate(wallpaper_path, work)
if generated.entry_hash != peh:
    raise RuntimeError(
        f"adapter entry hash mismatch: adapter={generated.entry_hash} "
        f"computed={peh} (templates dir divergence)"
    )
```

### 2.3 Typed fields the runtime depends on

**Finding.** The returned domain objects carry `hash_algorithm`, `kind`, `entry_hash`, the
source input hash(es), `artifact_hashes`, and `generated_at`. The artifact-hash key names are
fixed for palettes and open-ended for effects/icons.

Evidence: `src/runtime/src/runtime/domain/models.py:49-71` (`PaletteArtifacts`, `PaletteEntry`),
`:112-120` (`EffectsEntry`; `EffectsArtifacts` is `total=False`), `:132-141` (`IconsEntry`;
`IconsArtifacts` is `total=False`).

**Finding.** The runtime's `meta.json` consumes those fields. For example, the palette writer
maps the typed keys to file-name keys (`colors_yaml` → `colors.yaml`, etc.).

Evidence: `derive.py:726-742`; `seeder.py:288-336` (palette meta), `:338-386` (effects meta),
`:388-451` (icons meta).

### 2.4 Non-zero exit and other failures

**Finding.** All three adapters explicitly inspect `returncode` and raise `RuntimeError` with
the exit code plus truncated stderr/stdout. A negative return code is reported as a signal.

Evidence:

- CSG: `csg_adapter.py:331-350` — stderr up to 2048 chars, stdout up to 500; signal branch at
  `:333-345`.
- WEG: `weg_adapter.py:409-427` — same pattern.
- ITR: `itr_adapter.py:467-485` — same pattern.

**Finding.** Spawn/timeout failures map to typed exceptions:

| Failure | CSG | WEG | ITR |
|---|---|---|---|
| binary missing (`FileNotFoundError`/`ENOENT`) | `FileNotFoundError("csg not on PATH")` | `FileNotFoundError("weg not on PATH")` | `FileNotFoundError("itr not on PATH")` |
| permission denied | `FileNotFoundError("csg not on PATH (permission denied)")` | `FileNotFoundError("weg not on PATH (permission denied)")` | `PermissionError("itr not on PATH (permission denied)")` |
| timeout | `TimeoutError(...)` | `TimeoutError(...)` | `TimeoutError(...)` |
| env too large (`E2BIG`) | `RuntimeError(...)` | `RuntimeError(...)` | `RuntimeError(...)` |

Evidence: `csg_adapter.py:311-329`; `weg_adapter.py:372-407`; `itr_adapter.py:431-465`.
Note the ITR permission branch is `PermissionError` (`itr_adapter.py:433-434`), unlike CSG/WEG.

**Finding.** Unit tests assert the non-zero-exit path preserves stderr for all three.

Evidence:

- CSG: `tests/unit/test_csg_adapter.py:263-284` (`fake_fail` returns rc 1 with
  `"backend not available"`; `pytest.raises(RuntimeError, match="backend not available")`).
- WEG: `tests/unit/test_weg_adapter.py:222-245` (same shape).
- ITR: `tests/unit/test_itr_adapter.py:276-306` (`"template not found"`).

**Finding.** A zero exit with missing artifacts is also fatal (`RuntimeError("csg did not write
expected artifact...")`, etc.).

Evidence: `csg_adapter.py:363-367`; `weg_adapter.py:440-444`; `itr_adapter.py:493-497`.

### 2.5 Caller-level failure policy

**Finding.** Palette failure is hard; effects and icons failures are logged and degrade to a
null layer.

Evidence: `src/runtime/src/runtime/application/apply_wallpaper.py:186-222`:

- palette: `except Exception as exc: raise RuntimeError(f"palette apply failed: {exc}")`
- effects: `except Exception as exc: logger.warning("apply: effects generation failed; continuing: %s", exc)`
- icons: `except Exception as exc: logger.warning("apply: icon rendering failed; continuing: %s", exc)`

`SeedCacheUseCase` documents the same policy: `src/runtime/src/runtime/application/seed_cache.py:24-30`.

---

## 3. Question 3 — settings/config paths passed to the CLIs

### 3.1 No `--config` flag

**Finding.** The runtime never passes `--config` to any of the three CLIs. The only occurrence
of `--config` in `src/runtime` is a comment describing WEG's own CLI strategy.

Evidence:

```
$ grep -rn --exclude-dir=__pycache__ -- "--config" src/runtime/src
src/runtime/src/runtime/adapters/weg_adapter.py:58:    1. ``CliPathStrategy`` — ``--config`` flag (handled by the CLI, not here)
```

### 3.2 What each adapter does and does not pass

**CSG**

- Passes: `COLORSCHEME__OUTPUT__DIRECTORY`, `COLORSCHEME__OUTPUT__OVERWRITE`.
- Does **not** pass: the templates directory. `self._templates_dir` is used only for
  `canonical_hash_dir(templates_dir)` and entry-hash computation; it never enters argv or env.

Evidence: `csg_adapter.py:217-240` (hash), `:269-276` (env), `:278-300` (argv); recording-probe
env/argv in section 1.3.

**WEG**

- Passes: `WALLPAPER__OUTPUT__DIRECTORY`.
- Does **not** pass: the effects catalog path via argv or env. `self._catalog_path` (or
  `_find_default_effects_catalog()`) is used only to hash the catalog and compute `eh`.

Evidence: `weg_adapter.py:286-316` (catalog resolution + hash), `:344-349` (env), `:351-360`
(argv).

**Finding.** The WEG adapter's own catalog discovery consults the host
`WALLPAPER_EFFECTS_CONFIG_FILE_PATH`, but that variable is **not** forwarded to the child,
because `build_env` allows the `WALLPAPER__` prefix (double underscore) and not
`WALLPAPER_EFFECTS_` (single underscore).

Evidence:

- Adapter reads host env: `weg_adapter.py:73-81`.
- Allowlist prefix: `env.py:46-52` (`WALLPAPER__`).
- Probe: with host `WALLPAPER_EFFECTS_CONFIG_FILE_PATH=/tmp/z`, the child env showed
  `"WALLPAPER_EFFECTS_CONFIG_FILE_PATH"` absent from the child's `env_all_keys` and
  `"WALLPAPER__OUTPUT__DIRECTORY"` present only for the WEG call. The captured CSG call is
  representative of the allowlist: section 3.3.

**ITR**

- Passes: `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH`.
- Passes the mappings **file** as the required positional `yaml_file` when
  `effective_mappings.is_file()`.
- Does **not** pass: templates directory, and does not pass `yaml_file` for a mappings
  directory.

Evidence: `itr_adapter.py:402-419`; real `itr render` required-argument error in section 1.3.

**Finding.** The adapters themselves pass no container-engine flags (`-e`, volume mounts,
`--env`). Their docstrings state that CSG/WEG forward the host env into the container through
the CLI's own `container_processor`. Provisioning's image-build list contains `csg` and `weg`
but not `itr`.

Evidence: `csg_adapter.py:7-17`, `weg_adapter.py:7-16`, `itr_adapter.py:8-17`;
`src/provisioning/ansible/roles/cli_tools/vars/main.yml:42-48`
(`cli_tools_image_builds` = `csg`, `weg` only). The real CSG determinism test passed with
`container_mode: true` (`tests/integration/.csg_determinism.json`), and the real CSG adapter
integration test XPASSed (section 6.2).

### 3.3 XDG forwarding and filtering (observed)

**Finding.** `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`,
`PATH`, `HOME` are forwarded from the host; a secret and single-underscore tool-config vars
are not.

Evidence: probe command and observed child env (CSG call):

```
$ cd src/runtime
$ COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/tmp/x COLORSCHEME_OUTPUT_DIRECTORY=/tmp/y \
  WALLPAPER_EFFECTS_CONFIG_FILE_PATH=/tmp/z ICON_RENDERER_CONFIG_FILE_PATH=/tmp/w \
  MY_SECRET_TOKEN=leak DOTFILES_INSTALL_SPINE=/tmp/spine XDG_CONFIG_HOME=/tmp/xdg-config \
  FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
  uv run python ../../docs/investigation/S1-probe/probe_env.py

OK
{
  "COLORSCHEME__OUTPUT__DIRECTORY": "/tmp/opencode/probe_env/cache/palettes/79766d...",
  "COLORSCHEME__OUTPUT__OVERWRITE": "true",
  "DOTFILES_INSTALL_SPINE": null,
  "HOME": "/home/inumaki",
  "PATH": "...",
  "WALLPAPER__OUTPUT__DIRECTORY": null,
  "XDG_CACHE_HOME": "/home/inumaki/.cache",
  "XDG_CONFIG_HOME": "/tmp/xdg-config",
  "XDG_DATA_HOME": "/home/inumaki/.local/share",
  "XDG_STATE_HOME": "/home/inumaki/.local/state"
}

$ python3 - <<'PY'
import json
r=json.loads(open('/tmp/opencode/fake_cli_log.jsonl').readline())
for k in ('MY_SECRET_TOKEN','COLORSCHEME_TEMPLATES_TEMPLATES_DIR',
          'COLORSCHEME_OUTPUT_DIRECTORY','WALLPAPER_EFFECTS_CONFIG_FILE_PATH',
          'ICON_RENDERER_CONFIG_FILE_PATH','DOTFILES_INSTALL_SPINE',
          'XDG_CONFIG_HOME','PATH','HOME'):
    print(k, k in r['env_all_keys'])
PY
MY_SECRET_TOKEN False
COLORSCHEME_TEMPLATES_TEMPLATES_DIR False
COLORSCHEME_OUTPUT_DIRECTORY False
WALLPAPER_EFFECTS_CONFIG_FILE_PATH False
ICON_RENDERER_CONFIG_FILE_PATH False
DOTFILES_INSTALL_SPINE False
XDG_CONFIG_HOME True
PATH True
HOME True
```

The probe records `env_all_keys = sorted(os.environ)` inside the child
(`docs/investigation/S1-probe/fake_cli.py`), so the `False` lines above are direct evidence of
absence, not merely omission from a fixed capture list. `DOTFILES_INSTALL_SPINE` is likewise
absent even though the parent process can set it; it is not in the allowlist.

### 3.4 Where the runtime's paths come from

**Finding.** The install spine is resolved by `_resolve_install_spine()`:

1. `$DOTFILES_INSTALL_SPINE` if set;
2. otherwise `$XDG_DATA_HOME/dotfiles` (default `~/.local/share/dotfiles`).

Evidence: `src/runtime/src/runtime/cli/main.py:117-131`.

**Finding.** The state root is resolved by `_resolve_state_root()`:
`$XDG_STATE_HOME/dotfiles` (default `~/.local/state/dotfiles`), optionally suffixed with
`sessions/<id>` when a session id is resolvable.

Evidence: `src/runtime/src/runtime/cli/main.py:134-160`; session-id logic `:163-205`.

**Finding.** The four derivation inputs are resolved from the install spine (spine first),
with a repo checkout only when `DOTFILES_DEV_INPUTS_ROOT` is explicitly set:

| Input key | Spine candidate(s) | Repo fallback (dev only) |
|---|---|---|
| `csg_templates` | `<spine>/config/color-scheme-generator/templates` | `src/cli-tools/color-scheme-generator/{src/color_scheme_generator/,}defaults/templates` |
| `weg_effects` | `<spine>/config/weg/effects.yaml` | `src/cli-tools/wallpaper-effects-generator/{src/wallpaper_effects_generator/,}defaults/effects.yaml` |
| `icon_templates` | `<spine>/icon-templates`; `<spine>/config/icon-templates-renderer/templates` | `dotfiles/assets/icon-templates` |
| `icon_mappings` | `<spine>/icon-mappings/icons.yaml`; `<spine>/icon-mappings`; `<spine>/config/icon-templates-renderer/icons.yaml` | `dotfiles/config/icon-template-color-scheme-mappings/{icons.yaml,}` |

Evidence: `src/runtime/src/runtime/application/derive.py:152-205` (candidate table),
`:208-236` (`resolve_input`), `:256-277` (`find_*` wrappers).

**Finding.** The run-time output dirs are not spine paths; they are staging paths under the
state root. The pipeline supplies `staging/<entry-hash>` to each adapter:

- palette: `work = staging / peh` — `derive.py:717-719`
- effects: `work = staging / eeh` — `derive.py:775-777`
- icons: `work = staging / ieh` — `derive.py:1054-1057`

`staging` is a sibling of `cache/` named `.staging-<pid>-<uuid>`
(`cache.py:188-196`).

### 3.5 Provisioning-owned settings/config paths (context)

The runtime does not pass these paths, but they are the paths the CLIs themselves discover via
XDG, and the provisioning role establishes them:

- Settings files: `<install>/config/color-scheme-generator/settings.toml`,
  `<install>/config/weg/settings.toml`, `<install>/config/itr/settings.toml`.
  Evidence: `src/provisioning/ansible/roles/settings/vars/main.yml:69`, `:76-90`.
- Config links: `~/.config/color-scheme-generator`, `~/.config/weg`, `~/.config/itr` are
  symlinks to `<install>/config/<name>`.
  Evidence: `src/provisioning/ansible/roles/config_links/vars/main.yml:60-104`
  (managed dirs include `color-scheme-generator`, `weg`, `itr` at `:101-103`).
- CLI default cache dirs (manual runs only; overridden per runtime call):
  `<XDG_CACHE_HOME>/dotfiles/{weg-output,weg-tmp,csg-output,itr-output}`.
  Evidence: `src/provisioning/ansible/roles/settings/vars/main.yml:46-60`.
- The rendered ITR settings point templates at `<install>/icon-templates`
  (`src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2:8-9`) and the palette at
  `$XDG_STATE_HOME/dotfiles/current/colors.yaml` (`:16-17`).
- CSG/ WEG settings render `runtime.mode = "container"` and `image_tag = "latest"`:
  `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2:20-26`,
  `src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2:24-30`.

---

## 4. Question 4 — version pins and capability checks

### 4.1 No runtime version check

**Finding.** The runtime never invokes `--version` and has no version parsing/comparison for
`csg`, `weg`, or `itr`.

Evidence:

```
$ grep -rn -- "--version" src/runtime/src
EXIT=1   # no output
```

`grep -rn "version" src/runtime` returns `__version__ = "0.1.0"`
(`src/runtime/src/runtime/__init__.py:5`), schema `version` fields, and unrelated D-Bus/contract
wording; none is a CLI version check.

### 4.2 `is_available()` is not a production gate

**Finding.** The adapters expose `is_available()` (which uses `shutil.which`/`os.access`), but
no production code calls it; therefore a missing binary is discovered only when the adapter
attempts `subprocess.run`.

Evidence: section 1.2 grep; `subprocess.run` exception mapping in section 2.4.

### 4.3 No CLI dependency pin in the runtime package

**Finding.** `src/runtime/pyproject.toml` does not depend on any of the three CLI packages.

Evidence: `src/runtime/pyproject.toml:6-12` (`typer`, `cli-output`, `fastjsonschema`,
`jeepney`, `Pillow` only).

### 4.4 Test-only capability probe

**Finding.** The only `csg` capability probe found is in an integration test, not runtime code:
it runs `csg dump-templates -o <tmp>` and checks for `colors.adw.css.j2` and `colors.kitty.j2`.
The test is marked non-strict `xfail`.

Evidence: `src/runtime/tests/integration/test_csg_adapter_integration.py:29-51`
(`_csg_supports_artifact_set`, `subprocess.run([csg_bin, "dump-templates", "-o", str(out)], ...)`),
`:90-99` (`@pytest.mark.xfail(..., strict=False)`), `:100-110` (skip conditions).

### 4.5 Outside the runtime: provisioning installs, no version pin

**Finding.** Provisioning installs/updates the three tools from the current repo source with
`uv tool install` and `uv tool install --force`, then verifies the names resolve on PATH. No
version specifier is used.

Evidence: `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:98-109` (install),
`:117-122` (force reinstall), `:124-130` (`command -v` verification);
`src/provisioning/ansible/roles/cli_tools/vars/main.yml:56-60` (source specs).

**Finding.** The rendered container settings use `image_tag = "latest"` for both csg and weg.

Evidence: `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2:26`,
`src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2:30`.

---

## 5. Question 5 — state/cache directories the runtime expects; who writes/reads

### 5.1 What the CLIs are given

**Finding.** Each CLI receives a per-run staging work dir named after the computed entry hash,
under `<state_root>/cache/.staging-<pid>-<uuid>/`. The runtime creates the directory before
invocation; the CLI is expected to write artifacts into it.

Evidence:

- Staging path construction: `cache.py:188-196`.
- `populate_via_staging` creates the staging dir and calls `populate_fn(staging)`:
  `cache.py:517-580`.
- The pipeline passes `staging / <entry-hash>` to the adapter: `derive.py:717-719`,
  `:775-777`, `:1054-1057`.
- The adapter creates the output dir if missing: `csg_adapter.py:246-267`,
  `weg_adapter.py:322-342`, `itr_adapter.py:320-340`.

### 5.2 Final cache layout

**Finding.** The published cache layout is:

```
<state_root>/cache/wallpapers/<wh>/wallpaper.png + meta.json
<state_root>/cache/palettes/<ph>/colors.yaml + colors.conf + colors.gtk.css + colors.adw.css
                                + colors.sequences + colors.rasi + colors.kitty + colors.btop.theme
                                + meta.json
<state_root>/cache/effects/<eh>/**/*.{png,jpg,jpeg,webp,bmp,tiff,gif} + meta.json
<state_root>/cache/icons/<ih>/**/*.svg + meta.json
```

Evidence: `cache.py:6-13` (layout docstring); `cache.py:112-143` (`cache_entry_path` validation);
`seeder.py:597-696` (current symlink inventory names the same artifacts).

### 5.3 Who writes what

**Finding.** The CLIs write only artifacts in the supplied output dir. The runtime writes
`meta.json`, `current/` symlinks, and `current.json`.

Evidence:

- CLI artifacts: adapter post-run checks/hashes (`csg_adapter.py:352-380`,
  `weg_adapter.py:429-483`, `itr_adapter.py:487-529`).
- `meta.json` writes: `seeder.py:288-336` (palette), `:338-386` (effects), `:388-451` (icons);
  invoked from `derive.py:726-742`, `:783-790`, `:1065-1074`.
- Staging → final rename: `cache.py:517-604`.
- `current/` symlinks: `seeder.py:597-696` (cache entries) and `:698-801` (spine consumer
  pointers).
- `current.json`: `src/runtime/src/runtime/adapters/json_state_repository.py:1-20` (schema and
  projection contract), written by `apply_wallpaper.py:232-255`.

### 5.4 Who reads what

**Finding.** The runtime reads the cache in several places:

| Reader | What it reads | Evidence |
|---|---|---|
| `CacheSeeder.load_*_entry` | `cache/<layer>/<hash>/meta.json` → typed entry | `seeder.py:464-496` (palette), `:498-518` (effects), `:520-544` (icons) |
| `verify_entry` | `meta.json` + recorded artifact digests | `cache.py:331-393` |
| `InvalidationQueryAdapter.recorded_inputs` | `meta.json` input fields (`input_template_hash`, `input_catalog_hash`, `input_templates_hash`, `input_mappings_hash`) | `invalidation.py:161-202` |
| `InspectCacheUseCase` | `cache/<layer>/<64hex>` directory names only | `inspect.py:559-617` |
| `DoctorUseCase._check_entries` | entry dir + `meta.json` + artifact presence | `doctor.py:215-284` |
| `RegenerateStaleUseCase` | cached wallpaper bytes | `regenerate.py:145-158` |
| `JsonStateRepository` | hydrates `current.json` entries from `meta.json` | `json_state_repository.py:17-20`, `:71` |

**Finding.** Desktop consumers do not read the cache directly; they read the
`<state_root>/current/` symlinks and the spine consumer pointers created by the seeder.

Evidence: `seeder.py:597-696` (current symlink table), `:698-801` (spine pointer table); the
current symlink names include `colors.conf`, `colors.gtk.css`, `colors.yaml`,
`colors.adw.css`, `colors.sequences`, `colors.rasi`, `colors.kitty`, `colors.btop.theme`,
`effects`, `icons`.

### 5.5 CLI-owned dirs outside the passed output dir

**Finding.** No runtime code reads a CLI-specific output/cache directory such as
`<XDG_CACHE_HOME>/dotfiles/weg-output`, `csg-output`, or `itr-output`. Those are the CLIs'
manual-run defaults; the runtime overrides them per call.

Evidence:

- Defaults: `src/provisioning/ansible/roles/settings/vars/main.yml:46-60`.
- No runtime source references those four directory names:

  ```
  $ grep -rn "weg-output\|weg-tmp\|csg-output\|itr-output" src/runtime
  EXIT=1   # no output
  ```

- Runtime read paths are all under `<state_root>/cache` or `<state_root>/current`; the
  representative references are `derive.py:711`/`:769`/`:1048`, `seeder.py:597-696`,
  `invalidation.py:175`, `inspect.py:599`, `doctor.py:213`.
- WEG's `[processing] temp_dir` remains `<XDG_CACHE_HOME>/dotfiles/weg-tmp`
  (`src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2:15-16`); the runtime forwards `XDG_CACHE_HOME` (section 3.3), so WEG may
  use that scratch dir even though the runtime never reads it.

---

## 6. Question 6 — tests that assert the invocation contract

### 6.1 Unit assertions (quoted)

**CSG** — env keys, no `-o`/`--output`, eight `--format` pairs:

```python
assert env_passed["COLORSCHEME__OUTPUT__DIRECTORY"] == str(output_dir)
assert env_passed["COLORSCHEME__OUTPUT__OVERWRITE"] == "true"
assert "-o" not in args_passed
assert "--output" not in args_passed
assert "--format" in args_passed
assert args_passed.count("--format") == 8
```

Evidence: `tests/unit/test_csg_adapter.py:128-135`; non-zero exit at `:283-284`; entry-hash
mismatch at `:358-359` (`with pytest.raises(ValueError, match="hash mismatch")`).

**WEG** — env key, no `-o`/`--output`, positional `batch all <wallpaper>`:

```python
assert env_passed["WALLPAPER__OUTPUT__DIRECTORY"] == str(output_dir)
assert "-o" not in args_passed
assert "--output" not in args_passed
assert "batch" in args_passed
assert "all" in args_passed
assert str(wallpaper) in args_passed
```

Evidence: `tests/unit/test_weg_adapter.py:114-119`; non-zero exit at `:244-245`; entry-hash
mismatch at `:321-322`.

**ITR** — both env keys, no output/color-scheme flags, `render` present:

```python
assert env_passed["ICON_RENDERER__OUTPUT__OUTPUT_DIR"] == str(output_dir)
assert env_passed["ICON_RENDERER__COLOR_SCHEME__PATH"] == str(palette_entry / "colors.yaml")
assert "-o" not in args_passed
assert "--output" not in args_passed
assert "--output-dir" not in args_passed
assert "--color-scheme" not in args_passed
assert "render" in args_passed
```

Evidence: `tests/unit/test_itr_adapter.py:126-132`; non-zero exit at `:305-306`; entry-hash
mismatch at `:412-413`.

**Finding.** Entry-hash mismatch tests also assert the subprocess was never called.

Evidence: `tests/unit/test_csg_adapter.py:360` (`fake.assert_not_called()`),
`tests/unit/test_weg_adapter.py:323`, `tests/unit/test_itr_adapter.py:414`.

### 6.2 Commands and observed results

**Unit adapter tests:**

```
$ cd src/runtime
$ uv run pytest tests/unit/test_csg_adapter.py tests/unit/test_weg_adapter.py \
    tests/unit/test_itr_adapter.py -q
.................................                                        [100%]
33 passed in 0.09s
EXIT=0
```

**Broad adapter/CLI-name selection (the suggested command):**

```
$ cd src/runtime
$ uv run pytest tests/ -q -k "csg or weg or itr or adapter"
.................................................X...s.................. [ 49%]
........................................................................ [ 99%]
.
143 passed, 1 skipped, 1978 deselected, 1 xpassed, 6 warnings in 45.04s
EXIT=0
```

**Adapter integration tests with the real binaries on PATH:**

```
$ cd src/runtime
$ uv run pytest tests/integration/test_csg_adapter_integration.py \
    tests/integration/test_itr_adapter_integration.py \
    tests/integration/test_weg_adapter_integration.py -v -rs
tests/integration/test_csg_adapter_integration.py::test_csg_adapter_integration_real_binary XPASS
tests/integration/test_itr_adapter_integration.py::test_itr_adapter_integration_real_binary SKIPPED
tests/integration/test_weg_adapter_integration.py::test_weg_adapter_integration_real_binary PASSED
SKIPPED [1] tests/integration/test_itr_adapter_integration.py:147:
  itr real invocation skipped due to setup mismatch:
  itr render failed (exit 1): Error: Template not found:
  /home/inumaki/.local/share/dotfiles/icon-templates/battery/battery-0.svg
1 passed, 1 skipped, 1 xpassed, 3 warnings in 16.63s
EXIT=0
```

The CSG test is `xfail(strict=False)` and XPASSes because the installed `csg` supports the
expected formats; the ITR test's own guard skips when its minimal setup does not match the
real settings/discovery.

**CSG determinism (real `csg`, env override, container mode):**

```
$ cd src/runtime
$ uv run pytest tests/integration/test_csg_determinism.py -q -rs
..                                                                       [100%]
2 passed, 1 warning in 24.41s
EXIT=0
```

**Recording fake binary** (`docs/investigation/S1-probe/fake_cli.py`) captured three
invocations with the exact argv/env/cwd/stdin shown in sections 1.3–1.5 (full reproduction,
including the `cp` of the fake binary, is V9 in section 8):

```
$ cd src/runtime
$ rm -f /tmp/opencode/fake_cli_log.jsonl
$ FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
    uv run python ../../docs/investigation/S1-probe/probe_adapters.py
OK
$ wc -l /tmp/opencode/fake_cli_log.jsonl
3 /tmp/opencode/fake_cli_log.jsonl
```

**Real ITR probe** (private XDG config; real `itr` on PATH):

```
$ cd src/runtime
$ uv run python ../../docs/investigation/S1-probe/probe_itr_real.py
OK ee4371bf61431b231fc44d0d87fcc60bf22b9bb2df9c6c9002024333615f83ab ['battery-0.svg']
EXIT=0
```

---

## 7. Open questions

1. **CSG template-set parity.** The runtime hashes the templates dir it resolved from the
   install spine (`derive.py:708-710`, `csg_adapter.py:217-240`) but does not pass that path to
   `csg`; the CLI resolves templates itself (`src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/template_dir_resolver.py:21-30`:
   CLI → env → cwd traversal → `$XDG_CONFIG_HOME/color-scheme-generator/templates` → bundled).
   The provisioning symlink `~/.config/color-scheme-generator → <install>/config/color-scheme-generator`
   (`src/provisioning/ansible/roles/config_links/vars/main.yml:101`) is intended to make the XDG path the same content, but
   the runtime never asserts that the CLI resolved the same directory it hashed.
   `Evidence: MISSING — no runtime check found; would require observing csg inside the child or a
   csg-side path report.`

2. **WEG catalog parity.** The runtime hashes the catalog from
   `require_input("weg_effects", install_spine)` (`derive.py:766-767`), while `WegAdapter()`
   discovers its own catalog via host env / `$XDG_CONFIG_HOME/weg/effects.yaml` / cwd traversal
   / repo ancestor (`weg_adapter.py:51-131`) and the CLI separately discovers its own. The
   provisioning symlink `~/.config/weg → <install>/config/weg` is intended to converge them
   (`src/provisioning/ansible/roles/config_links/vars/main.yml:102`), but there is no runtime assertion that the path hashed is
   the path the child loads. Additionally, the adapter's host-env branch
   (`WALLPAPER_EFFECTS_CONFIG_FILE_PATH`, `weg_adapter.py:73-81`) is filtered out of the child
   env by `build_env` (section 3.2), so that specific host override cannot reach WEG through the
   adapter.
   `Evidence: MISSING — no runtime check found; would require observing weg's loaded catalog.`

3. **ITR templates/mappings parity.** The runtime passes `templates_dir` to `ItrAdapter` for
   hashing (`derive.py:1012-1015`, `itr_adapter.py:189-239`) but does not pass it to `itr`;
   ITR resolves `[templates] dir` from its settings (`src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2:8-9`) or discovery
   (`src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/cli/_helpers.py:66-71`). For a mappings **directory**, the adapter
   omits the required `yaml_file` positional entirely (`itr_adapter.py:413-417`), and real
   `itr render` exits 2 (`Missing argument 'yaml_file'`). The provisioned spine provides
   `<install>/icon-mappings/icons.yaml`, so the file branch is the observed production path
   (`src/provisioning/ansible/roles/assets/vars/main.yml:66-72`), but a non-provisioned or partial spine can hit the dir
   branch.
   `Evidence: MISSING — no runtime check that the CLI resolved the same templates/mappings the
   runtime hashed; the dir-branch behavior is proven, but whether it occurs on a supported
   deployment is not.`

4. **Container-mode coverage across engines.** The real CSG adapter integration XPASSed and the
   CSG determinism test reported `container_mode: true`, `engine: podman`
   (`tests/integration/.csg_determinism.json`). There is no executed evidence in this session
   for a docker engine or for an unbuilt image; the determinism test's own skip path treats an
   unbuilt image as "not proven" (`src/runtime/tests/integration/test_csg_determinism.py:423-452`).
   `Evidence: MISSING — run with container_runtime_engine=docker and an unbuilt image to
   observe the skip/failure paths.`

5. **Version compatibility is unasserted.** Because no runtime version check exists
   (section 4.1) and provisioning reinstalls from the current repo source without a version
   specifier (section 4.5), the runtime has no evidence that a given installed CLI supports the
   argv/env contract it uses except the tests' runtime behavior. The only explicit capability
   guard is test-only (`src/runtime/tests/integration/test_csg_adapter_integration.py:29-51`).
   `Evidence: MISSING — no version handshake in the protocol.`

---

## 8. Verify

Run from the worktree root unless marked `src/runtime`.

```
# --- V1: adapters exist, one per CLI, and implement the ports
sed -n '117,124p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '177,183p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '93,99p'  src/runtime/src/runtime/adapters/itr_adapter.py
cat src/runtime/src/runtime/ports/color_scheme_generator.py \
    src/runtime/src/runtime/ports/effects_generator.py \
    src/runtime/src/runtime/ports/icon_renderer.py

# --- V2: binary resolution is literal name / constructor override, no which at invoke
sed -n '125,163p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '190,227p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '100,151p' src/runtime/src/runtime/adapters/itr_adapter.py
grep -rn "command -v" src/runtime/src/runtime            # expect: no output, exit 1
grep -rn "is_available" src/runtime/src/runtime           # expect: only method defs, no callers
grep -rn "is_available" src/runtime/tests                 # expect: unit tests only

# --- V3: exact argv (CSG / WEG / ITR)
sed -n '278,310p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '351,371p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '410,430p' src/runtime/src/runtime/adapters/itr_adapter.py

# --- V4: no cwd / stdin / input kwarg
grep -rn "cwd=\|stdin=\|input=" \
  src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py    # expect: exit 1

# --- V5: env allowlist and per-adapter override keys
sed -n '22,70p' src/runtime/src/runtime/adapters/env.py
sed -n '269,276p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '344,349p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '402,408p' src/runtime/src/runtime/adapters/itr_adapter.py

# --- V5a: no runtime reads of the CLIs' manual-run cache dirs
grep -rn "weg-output\|weg-tmp\|csg-output\|itr-output" src/runtime   # expect: exit 1
sed -n '711p;769p;1048p' src/runtime/src/runtime/application/derive.py
sed -n '213p' src/runtime/src/runtime/application/doctor.py
sed -n '599p' src/runtime/src/runtime/application/inspect.py
sed -n '175p' src/runtime/src/runtime/adapters/invalidation.py

# --- V6: no stdout parsing / no cli_output in adapters
grep -rn "result\.stdout" \
  src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py
grep -rn "json.loads" \
  src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py \
  src/runtime/src/runtime/application/derive.py                 # expect: exit 1
grep -rn "cli_output" src/runtime/src/runtime/adapters \
  src/runtime/src/runtime/application                           # expect: only regenerate.py:60 docstring

# --- V7: artifact checks and entry-hash cross-check
sed -n '352,380p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '429,483p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '487,529p' src/runtime/src/runtime/adapters/itr_adapter.py
sed -n '719,724p;777,781p;1056,1063p' src/runtime/src/runtime/application/derive.py

# --- V8: error mapping
sed -n '331,350p' src/runtime/src/runtime/adapters/csg_adapter.py
sed -n '409,427p' src/runtime/src/runtime/adapters/weg_adapter.py
sed -n '467,485p' src/runtime/src/runtime/adapters/itr_adapter.py

# --- V9: recording probe (argv/cwd/stdin/env)
cd src/runtime
cp ../../docs/investigation/S1-probe/fake_cli.py /tmp/opencode/fake_cli.py
chmod +x /tmp/opencode/fake_cli.py
rm -f /tmp/opencode/fake_cli_log.jsonl
rm -rf /tmp/opencode/probe
FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
  uv run python ../../docs/investigation/S1-probe/probe_adapters.py    # OK
cat /tmp/opencode/fake_cli_log.jsonl                                  # 3 JSON lines
cd ../..

# --- V10: env filtering probe
cd src/runtime
cp ../../docs/investigation/S1-probe/fake_cli.py /tmp/opencode/fake_cli.py
chmod +x /tmp/opencode/fake_cli.py
rm -f /tmp/opencode/fake_cli_log.jsonl
rm -rf /tmp/opencode/probe_env
COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/tmp/x COLORSCHEME_OUTPUT_DIRECTORY=/tmp/y \
WALLPAPER_EFFECTS_CONFIG_FILE_PATH=/tmp/z ICON_RENDERER_CONFIG_FILE_PATH=/tmp/w \
MY_SECRET_TOKEN=leak DOTFILES_INSTALL_SPINE=/tmp/spine XDG_CONFIG_HOME=/tmp/xdg-config \
FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
  uv run python ../../docs/investigation/S1-probe/probe_env.py         # OK
python3 -c 'import json; k=json.loads(open("/tmp/opencode/fake_cli_log.jsonl").readline())["env_all_keys"]; print({x: (x in k) for x in ("MY_SECRET_TOKEN","COLORSCHEME_TEMPLATES_TEMPLATES_DIR","WALLPAPER_EFFECTS_CONFIG_FILE_PATH","DOTFILES_INSTALL_SPINE","XDG_CONFIG_HOME")})'
cd ../..

# --- V11: unit + broad tests
cd src/runtime
uv run pytest tests/unit/test_csg_adapter.py tests/unit/test_weg_adapter.py \
  tests/unit/test_itr_adapter.py -q                                    # 33 passed
uv run pytest tests/ -q -k "csg or weg or itr or adapter"              # 143 passed, 1 skipped, 1 xpassed
cd ../..

# --- V12: integration tests with real binaries
cd src/runtime
uv run pytest tests/integration/test_csg_adapter_integration.py \
  tests/integration/test_itr_adapter_integration.py \
  tests/integration/test_weg_adapter_integration.py -v -rs             # 1 passed, 1 skipped, 1 xpassed
uv run pytest tests/integration/test_csg_determinism.py -q -rs         # 2 passed
cd ../..

# --- V13: real ITR invocation
cd src/runtime
rm -rf /tmp/opencode/probe_itr_real
uv run python ../../docs/investigation/S1-probe/probe_itr_real.py      # OK ... ['battery-0.svg']
cd ../..

# --- V14: no version check / no --config
grep -rn -- "--version" src/runtime/src                            # exit 1
grep -rn -- "--config" src/runtime                                   # only weg_adapter.py:58 comment

# --- V15: no CLI dependency in runtime package
sed -n '1,15p' src/runtime/pyproject.toml

# --- V16: provisioning install / config paths (context)
sed -n '98,130p' src/provisioning/ansible/roles/cli_tools/tasks/main.yml
sed -n '56,60p' src/provisioning/ansible/roles/cli_tools/vars/main.yml
sed -n '46,90p' src/provisioning/ansible/roles/settings/vars/main.yml
sed -n '60,104p' src/provisioning/ansible/roles/config_links/vars/main.yml
nl -ba src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2 | sed -n '20,26p'
nl -ba src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2 | sed -n '24,30p'
nl -ba src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2 | sed -n '1,17p'
```

### Exit codes / observations recorded

| check | result |
|---|---|
| `rg '^(from\|import) (cli packages)' src/runtime --glob '*.py'` | exit 1, no matches |
| `grep -rn "command -v" src/runtime/src` | exit 1, no matches |
| `grep -rn "cwd=\|stdin=\|input=" .../{csg,weg,itr}_adapter.py` | exit 1, no matches |
| `grep -rn -- "--version" src/runtime/src` | exit 1, no matches |
| `grep -rn "is_available" src/runtime/src/runtime` | only the three method definitions, no callers |
| `uv run pytest tests/unit/test_{csg,weg,itr}_adapter.py -q` | `33 passed in 0.09s`, exit 0 |
| `uv run pytest tests/ -q -k "csg or weg or itr or adapter"` | `143 passed, 1 skipped, 1978 deselected, 1 xpassed in 45.04s`, exit 0 |
| adapter integration tests (`-v -rs`) | `1 passed` (weg), `1 skipped` (itr), `1 xpassed` (csg), exit 0 |
| `uv run pytest tests/integration/test_csg_determinism.py -q -rs` | `2 passed in 24.41s`, exit 0 |
| real `itr render` with no arg | `Missing argument 'yaml_file'.`, exit 2 |
| real-ITR probe | `OK ee4371bf... ['battery-0.svg']`, exit 0 |
| recording probe | 3 JSON lines, cwd `.../src/runtime`, stdin `/dev/null` |
| env-filter probe | secret + single-underscore config vars absent; `XDG_CONFIG_HOME` forwarded |

---

## Appendix A — probe scripts

The probe scripts used above are checked in under `docs/investigation/S1-probe/`:

- `fake_cli.py` — recording stand-in for all three consoles.
- `probe_adapters.py` — runs all three adapters against `fake_cli.py`.
- `probe_env.py` — proves which host env keys are forwarded vs filtered.
- `probe_itr_real.py` — invokes the real `itr` with a private XDG config.

They write only under `/tmp/opencode/` and do not touch the runtime state root.
