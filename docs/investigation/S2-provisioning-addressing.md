# S2 — Provisioning addressing chain for the CLI tools

> **Historical (2026-10-22):** evidence-only spike from before the assets/engine split; the
> `dotfiles/config/zsh/...` path it records is now the pinned `dotfiles-assets` templates class.

**Type:** evidence-only spike. **Worktree:** `/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit`
(branch `ticket/clirsplit-investigate-and-spine`, HEAD `fb94b64e`, `master` = `fb94b64e`).
**Question:** what is the complete provisioning addressing chain for `csg`, `weg`, `itr`, and
`dotfiles-runtime`, and exactly which references break if they move to external pinned repos?

No recommendations or design proposals appear in this document. Every non-trivial claim carries
`Evidence:` with the command that was run (and its key output / exit code) or a `file:line` that was
read. Where something could not be proven it is marked `Evidence: MISSING`.

All paths below are relative to the worktree root unless absolute.

---

## 1. `dotfiles/provisioning/cli-tools.yaml`

### 1.1 Full contents and declaration

```
$ cat dotfiles/provisioning/cli-tools.yaml
# CLI tools installed via `uv tool install` from repo source paths (plan §3).
#
# csg/weg/itr are the three compute-provider CLIs; dotfiles-runtime is the
# desktop-state CLI (wallpaper set / reconcile / inspect) that the login
# hook needs on PATH. src/cli-tools/openspec/ is NOT an install target and
# must not be listed here.
kind: cli-tools
entries:
  - name: csg
    source: src/cli-tools/color-scheme-generator
  - name: weg
    source: src/cli-tools/wallpaper-effects-generator
  - name: itr
    source: src/cli-tools/icon-templates-renderer
  - name: dotfiles-runtime
    source: src/runtime
```

Claim: the manifest declares four entries, each as `{name, source}` where `source` is a
repo-relative directory, not a URL or a git ref.

`Evidence:` `dotfiles/provisioning/cli-tools.yaml:7-16` (read in full; reproduced above).

Claim: `src/cli-tools/openspec/` exists but is explicitly excluded from the manifest.

`Evidence:` `dotfiles/provisioning/cli-tools.yaml:5-6`; `ls src/cli-tools/` →
`color-scheme-generator  icon-templates-renderer  openspec  wallpaper-effects-generator`.

### 1.2 Who consumes the manifest

Claim: **Ansible does not read `cli-tools.yaml`.** The `cli_tools` role carries a hand-written
mirror of the manifest in `vars/main.yml`, and the file itself says the parity is locked by a
structural test rather than by a runtime read.

`Evidence:`

- `src/provisioning/ansible/roles/cli_tools/vars/main.yml:50-55`:
  ```
  # cli_tools: install specs mirroring dotfiles/provisioning/cli-tools.yaml
  #   (csg/weg/itr -> repo source paths, plus dotfiles-runtime -> src/runtime).
  #   ...
  #   Parity with the manifest is locked by a structural test.
  ```
- `src/provisioning/ansible/roles/cli_tools/vars/main.yml:56-60` repeats the four entries
  verbatim:
  ```
  cli_tools:
    - { name: csg, source: src/cli-tools/color-scheme-generator }
    - { name: weg, source: src/cli-tools/wallpaper-effects-generator }
    - { name: itr, source: src/cli-tools/icon-templates-renderer }
    - { name: dotfiles-runtime, source: src/runtime }
  ```
- `src/provisioning/ansible/playbooks/cli-tools.yaml:13-17` runs the role; it never names the
  manifest:
  ```
  - name: Install CLI tools via uv
    hosts: localhost
    gather_facts: true
    roles:
      - cli_tools
  ```
- No script under `scripts/` reads it:
  ```
  $ grep -rn "cli-tools.yaml" scripts/
  (no output)
  ```
- No production module imports the YAML reader for this manifest. `YamlManifestReader` is
  exported from `src/provisioning/src/provisioning/adapters/__init__.py:3`, but its only callers
  are tests:
  ```
  $ grep -rn "YamlManifestReader" --include="*.py" .
  ./src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py:7
  ./src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py:11
  ./src/provisioning/src/provisioning/adapters/__init__.py:3
  ./src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py:184
  ./src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py:196
  ```
- The orchestrator runs playbooks, not manifests: `src/provisioning/src/provisioning/application/use_cases.py:66-74`
  constructs `ProvisionMachineUseCase` with `playbook: Path("bootstrap.yaml")`; `grep -rn
  "cli-tools.yaml\|ManifestKind\|YamlManifestReader" src/provisioning/src` matches only the
  reader/enums/models files, never `use_cases.py` or `cli/main.py`.

Claim: the manifest schema accepts only `name`, `source`, and an optional `version`; there is no
`repo`, `url`, or `ref` key.

`Evidence:` `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py:41-44`:
```python
ManifestKind.CLI_TOOLS: (
    frozenset({"name", "source", "version"}),
    frozenset({"name", "source"}),
),
```
The entries in `cli-tools.yaml` use only `name` and `source` (`:9-16`), so `version` is declared
in the schema but unused by the manifest today.

### 1.3 The parity check, and its execution

Claim: parity is a pytest assertion comparing the role list to the manifest by exact dict items.

`Evidence:` `src/provisioning/tests/unit/test_cli_tools_role.py:692-701`:
```python
def test_cli_tools_parity_with_manifest(self) -> None:
    """Parity lock: the role var exactly mirrors the manifest by
    (name, source) so they can never silently diverge (AC 2)."""
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    role_entries = [dict(item) for item in data["cli_tools"]]
    manifest_entries = _manifest_entries()
    assert len(role_entries) == len(manifest_entries)
    assert {tuple(e.items()) for e in role_entries} == {
        tuple(e.items()) for e in manifest_entries
    }
```

Claim: the test passes today.

`Evidence:` (executed from the worktree)
```
$ uv run --directory src/provisioning pytest \
    "tests/unit/test_cli_tools_role.py::TestCliToolsVars::test_cli_tools_parity_with_manifest" -q
.                                                                        [100%]
1 passed in 0.02s
EXIT=0
```

Claim: the whole `test_cli_tools_role.py` suite passes (43 tests).

`Evidence:` `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py -q` →
`43 passed in 2.25s`.

Claim: **no Makefile gate runs this parity test.** `contracts-check` runs tests under
`src/runtime` only; `per-app-drift-symbol-suites` is empty; `deploy-coverage`, `ci-gates-parity`,
and `ansible-embedded-template-lint` are Python scripts that do not invoke pytest.

`Evidence:`

- `Makefile:14` (`contracts-check`): `uv run --directory src/runtime pytest
  tests/unit/test_contract_schema_conformance.py ... -q`.
- `Makefile:48-49`: `GATES := contracts-check ansible-embedded-template-lint deploy-coverage
  ci-gates-parity per-app-drift-symbol-suites`.
- `Makefile:138`: `PER_APP_SUITES :=` (empty).
- `make -n gates-ci` output (exit 0) shows the five recipes above and no `pytest` for
  `src/provisioning`.

---

## 2. `src/provisioning/ansible/roles/cli_tools/`

### 2.1 `vars/main.yml`

Claim: the repo root used by every install is derived from the playbook location, not from an
external unit path.

`Evidence:` `vars/main.yml:3-8`:
```
# cli_tools_repo_root: repo root derived from this playbook's location.
#   cli-tools.yaml lives at <repo>/src/provisioning/ansible/playbooks/, so
#   <repo> = {{ playbook_dir }}/../../../.. (playbooks -> ansible ->
#   provisioning -> src -> repo root). Overridable if a future user runs the
#   playbooks from a relocated repo.
cli_tools_repo_root: "{{ playbook_dir }}/../../../.."
```

Claim: the bin dir is resolved exactly as uv resolves it: `$UV_TOOL_BIN_DIR` → `$XDG_BIN_HOME` →
`$HOME/.local/bin`.

`Evidence:` `vars/main.yml:10-21`:
```yaml
# cli_tools_bin_dir: uv's executable directory, resolved EXACTLY as uv does,
#   so the PATH prepend + `creates` guard match where `uv tool install` actually
#   drops the binary. Resolution order (uv docs): $UV_TOOL_BIN_DIR ->
#   $XDG_BIN_HOME -> $HOME/.local/bin. ...
cli_tools_bin_dir: >-
  {{ ansible_facts.env.UV_TOOL_BIN_DIR
     | default(ansible_facts.env.XDG_BIN_HOME | default(ansible_facts.env.HOME + '/.local/bin', true), true) }}
```

Claim: the container engine is a declared value, not detected; `cli_tools_engine_smoke_image` is
pinned.

`Evidence:` `vars/main.yml:23-38`:
```yaml
# CONTAINER ENGINE — DECLARED, not detected:
# ... The engine is the DECLARED value from group_vars/all.yml (shipped default podman; ...
cli_tools_engine_smoke_image: "docker.io/library/alpine:3.20"
```
The declared value itself is `group_vars/all.yml:36`:
```yaml
container_runtime_engine: "{{ ansible_facts.env.DOTFILES_CONTAINER_ENGINE | default('podman', true) }}"
```

Claim: only `csg` and `weg` get container images; `itr` is deliberately absent.

`Evidence:` `vars/main.yml:40-48`:
```yaml
# cli_tools_image_builds: the container-mode CLIs whose container images this
#   role builds after `uv tool install`. `itr` is deliberately absent (no
#   container mode). ...
cli_tools_image_builds:
  - { name: csg }
  - { name: weg }
```

### 2.2 `tasks/main.yml` — the install path

Claim: the first-install task runs `uv tool install --no-cache` against
`{{ cli_tools_repo_root }}/{{ item.source }}`, with `creates:` on the bin path and
`UV_TOOL_BIN_DIR` pinned to `cli_tools_bin_dir`.

`Evidence:` `tasks/main.yml:98-109`:
```yaml
- name: Install csg/weg/itr via uv tool install
  ansible.builtin.command: "uv tool install --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'"
  args:
    creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"
  environment:
    # Pin UV_TOOL_BIN_DIR to the same cli_tools_bin_dir the `creates` guard and
    # the verify PATH prepend use. ...
    UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"
  loop: "{{ cli_tools }}"
```

Claim: a second, force-upgrade pass re-installs every tool from current repo source on every
bootstrap run, with no `creates:` guard and gated off check mode.

`Evidence:` `tasks/main.yml:111-122`:
```yaml
# Upgrade-after-install (2026-09-07): the `creates:` guard above only fires on
# FIRST install, so an already-provisioned machine kept running a stale itr
# forever ...
- name: Upgrade csg/weg/itr tool envs from current repo source
  ansible.builtin.command: "uv tool install --force --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'"
  environment:
    UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"
  loop: "{{ cli_tools }}"
  when: not ansible_check_mode
```

Claim: after installation the role verifies each console script with the `command -v` shell
builtin and a PATH prepend, not with a `stat`/symlink check.

`Evidence:` `tasks/main.yml:124-129`:
```yaml
- name: Verify csg/weg/itr resolve on PATH
  ansible.builtin.shell: "command -v {{ item.name }}"
  loop: "{{ cli_tools }}"
  environment:
    PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"
  changed_when: false
```

Claim: the image-build step at the end passes both the declared engine and an **explicit local
source root**, and has no `creates:` guard.

`Evidence:` `tasks/main.yml:328-340`:
```yaml
- name: Build container images for the container-mode CLIs
  ansible.builtin.command:
    argv:
      - "{{ item.name }}"
      - install
      - --container-engine
      - "{{ container_runtime_engine }}"
      - --source-root
      - "{{ cli_tools_repo_root }}"
  loop: "{{ cli_tools_image_builds }}"
  environment:
    PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"
  when: not ansible_check_mode
```
The comment at `:194-197` states the reason: the build context must not depend on the CLI
rediscovering its source via PEP 610 metadata.

Every local-path expression in the task file, with its line:

| Line(s) | Expression | Use |
|---|---|---|
| `41-42` | `{{ cli_tools_repo_root }}/dotfiles/provisioning/scripts/gloview-activate` → `{{ cli_tools_bin_dir }}/gloview-activate` | copy one repo script into the bin dir |
| `49`, `58`, `69`, `77`, `85`, `95` | `{{ cli_tools_bin_dir }}/<launcher>` | render six launcher templates |
| `99` | `{{ cli_tools_repo_root }}/{{ item.source }}` | first `uv tool install` source |
| `101` | `{{ cli_tools_bin_dir }}/{{ item.name }}` | `creates:` guard |
| `108` | `UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"` | pin uv's bin dir |
| `118` | `{{ cli_tools_repo_root }}/{{ item.source }}` | force-upgrade source |
| `120` | `UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"` | pin uv's bin dir |
| `125`, `128` | `command -v {{ item.name }}` with `PATH: "{{ cli_tools_bin_dir }}:..."` | PATH verification |
| `146`, `151` | `{{ cli_tools_bin_dir }}/codex` | Codex shadow check/removal |
| `164`, `169` | `{{ ansible_facts.env.HOME }}/.codex/packages[/standalone]` | Codex payload check/removal |
| `335-336` | `--source-root "{{ cli_tools_repo_root }}"` | container build context |
| `339` | `PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"` | image-build PATH |

`Evidence:` the table is a line-by-line read of `tasks/main.yml`; every expression above is quoted
from the file at the stated line.

Claim: the same role copies one repo file and renders six launchers into the same bin dir; these
are local path references in the role, but they are not CLI-tool package sources.

`Evidence:` `tasks/main.yml:39-96`; the only repo source path is
`tasks/main.yml:41-42`:
```yaml
src: "{{ cli_tools_repo_root }}/dotfiles/provisioning/scripts/gloview-activate"
dest: "{{ cli_tools_bin_dir }}/gloview-activate"
```
The templates use `REPO_ROOT="{{ cli_tools_repo_root }}"` as a checkout hint for the
`icme`/`btop-theme-studio` GUI launchers
(`roles/cli_tools/templates/icon-color-mapping-editor.j2:22`,
`roles/cli_tools/templates/btop-theme-studio.j2:22`), not as a CLI install target.

### 2.3 The package side that `uv tool install` resolves

Claim: each CLI declares its console-script name in its own `pyproject.toml`; that name is what
the role's `creates:` guard looks for.

`Evidence:`

- `src/cli-tools/color-scheme-generator/pyproject.toml:16-17` → `csg = "color_scheme_generator.cli.main:app"`
- `src/cli-tools/wallpaper-effects-generator/pyproject.toml:23-24` → `weg = "wallpaper_effects_generator.cli.main:app"`
- `src/cli-tools/icon-templates-renderer/pyproject.toml:16-17` → `itr = "icon_templates_renderer.cli.main:app"`
- `src/runtime/pyproject.toml:14-15` → `dotfiles-runtime = "runtime.cli.main:app"`

Claim: all four packages depend on sibling shared libraries through **relative path sources**
marked editable. There is no published version requirement for `cli-output` in three of them
(`csg`/`itr`/`runtime` declare bare `cli-output`; `weg` declares `cli-output>=0.1.0`, but its
`[tool.uv.sources]` still overrides it with a path).

`Evidence:`

- `src/cli-tools/color-scheme-generator/pyproject.toml:39-42`:
  ```toml
  [tool.uv.sources]
  cli-output = { path = "../../shared/cli-output", editable = true }
  config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
  oci-runtime = { path = "../../shared/oci-runtime", editable = true }
  ```
- `src/cli-tools/wallpaper-effects-generator/pyproject.toml:26-29`:
  ```toml
  [tool.uv.sources]
  cli-output = { path = "../../shared/cli-output", editable = true }
  config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
  oci-runtime = { path = "../../shared/oci-runtime", editable = true }
  ```
- `src/cli-tools/icon-templates-renderer/pyproject.toml:36-38`:
  ```toml
  [tool.uv.sources]
  cli-output = { path = "../../shared/cli-output", editable = true }
  config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
  ```
- `src/runtime/pyproject.toml:24-25`:
  ```toml
  [tool.uv.sources]
  cli-output = { path = "../shared/cli-output", editable = true }
  ```
- The locks pin the same relative edits: `src/cli-tools/color-scheme-generator/uv.lock:26,93,233`;
  `src/cli-tools/wallpaper-effects-generator/uv.lock:26,49,169`;
  `src/cli-tools/icon-templates-renderer/uv.lock:26,49`;
  `src/runtime/uv.lock:85`.

Claim: on this host, a `uv tool install` of these packages produced tool environments whose PEP 610
metadata and `.pth` files point at the **absolute paths of the checkout**, including the editable
shared libraries. This is executed evidence of how the current install mode resolves.

`Evidence:` (host-level, installed from `/home/inumaki/Development/dotfiles-v3`, not from this
worktree; host `uv --version` → `uv 0.9.22`):
```
$ uv tool list
color-scheme-generator v0.1.0
- csg
dotfiles-runtime v0.1.0
- dotfiles-runtime
icon-templates-renderer v0.1.0
- itr
mu v0.1.0
- mu
wallpaper-effects-generator v0.1.0
- weg

$ ls -la ~/.local/bin | grep -E "csg|weg|itr|dotfiles-runtime"
lrwxrwxrwx ... csg -> /home/inumaki/.local/share/uv/tools/color-scheme-generator/bin/csg
lrwxrwxrwx ... dotfiles-runtime -> /home/inumaki/.local/share/uv/tools/dotfiles-runtime/bin/dotfiles-runtime
lrwxrwxrwx ... itr -> /home/inumaki/.local/share/uv/tools/icon-templates-renderer/bin/itr
lrwxrwxrwx ... weg -> /home/inumaki/.local/share/uv/tools/wallpaper-effects-generator/bin/weg

$ find ~/.local/share/uv/tools/color-scheme-generator -name direct_url.json -exec cat {} \;
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/shared/oci-runtime","dir_info":{"editable":true}}
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/cli-tools/color-scheme-generator","dir_info":{}}
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/shared/config-assembler-engine","dir_info":{"editable":true}}
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/shared/cli-output","dir_info":{"editable":true}}

$ find ~/.local/share/uv/tools/color-scheme-generator -name "*.pth" -exec cat {} \;
/home/inumaki/Development/dotfiles-v3/src/shared/config-assembler-engine/src
/home/inumaki/Development/dotfiles-v3/src/shared/oci-runtime/src
/home/inumaki/Development/dotfiles-v3/src/shared/cli-output/src
```
The same pattern was observed for `dotfiles-runtime` (`src/shared/cli-output` editable),
`icon-templates-renderer` (`cli-output`, `config-assembler-engine` editable), and
`wallpaper-effects-generator` (`cli-output`, `config-assembler-engine`, `oci-runtime` editable).

Claim: the container-image build uses the **whole dotfiles repo root** as build context and
requires the `src/cli-tools` + `src/shared` layout to be present.

`Evidence:`

- `src/shared/oci-runtime/src/oci_runtime/source_locator.py:3-21` says the image build needs
  `src/cli-tools/...` and `src/shared/...` as the `docker build`/`podman build` context.
- `source_locator.py:37-39`:
  ```python
  # The monorepo layout marker: a repo root contains both `src/cli-tools` and
  # `src/shared` as directories.
  _REPO_MARKER_DIRS = ("src", "cli-tools"), ("src", "shared")
  ```
- `source_locator.py:109-144` resolves in order `override` (`--source-root`) → env var
  (`CSG_SOURCE_ROOT` / `WEG_SOURCE_ROOT`) → PEP 610 `direct_url.json` → package walk, then
  raises `SourceRootNotFoundError` if no candidate has the marker.
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/install_cmd.py:63-66`
  passes `override=source_root` into `resolve_source_root`.
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/install.py:59-62`
  does the same with `WEG_SOURCE_ROOT`.
- The Dockerfiles `COPY` the repo-relative layout directly:
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base:3-7`
    ```dockerfile
    COPY src/cli-tools/color-scheme-generator /app/csg
    COPY src/shared/config-assembler-engine /app/config-assembler-engine
    COPY src/shared/oci-runtime /app/oci-runtime
    COPY src/shared/cli-output /app/cli-output
    ```
  - `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick:9-12`
    ```dockerfile
    COPY src/shared/config-assembler-engine /app/shared/config-assembler-engine
    COPY src/shared/oci-runtime /app/shared/oci-runtime
    COPY src/shared/cli-output /app/shared/cli-output
    COPY src/cli-tools/wallpaper-effects-generator /app/wallpaper-effects-generator
    ```

Claim: an external checkout that lacks `src/cli-tools` + `src/shared` is not recognized as a
source root by the marker check. Resolution then falls through to the PEP 610/package candidates;
in an external install those also lack the marker. Executed proof used a temp tree containing only
`src/cli-tools/color-scheme-generator` and a package name that is not installed (to remove the
host fallback):

```
$ uv run --directory src/cli-tools/color-scheme-generator python -c "
from pathlib import Path
from oci_runtime.source_locator import resolve_source_root, _repo_root_from_candidate, SourceRootNotFoundError
ext = Path('/tmp/opencode/s2-ext')
print('marker on external layout:', _repo_root_from_candidate(ext))
try:
    resolve_source_root(package='not_installed_pkg_xyz', override=ext)
except SourceRootNotFoundError as e:
    print('SourceRootNotFoundError:', e)
"
marker on external layout: None
SourceRootNotFoundError: Cannot locate the 'not_installed_pkg_xyz' source repo to use as a container build context.
EXIT=0
```

Note: when the package **is** installed from a checkout, `resolve_source_root` falls through to
`direct_url`/package candidates even when the explicit override lacks the marker; that is why the
first probe on this host returned the worktree root with `source='direct_url'` instead of raising.

`Evidence:` executed probe output:
```
SourceRoot(root=PosixPath('/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit'), source='direct_url')
```

---

## 3. The `verify` role — every assertion touching the CLI tools

Claim: the role's header states an explicit invariant: it references only machine locations, never
the repo checkout.

`Evidence:` `src/provisioning/ansible/roles/verify/tasks/main.yml:45-48`:
```
# Machine, not repo (the core invariant): NOTHING here references the repo
# checkout (no playbook_dir / repo-root var). The gate must never go green
# because the repo still exists while the machine is unprovisioned.
```

Claim: `verify_cli_tools` is exactly `csg`, `weg`, `itr` — `dotfiles-runtime` is **not** in this
list.

`Evidence:` `src/provisioning/ansible/roles/verify/vars/main.yml:213-219`:
```yaml
# verify_cli_tools: the uv-tool-installed CLIs on PATH (criterion 3). `itr` IS
#   the icon-renderer console script (no separate binary), mirror of
#   cli_tools.cli_tools.
verify_cli_tools:
  - csg
  - weg
  - itr
```
`grep -n "dotfiles-runtime" src/provisioning/ansible/roles/verify/tasks/main.yml` returns only
comment/fail-message lines (`728`, `750`, `1777`); there is no stat/PATH assertion for it in
`verify`.

Claim: `verify_cli_bin_dir` is a second, independently written mirror of `cli_tools_bin_dir`.

`Evidence:` `src/provisioning/ansible/roles/verify/vars/main.yml:323-330`:
```yaml
# verify_cli_bin_dir: the uv bin dir to prepend to PATH — mirror of
#   cli_tools_bin_dir exactly. The CLIs land here via `uv tool install`
#   ($UV_TOOL_BIN_DIR -> $XDG_BIN_HOME -> $HOME/.local/bin); ...
verify_cli_bin_dir: >-
  {{ ansible_facts.env.UV_TOOL_BIN_DIR
     | default(ansible_facts.env.XDG_BIN_HOME | default(ansible_facts.env.HOME + '/.local/bin', true), true) }}
```

Claim: the criterion-3 assertion is `command -v` over the three names with that bin dir prepended;
it checks rc == 0 and non-empty stdout.

`Evidence:` `src/provisioning/ansible/roles/verify/tasks/main.yml:381-401`:
```yaml
- name: Check CLI tools on PATH
  ansible.builtin.shell: "command -v {{ item }}"
  loop: "{{ verify_cli_tools }}"
  register: verify_cli_tool_checks
  ...
  environment:
    PATH: "{{ verify_cli_bin_dir }}:{{ ansible_facts.env.PATH }}"
  when: not ansible_check_mode

- name: Assert CLI tools are on PATH
  ansible.builtin.assert:
    that:
      - verify_cli_tool_checks.results | selectattr('rc', 'equalto', 0) | list | length == verify_cli_tools | length
      - verify_cli_tool_checks.results | map(attribute='stdout') | reject('equalto', '') | list | length == verify_cli_tools | length
```
The loop interpolates each name into a shell string, so names are regex-validated at `:141-150`.

Claim: criterion 5 runs three CLI commands against the rendered settings and asserts rc == 0. The
`csg` half is documented as a weak gate because `csg info` can exit 0 on a parse-broken file.

`Evidence:` `src/provisioning/ansible/roles/verify/tasks/main.yml:836-903`; the three commands are
`csg info --config ...` (`:848-860`), `weg info --config ...` (`:862-875`), and
`itr list <install>/icon-mappings/icons.yaml --config ...` (`:877-890`); the assert is at
`:892-903`.

Claim: before those commands, `verify` stats the three rendered settings files and asserts they
are regular files. This addresses the tools' config destinations, not their binaries.

`Evidence:` `src/provisioning/ansible/roles/verify/vars/main.yml:338-341` lists the three dests
(`csg`, `weg`, `itr`); `src/provisioning/ansible/roles/verify/tasks/main.yml:754-768` stats each
`item.dest` and asserts `stat.isreg` for all three. The spine-target extraction that follows reads
`verify_settings_spine_keys` from the same files (`tasks/main.yml:779-830`).

Claim: `verify` has **no** symlink/pin assertion for `csg`, `weg`, `itr`, or `dotfiles-runtime`.
The only symlink+pin assertions in the role are for the external `ags-apps` apps (see §5).

`Evidence:` `grep -n "islnk\|command -v\|cli_bin_dir" src/provisioning/ansible/roles/verify/tasks/main.yml`
shows `islnk` only at `959, 1022, 1025, 1070, 1114, 1162, 1196, 1238, 1284, 1330, 1374, 1411` —
all `ags-*` unit/link checks or consumer links, none for the uv-installed CLIs.

Claim: `verify_bin_scripts` does assert the existence (not symlink target) of three launchers in
the same bin dir: `toggle-touchpad`, `capture-ui`, `rofi-ui`.

`Evidence:` `src/provisioning/ansible/roles/verify/vars/main.yml:59-72`; assertion tasks at
`tasks/main.yml:616-630` (`selectattr('stat.exists')`).

Claim: downstream roles assert the `dotfiles-runtime` binary by path, not `verify`.

`Evidence:`

- `src/provisioning/ansible/roles/runtime_daemon/vars/main.yml:3-9` repeats the uv bin-dir
  resolution; `runtime_daemon/tasks/main.yml:34-47` stats
  `{{ runtime_daemon_bin_dir }}/dotfiles-runtime` and asserts `stat.exists`.
- `src/provisioning/ansible/roles/runtime_clipboard/vars/main.yml:3-9` repeats it;
  `runtime_clipboard/tasks/main.yml:31-44` stats and asserts the same binary in its bin dir.
- The systemd templates execute the same absolute path:
  `runtime_daemon/templates/dotfiles-runtime-daemon.service.j2:30` and
  `runtime_clipboard/templates/dotfiles-runtime-clipboard.service.j2:19`.

---

## 4. `scripts/deploy-coverage.py`

### 4.1 What it asserts about CLI tools today

Claim: the script contains exactly one constant named for the `cli_tools` role
(`CLI_TOOLS_ROLE_TASKS`) and one assertion that reads that tasks file. That assertion is only a
**negative** check about the retired capture-tool backend — it does not assert any
`csg`/`weg`/`itr`/`dotfiles-runtime` source path.

`Evidence:`

```
$ grep -n "cli_tools\|src/cli-tools\|src/shared" scripts/deploy-coverage.py
209:CLI_TOOLS_ROLE_TASKS = "src/provisioning/ansible/roles/cli_tools/tasks/main.yml"
819:    # The retired copy task lived in cli_tools; a stale src reference would
```
No `src/cli-tools` or `src/shared` match exists in the file.

The assertion body (`scripts/deploy-coverage.py:819-829`):
```python
# The retired copy task lived in cli_tools; a stale src reference would
# resurrect the split (an old backend from this checkout installed over the
# unit's pinned one).
cli_tasks = root / CLI_TOOLS_ROLE_TASKS
if not cli_tasks.is_file():
    raise ValueError(f"{CLI_TOOLS_ROLE_TASKS} is missing")
if RETIRED_CAPTURE_TOOL_DIR in cli_tasks.read_text():
    raise ValueError(
        f"{CLI_TOOLS_ROLE_TASKS} still references {RETIRED_CAPTURE_TOOL_DIR} — "
        f"the backend is installed from the unit by the ags_apps role"
    )
```
`RETIRED_CAPTURE_TOOL_DIR = "src/gui-tools/capture-tool"` (`:205`). So the assertion is:
the `cli_tools` tasks file must exist and must not mention the retired capture-tool dir.

Claim: `deploy-coverage` does **not** assert the CLI-tool install shape (no check for
`uv tool install`, no check for `cli_tools` entries, no check for the `--source-root` path). The
rest of the gate is about `ags-platform`/`ags-apps` units and the retired per-file bridges.

`Evidence:` `scripts/deploy-coverage.py:1333-1365` calls the `ags`-related assertions only;
`main()` prints the external units at `:1381-1427`. Full run below.

### 4.2 Invocation and current result

Claim: the Makefile target runs it through the provisioning project so PyYAML is importable.

`Evidence:` `Makefile:253-254`:
```make
deploy-coverage:
	uv run --directory src/provisioning python ../../scripts/deploy-coverage.py
```
It is in `GATES` (`Makefile:48-49`) and in CI (`.github/workflows/gates.yml:91-98`).

Claim: the gate passes today.

`Evidence:` executed in the worktree:
```
$ make deploy-coverage
uv run --directory src/provisioning python ../../scripts/deploy-coverage.py
deploy-coverage: NOTE — dotfiles/config/ags/app.tsx absent (bridge retired); the closure is not computed
deploy-coverage: per-file non-bar sources in the manifest: 0
...
deploy-coverage: external 'capture-tool' app — pinned unit subdir + live-capture link provisioned; no per-file gui_tools source remains and the Python backend is linked from the unit into the user bin dir (not a per-file deploy)
...
deploy-coverage: PASS -- the retired bar + hypr-pano + notifications + capture-tool + wallpaper-selector + icme + btop-theme-studio bridges carry no per-file deploy source and the external units are provisioned
EXIT=0
```
(`make` also printed duplicate-recipe warnings for unrelated VM/dev targets; exit remained 0.)

---

## 5. The working precedent: `roles/ags_apps` external pinned install

### 5.1 How the pinned unit is addressed

Claim: the unit is a **git tag**, cloned shallow and anonymously over HTTPS, into a
version-named directory under `<install>/ags-apps/`.

`Evidence:`

- `vars/main.yml:87-90`:
  ```yaml
  ags_apps_repo_url: https://github.com/RandomGenericUsername/ags-apps.git
  ```
- `vars/main.yml:92-102`: `ags_apps_version: v0.4.0` (the pin).
- `vars/main.yml:104-112`:
  ```yaml
  ags_apps_install_root: "{{ install_dir | trim }}/ags-apps"
  ags_apps_unit_dir: "{{ ags_apps_install_root }}/{{ ags_apps_version }}"
  ```
- `vars/main.yml:114-127`: `ags_apps_bar_dir = <unit>/bar`, marker
  `ags_apps_unit_marker = <bar>/app.tsx`, pin file `<install>/ags-apps/pinned`.
- `vars/main.yml:70-74` documents the monorepo deviation: the repo root is not the package; the
  bar is the `bar/` subdir.
- `tasks/main.yml:109-127`: a `stat` on the marker guards a `ansible.builtin.git` clone with
  `repo`, `dest`, `version: "{{ ags_apps_version }}"`, `depth: 1`, `single_branch: true`,
  `retries: 3`; the task is gated on `not exists` and `not ansible_check_mode`.
- `tasks/main.yml:129-133`: the clone's `.git` is removed (`file state: absent`).
- `tasks/main.yml:135-140`: the pin is recorded to a one-line file with `force: true`.

### 5.2 How the unit is deployed (whole-tree symlink, not per-file copy)

Claim: the live bar is a symlink to the unit's `bar/` subdir, with a migrate-then-symlink
discipline for a pre-existing real dir.

`Evidence:` `tasks/main.yml:161-243` (stat with `follow: false`, find children, remove empty dir,
move non-empty dir to a timestamped backup, then):
```yaml
- name: Deploy the unit's bar as the live bar
  ansible.builtin.file:
    src: "{{ ags_apps_bar_dir }}"
    dest: "{{ ags_apps_live_bar_link }}"
    state: link
    force: true
```
`vars/main.yml:136-141` defines `ags_apps_live_bar_link: {{ ags_apps_spine_config_dir }}/ags`.

Claim: the unit's Python backend is installed as a **bin-dir symlink**, not a copy.

`Evidence:` `tasks/main.yml:499-510`:
```yaml
- name: Ensure the capture-tool CLI bin dir exists
  ansible.builtin.file:
    path: "{{ ags_apps_bin_dir | trim }}"
    state: directory
    mode: "0755"

- name: Install the unit's capture-tool backend as the CLI entry point
  ansible.builtin.file:
    src: "{{ ags_apps_capture_tool_backend }}"
    dest: "{{ ags_apps_capture_tool_bin_link }}"
    state: link
    force: true
```
`vars/main.yml:190-224` defines:
```yaml
ags_apps_capture_tool_dir: "{{ ags_apps_unit_dir }}/capture-tool"
ags_apps_bin_dir: >-
  {{ ansible_facts.env.UV_TOOL_BIN_DIR
     | default(ansible_facts.env.XDG_BIN_HOME | default(ansible_facts.env.HOME + '/.local/bin', true), true) }}
ags_apps_capture_tool_backend: "{{ ags_apps_capture_tool_dir }}/bin/capture-tool"
ags_apps_capture_tool_bin_link: "{{ ags_apps_bin_dir | trim }}/capture-tool"
```
`ags_apps_bin_dir` is an exact mirror of `cli_tools_bin_dir`; the comment at `:200-205` says so
and says a structural test locks the parity.

Claim: the `capture-tool` CLI is then verified on PATH in the same role.

`Evidence:` `tasks/main.yml:512-523`:
```yaml
- name: Verify capture-tool is on PATH
  ansible.builtin.shell: "command -v capture-tool"
  environment:
    PATH: "{{ ags_apps_bin_dir | trim }}:{{ ansible_facts.env.PATH }}"
  changed_when: false
  when: not ansible_check_mode
```

### 5.3 The platform resolution shortcut

Claim: because esbuild realpaths the live link, the bar unit needs a `node_modules/ags-platform`
shortcut **inside the unit**, in addition to the shared-ancestor shortcut under
`<install>/config/node_modules`.

`Evidence:`

- `vars/main.yml:57-67` explains the realpath problem.
- `vars/main.yml:314-336`:
  ```yaml
  ags_apps_platform_version: v0.2.0
  ags_apps_platform_unit_dir: "{{ install_dir | trim }}/ags-platform/{{ ags_apps_platform_version }}"
  ags_apps_resolution_dir: "{{ ags_apps_unit_dir }}/node_modules"
  ags_apps_resolution_shortcut: "{{ ags_apps_resolution_dir }}/ags-platform"
  ```
- `tasks/main.yml:148-159`:
  ```yaml
  - name: Ensure the per-unit node_modules dir exists
    ansible.builtin.file:
      path: "{{ ags_apps_resolution_dir }}"
      state: directory
      mode: "0755"

  - name: Point the per-unit resolution shortcut at the pinned platform unit
    ansible.builtin.file:
      src: "{{ ags_apps_platform_unit_dir }}"
      dest: "{{ ags_apps_resolution_shortcut }}"
      state: link
      force: true
  ```
- The sibling `ags_platform` role installs the unit itself and the `${install}/config/node_modules/ags-platform`
  shared-ancestor shortcut (`roles/ags_platform/vars/main.yml:23-66`,
  `roles/ags_platform/tasks/main.yml:49-87`).

### 5.4 How `verify` mirrors the pin

Claim: `verify` mirrors the role's pin and path layout with independent literals, then asserts
that the live link's target **contains the pinned tag** and resolves.

`Evidence:`

- `verify/vars/main.yml:495-514`:
  ```yaml
  verify_ags_apps_version: v0.4.0
  verify_ags_apps_platform_version: v0.2.0
  verify_ags_apps_unit_dir: "{{ install_dir | trim }}/ags-apps/{{ verify_ags_apps_version }}"
  verify_ags_apps_bar_dir: "{{ verify_ags_apps_unit_dir }}/bar"
  verify_ags_apps_pin_file: "{{ install_dir | trim }}/ags-apps/pinned"
  verify_ags_apps_live_bar_link: "{{ install_dir | trim }}/config/ags"
  verify_ags_apps_resolution_shortcut: "{{ verify_ags_apps_unit_dir }}/node_modules/ags-platform"
  ```
- `verify/tasks/main.yml:983-1038` stats the unit dir, the pin file, every representative unit
  file, the live link with `follow: false`, the live link with `follow: true`, the resolution
  shortcut with `follow: false`, and with `follow: true`; the assertion (`:1013-1027`) includes:
  ```yaml
  - verify_ags_apps_unit_checks.results[0].stat.isdir
  - verify_ags_apps_unit_checks.results[1].stat.isreg
  - verify_ags_apps_live_bar_check.stat.islnk
  - verify_ags_apps_live_bar_check.stat.lnk_target is search(verify_ags_apps_version)
  - verify_ags_apps_live_bar_resolve_check.stat.isdir
  - verify_ags_apps_resolution_check.stat.islnk
  - verify_ags_apps_resolution_check.stat.lnk_target is search(verify_ags_apps_platform_version)
  - verify_ags_apps_resolution_resolve_check.stat.isdir
  ```
- The CLI half mirrors the same shape (`verify/vars/main.yml:596-598`,
  `verify/tasks/main.yml:1175-1205`):
  ```yaml
  verify_ags_apps_capture_tool_bin_link: "{{ verify_cli_bin_dir | trim }}/capture-tool"
  ...
  - verify_capture_tool_bin_link_check.stat.islnk
  - verify_capture_tool_bin_link_check.stat.lnk_target is search(verify_ags_apps_version)
  - verify_capture_tool_backend_check.stat.isreg
  ```
- The role/verify pins were observed to be equal:
  ```
  $ grep -E '^ags_apps_version:' src/provisioning/ansible/roles/ags_apps/vars/main.yml
  ags_apps_version: v0.4.0
  $ grep -E '^verify_ags_apps_version:' src/provisioning/ansible/roles/verify/vars/main.yml
  verify_ags_apps_version: v0.4.0
  $ grep -E '^ags_apps_platform_version:' src/provisioning/ansible/roles/ags_apps/vars/main.yml
  ags_apps_platform_version: v0.2.0
  $ grep -E '^verify_ags_apps_platform_version:' src/provisioning/ansible/roles/verify/vars/main.yml
  verify_ags_apps_platform_version: v0.2.0
  ```

Claim: `deploy-coverage` also asserts the repo-side shape of this precedent: pin present and
`v`-prefixed, versioned unit dir, `bar` subdir, live link ending in `/ags`, per-unit
`node_modules/ags-platform` shortcut, and the presence of the clone/link variables in the tasks.

`Evidence:` `scripts/deploy-coverage.py:480-586` (the `assert_bar_provisioning` body quoted
above), and the capture-tool half at `:864-941`.

---

## 6. Gates that enumerate CLI tool sources

Claim: **no gate in `scripts/`, the `Makefile`, or `.github/workflows/gates.yml` enumerates the
CLI tool package sources.** The only CLI-related checks are in `deploy-coverage` (the retired
capture-tool reference and the `ags-apps` capture-tool backend symlink shape); none of them
enumerate the four `cli-tools` sources.

`Evidence:`

```
$ grep -rn "cli_tools\|cli-tools\|csg\|weg\|itr\|dotfiles-runtime" scripts/ | grep -v deploy-coverage.py
scripts/ansible-embedded-template-lint.py:40:``packages.yaml``, ``roles/verify/tasks/main.yml``, ``roles/cli_tools/tasks/
scripts/sync-icons-manifest.py:9:  MEASURED 2026-10-05: `dotfiles-runtime icons regenerate` re-renders every
scripts/sync-icons-manifest.py:11:  does not touch icons.json. `dotfiles-runtime reconcile` does not either.

$ grep -n "cli_tools\|cli-tools\|csg\|weg\|itr" Makefile .github/workflows/gates.yml
Makefile:44:# cli_tools) and the provisioning SHAPE, which `deploy-coverage` asserts.
```
The only `Makefile` match is a comment; the workflow has no match.
- `scripts/ansible-embedded-template-lint.py` only *names* `roles/cli_tools/tasks/main.yml` in its
  docstring as a place where `fail_msg` text legitimately contains `{{ }}`; it parses the Ansible
  tree for nested templates and never enumerates install sources
  (`scripts/ansible-embedded-template-lint.py:1-48, 55-70`).
- `scripts/sync-icons-manifest.py` mentions `dotfiles-runtime` only as documentation of what does
  **not** update `icons.json`; it is not a gate.
- `scripts/ci-gates-parity.py` compares `Makefile` `GATES`/`gates-ci` with workflow job keys. It
  parses no CLI data:
  - `MAKEFILE = "Makefile"`, `WORKFLOW = ".github/workflows/gates.yml"` (`:68-69`).
  - `parse_makefile_gates` reads only the `GATES` variable and the `gates-ci` `filter-out`
    (`:130-171`).
  - `parse_workflow_jobs` reads only `jobs:` keys (`:173-188`).
  - `check()` compares the two name sets modulo `RENAMES` / `CI_ONLY_EXEMPT` /
    `CI_EXCLUDED_GATES` (`:190-294`).
- `scripts/contract-pin-check.py` addresses the vendored contract files under `src/runtime` only
  (`:60-67`); it knows nothing about `csg`/`weg`/`itr`.
- `per-app-drift-symbol-suites` is intentionally empty (`Makefile:138`, `:140-150`).
- `deploy-coverage` is covered in §4; its only CLI statement is the negative capture-tool one.

Claim: the `Makefile`'s authoritative gate set is five targets, none of which runs the provisioning
pytest suite where the CLI parity test lives.

`Evidence:` `Makefile:48-49`; `make -n gates-ci` output (exit 0) lists only
`contracts-check`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`, and the
no-op `per-app-drift-symbol-suites`.

---

## 7. Gates executed for this spike

All commands were run from `/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit`.

| Command | Result |
|---|---|
| `make deploy-coverage` | exit 0; `deploy-coverage: PASS -- the retired bar + hypr-pano + notifications + capture-tool + wallpaper-selector + icme + btop-theme-studio bridges carry no per-file deploy source and the external units are provisioned` |
| `make ci-gates-parity` | exit 0; `ci-gates-parity: PASS -- every gates-ci target has a CI job and every CI job is a gates-ci target (modulo the declared tables)` |
| `make contract-pin-check` | exit 0; `contract-pin-check: PASS — vendored bindings match /home/inumaki/Development/contracts/generated at pin dbdc5b8` |
| `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py -q` | exit 0; `43 passed in 2.25s` |
| `uv run --directory src/provisioning pytest "tests/unit/test_cli_tools_role.py::TestCliToolsVars::test_cli_tools_parity_with_manifest" -q` | exit 0; `1 passed in 0.02s` |
| `uv run --directory src/provisioning pytest tests/unit/adapters/test_yaml_manifest_reader.py -q` | exit 0; `45 passed in 0.09s` |

`ci-gates-parity` key output:
```
ci-gates-parity: authoritative gates-ci set (5): contracts-check ansible-embedded-template-lint deploy-coverage ci-gates-parity per-app-drift-symbol-suites
ci-gates-parity: workflow jobs (5): contracts ansible-embedded-template-lint deploy-coverage ci-gates-parity per-app-drift-symbol-suites
ci-gates-parity: declared gates-ci exclusions (0): (none)
ci-gates-parity: declared CI-only jobs (0): (none)
ci-gates-parity: declared self-hosted gates (0): (none)
ci-gates-parity: declared renames (1): contracts-check->contracts
ci-gates-parity: PASS -- every gates-ci target has a CI job and every CI job is a gates-ci target (modulo the declared tables)
```

Not run, and why:

- `make vm-verify` / `make vm-fresh` — require an Incus VM (`Makefile:320-341` → `./dev/vm ...`).
  `command -v incus` → `incus: not on PATH`; no VM was created for this spike.
- `ansible-playbook --syntax-check` directly — `command -v ansible-playbook` →
  `ansible-playbook: not on PATH`. The unit suite contains a syntax-check test that skips when the
  binary is absent (`src/provisioning/tests/unit/test_cli_tools_role.py:737-757`).

---

## Breaking references if tools move

The list below is limited to references that address a **local tool package path** or a **local
tool install path**. Each item names the current address and the exact failure mode. Items marked
**(conditional)** break only if the external install does not preserve the current console-script
name or uv bin-dir convention.

### A. Install addressing (hard breaks)

1. `dotfiles/provisioning/cli-tools.yaml:9-16` — `source:` values are
   `src/cli-tools/{color-scheme-generator,wallpaper-effects-generator,icon-templates-renderer}` and
   `src/runtime`. If those dirs leave the repo, the manifest names nonexistent paths. The YAML
   reader still accepts the file (schema is syntax-only), but the parity test and any tool that
   resolves `source` see dead paths.
2. `src/provisioning/ansible/roles/cli_tools/vars/main.yml:57-60` — the role's mirrored
   `source` values. These are the values the install task interpolates, so the install target
   becomes a nonexistent directory.
3. `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:99` — first install:
   `uv tool install --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'`. With the source
   gone, `uv` cannot resolve the project; the `creates:` guard at `:101` can skip this task if an
   old console script still exists, and then the force-upgrade task at `:118` fails.
4. `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:118` — force upgrade:
   `uv tool install --force --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'` runs on
   every bootstrap and has no `when:` guard other than check mode. It fails every run once the
   source path is gone.
5. `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:331-336` — image build invokes
   `{{ item.name }} install ... --source-root "{{ cli_tools_repo_root }}"`. The CLI's resolver
   requires the build-context root to contain both `src/cli-tools` and `src/shared`
   (`src/shared/oci-runtime/src/oci_runtime/source_locator.py:37-39`), so a checkout without that
   layout is rejected with `SourceRootNotFoundError` (executed proof in §2.3). **(conditional)**
   The task also assumes the binary keeps the `<name> install` subcommand and the image names the
   settings templates expect (`settings/templates/csg-settings.toml.j2:24-26`,
   `weg-settings.toml.j2:28-30`).
6. `src/provisioning/ansible/roles/assets/vars/main.yml:72` — `csg-templates` asset source:
   `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/`. If
   `csg` moves, the assets role has nothing to synchronize for CSG's template catalog.
7. `src/provisioning/ansible/roles/assets/tasks/main.yml:99-103` — the `synchronize` loop uses
   `{{ assets_repo_root }}/{{ item.source }}`, so item 6 fails at copy time.
8. `dotfiles/provisioning/assets.yaml:20` — the manifest mirror of the same `csg-templates`
   source; `test_assets_role.py:519-557` asserts the role and manifest sources are identical.
9. `src/provisioning/ansible/playbooks/runtime-seed.yaml:45-52` — the seed runs
   `uv run --directory "{{ playbook_dir }}/../../../../src/runtime" dotfiles-runtime wallpaper set`.
   If `dotfiles-runtime` moves, this command's `--directory` no longer exists.
10. `src/cli-tools/color-scheme-generator/pyproject.toml:39-42`,
    `src/cli-tools/wallpaper-effects-generator/pyproject.toml:26-29`,
    `src/cli-tools/icon-templates-renderer/pyproject.toml:36-38` — each declares
    `../../shared/{cli-output,config-assembler-engine,oci-runtime}` as editable path sources.
    Moving a tool alone (without the shared libraries at the same relative location) breaks that
    resolution. The locks record the same relative paths:
    `color-scheme-generator/uv.lock:26,93,233`;
    `wallpaper-effects-generator/uv.lock:26,49,169`;
    `icon-templates-renderer/uv.lock:26,49`.
11. `src/runtime/pyproject.toml:24-25` — `cli-output = { path = "../shared/cli-output", editable = true }`;
    `src/runtime/uv.lock:85` repeats it. Moving `dotfiles-runtime` alone breaks the relative path.
12. `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base:3-7`
    and `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick:9-12`
    — both `COPY` repo-relative `src/cli-tools/...` and `src/shared/...` paths. They only build if
    the build context is the current monorepo root (§2.3 item 5).
13. `src/shared/oci-runtime/src/oci_runtime/source_locator.py:37-39` — the hard-coded marker
    `("src", "cli-tools"), ("src", "shared")`. An external repo that does not reproduce this
    two-directory layout is not recognized as a source root.
14. `Makefile:14` — `contracts-check` runs
    `uv run --directory src/runtime pytest tests/unit/test_contract_schema_conformance.py ...`.
    If `dotfiles-runtime` moves out of `src/runtime`, this gate's working directory and test files
    are gone.
15. `scripts/contract-pin-check.py:63-67` — `PY_VENDORED`, `SCHEMA_VENDORED`, `PIN_FILE` are all
    under `src/runtime/src/runtime/...`. If the runtime moves, the pin gate reports missing
    vendored copies.
16. `src/provisioning/tests/unit/test_cli_tools_role.py:330-347` asserts every install command
    uses `{{ cli_tools_repo_root }}/{{ item.source }}` and never an absolute literal; `:441-449`
    asserts `--source-root == {{ cli_tools_repo_root }}`; `:692-701` asserts exact parity with the
    manifest. Any manifest/role change that is not mirrored fails these tests.
17. `src/provisioning/tests/unit/test_assets_role.py:519-557` — asserts `assets_copies` sources
    exactly equal `assets.yaml` sources (normalizing the trailing `/`). A moved `csg-templates`
    source that is changed in one file only fails this test.

### B. Runtime/consumer addressing (hard or conditional)

18. `src/provisioning/ansible/roles/assets/tasks/main.yml:50-66` and `:125-134` — the assets role
    runs `command -v weg` and `weg dump-effects --output <install>/config/weg/effects.yaml`.
    **(conditional)** This breaks if the external `weg` is not installed under the same console
    name into `assets_weg_bin_dir` (`assets/vars/main.yml:21-30`, the same uv-resolution
    expression as `cli_tools_bin_dir`).
19. `src/provisioning/ansible/roles/runtime_daemon/vars/main.yml:7-9` +
    `runtime_daemon/tasks/main.yml:34-47` — stats
    `{{ runtime_daemon_bin_dir }}/dotfiles-runtime` and fails if absent; the systemd unit's
    `ExecStart` is that same path (`runtime_daemon/templates/dotfiles-runtime-daemon.service.j2:30`).
    **(conditional)** Breaks if an external runtime install lands anywhere other than the uv bin
    dir expression.
20. `src/provisioning/ansible/roles/runtime_clipboard/vars/main.yml:7-9` +
    `runtime_clipboard/tasks/main.yml:31-44` +
    `runtime_clipboard/templates/dotfiles-runtime-clipboard.service.j2:19` — the same path
    assertion and `ExecStart` for the clipboard watcher. Same conditional break.
21. `src/provisioning/ansible/roles/verify/tasks/main.yml:381-401` — `command -v csg|weg|itr`
    with `verify_cli_bin_dir` prepended. **(conditional)** Breaks if the external install changes
    a console-script name or installs outside the uv bin-dir convention. `verify` has no symlink
    or pin assertion to catch a wrong-tag install; it only proves `command -v` resolves.
22. `src/provisioning/ansible/roles/verify/tasks/main.yml:848-903` — runs `csg info`,
    `weg info`, and `itr list` against rendered settings and asserts all three rc == 0.
    **(conditional)** Requires the moved tools to keep those subcommands and CLI flags
    (`info --config`, `list <icons.yaml> --config`) and to parse the same settings schema.
23. `src/provisioning/ansible/roles/verify/vars/main.yml:216-219` and
    `src/provisioning/tests/unit/test_verify_role.py:1963-1965` — pin the exact list
    `[csg, weg, itr]`. Adding/removing/renaming a tool in the manifest without updating this list
    fails the test; the runtime list is not checked here at all.

### C. Not broken by a tool-source move

24. `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:41-42` — `gloview-activate` is copied
    from `dotfiles/provisioning/scripts/`, not from a CLI package. Unaffected by moving the four
    tools.
25. `src/provisioning/ansible/roles/cli_tools/templates/icon-color-mapping-editor.j2:22` and
    `btop-theme-studio.j2:22` — `REPO_ROOT="{{ cli_tools_repo_root }}"` is a checkout hint for
    GUI apps, not a CLI package path. Unaffected by moving `csg`/`weg`/`itr`/`dotfiles-runtime`
    (the GUI apps are in the `ags-apps` unit).
26. `dotfiles/config/zsh/.zshrc.j2:1-9` — only adds `$HOME/.local/bin` to PATH. It does not
    address a package source; **(conditional)** it fails to expose the tools at login if an
    external install places them outside `$HOME/.local/bin` and `UV_TOOL_BIN_DIR`/`XDG_BIN_HOME`
    are not set.
27. The runtime adapters invoke the tools by **name on PATH**, not by repo path:
    `src/runtime/src/runtime/adapters/csg_adapter.py:140-155`,
    `src/runtime/src/runtime/adapters/weg_adapter.py:207`,
    `src/runtime/src/runtime/adapters/itr_adapter.py:131` use `shutil.which(...)`. This part
    survives an external install as long as the console-script names remain.
28. `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2:20-27` and
    `weg-settings.toml.j2:24-31` render `[runtime] mode = "container"`, the declared engine, and
    image names/tags (`csg`/`latest`, `weg`/`latest`). These are not source paths; **(conditional)**
    they break only if the external package's `install` command stops building images with those
    names/tags (the `cli_tools_image_builds` list at `vars/main.yml:46-48` is the only build
    driver).
29. `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:144-173` — Codex shadow cleanup in
    the bin dir. Unaffected by moving the four tools.

---

## Open questions

1. **Manifest address vocabulary.** `cli-tools.yaml` has no `repo`, `url`, or `ref` key, and the
   reader schema allows only `name`/`source`/`version`
   (`yaml_manifest_reader.py:41-44`). It is unknown what the intended address form is for an
   external pinned install (git URL + tag? wheel index + version? a local pinned unit like
   `ags-apps`?).
2. **Do the three shared libraries move too?** All four packages resolve
   `cli-output`/`config-assembler-engine`/`oci-runtime` through `../../shared/*` editable paths
   (§2.3). It is unknown whether those libraries become published packages, move into each tool
   repo, or stay in `dotfiles-v3`.
3. **Container build context after a move.** `resolve_source_root` requires the context root to
   contain `src/cli-tools` and `src/shared`, and the Dockerfiles `COPY` those paths
   (`source_locator.py:37-39`; Dockerfiles above). It is unknown what the build context would be
   for an external pinned tool repo.
4. **Scope of `dotfiles-runtime`.** It is one of the four `cli-tools.yaml` entries, but it is also
   the subject of `Makefile:14` (`contracts-check`) and the vendored contract paths in
   `scripts/contract-pin-check.py:63-67`. It is not in `verify_cli_tools`
   (`verify/vars/main.yml:216-219`) and is not asserted by `verify`; only
   `runtime_daemon`/`runtime_clipboard` stat it. It is unknown whether "CLI tools move" includes
   `dotfiles-runtime`.
5. **Editable installs at runtime.** The host evidence shows the installed tool environments carry
   absolute `.pth` paths into the checkout's `src/shared/*` (§2.3). It is unknown whether that
   runtime dependency on the checkout path is intended, or whether a future install is expected to
   be self-contained (wheel/non-editable).
6. **Gate ownership.** No gate in `GATES` runs the `cli-tools` manifest/role parity test
   (`test_cli_tools_role.py:692-701`); it is only run manually. It is unknown which gate should own
   that check after an external move, or whether `deploy-coverage` is expected to grow a CLI-tools
   assertion (it currently only checks the retired capture-tool reference, §4).
7. **Verify depth for uv-installed CLIs.** `verify` asserts only `command -v` + parse gates for
   `csg`/`weg`/`itr`, with no symlink/pin check, while the `ags-apps` capture-tool CLI gets a
   symlink+target-tag+regular-file assertion (`verify/tasks/main.yml:1175-1205`). It is unknown
   whether that asymmetry is intentional.
8. **VM evidence.** No VM run was performed (`incus` is not on PATH), so the host-level
   `uv tool install` and `verify` behavior on a fresh machine is not established here.
   `Evidence: MISSING — run make vm-verify (requires Incus).`

---

## Verify

Reproduce every executable claim from the worktree root:

```bash
cd /home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit

# 1. Manifest + role mirror + parity test
sed -n '1,20p' dotfiles/provisioning/cli-tools.yaml
sed -n '50,60p' src/provisioning/ansible/roles/cli_tools/vars/main.yml
uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py -q
uv run --directory src/provisioning pytest \
  "tests/unit/test_cli_tools_role.py::TestCliToolsVars::test_cli_tools_parity_with_manifest" -q
uv run --directory src/provisioning pytest tests/unit/adapters/test_yaml_manifest_reader.py -q

# 2. Role addressing
grep -n "cli_tools_repo_root\|UV_TOOL_BIN_DIR\|uv tool install\|source-root\|command -v {{ item.name }}" \
  src/provisioning/ansible/roles/cli_tools/tasks/main.yml

# 3. Verify role
grep -n "verify_cli_tools\|verify_cli_bin_dir\|csg\|weg\|itr" \
  src/provisioning/ansible/roles/verify/vars/main.yml
sed -n '381,401p;848,903p' src/provisioning/ansible/roles/verify/tasks/main.yml

# 4. deploy-coverage: no CLI source assertions, and current PASS
grep -n "cli_tools\|src/cli-tools\|src/shared" scripts/deploy-coverage.py
make deploy-coverage; echo "EXIT=$?"

# 5. ags_apps precedent (pin, clone, symlink, verify mirror)
grep -n "ags_apps_repo_url\|ags_apps_version\|ags_apps_install_root\|ags_apps_unit_dir\|ags_apps_bar_dir\|ags_apps_live_bar_link\|ags_apps_resolution" \
  src/provisioning/ansible/roles/ags_apps/vars/main.yml
sed -n '109,140p;154,159p;238,243p;499,510p' \
  src/provisioning/ansible/roles/ags_apps/tasks/main.yml
sed -n '495,514p' src/provisioning/ansible/roles/verify/vars/main.yml
sed -n '983,1038p;1175,1205p' src/provisioning/ansible/roles/verify/tasks/main.yml
grep -n "ags_apps_version\|ags_apps_unit_dir\|ags_apps_live_bar_link\|ags_apps_resolution" \
  scripts/deploy-coverage.py | head -20

# 6. CI gate set (no CLI enumeration)
grep -rn "cli_tools\|cli-tools\|csg\|weg\|itr" scripts/ .github/workflows/gates.yml Makefile
make ci-gates-parity; echo "EXIT=$?"
make contract-pin-check; echo "EXIT=$?"

# 7. Package-side path dependencies and the external-layout probe
grep -n "tool.uv.sources" -A 5 src/cli-tools/*/pyproject.toml src/runtime/pyproject.toml
grep -n 'editable = "\.\./\.\./shared\|editable = "\.\./shared' \
  src/cli-tools/*/uv.lock src/runtime/uv.lock
sed -n '37,39p;109,144p' src/shared/oci-runtime/src/oci_runtime/source_locator.py
sed -n '1,8p' src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base

# external-layout probe: a tree with only src/cli-tools/<pkg> is not a source root
mkdir -p /tmp/opencode/s2-ext/src/cli-tools/color-scheme-generator
uv run --directory src/cli-tools/color-scheme-generator python -c "
from pathlib import Path
from oci_runtime.source_locator import resolve_source_root, _repo_root_from_candidate, SourceRootNotFoundError
ext = Path('/tmp/opencode/s2-ext')
print('marker on external layout:', _repo_root_from_candidate(ext))
try:
    resolve_source_root(package='not_installed_pkg_xyz', override=ext)
except SourceRootNotFoundError as e:
    print('SourceRootNotFoundError:', e)
"

# 8. Host-level proof of how uv resolved the tool envs (installed from this repo, not the worktree)
uv tool list
ls -la ~/.local/bin | grep -E "csg|weg|itr|dotfiles-runtime"
find ~/.local/share/uv/tools/color-scheme-generator -name direct_url.json -exec cat {} \;
find ~/.local/share/uv/tools/color-scheme-generator -name "*.pth" -exec cat {} \;

# 9. VM gate (not run for this spike; requires Incus)
command -v incus || echo "incus: not on PATH"
```

Expected results observed on 2026-10-19 in this worktree:

- `make deploy-coverage` → exit 0, `PASS`.
- `make ci-gates-parity` → exit 0, `PASS`.
- `make contract-pin-check` → exit 0, `PASS` at pin `dbdc5b8`.
- `test_cli_tools_role.py` → `43 passed`; the single parity test → `1 passed`;
  `test_yaml_manifest_reader.py` → `45 passed`.
