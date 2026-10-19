# S3 — CLI settings/config runtime resolution

**Type:** evidence-only spike. **Scope:** `dotfiles-v3` worktree
`/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit`, branch
`ticket/clirsplit-investigate-and-spine`, HEAD `fb94b64e`.
**Question:** how do `csg` / `weg` / `itr` resolve settings/config at runtime, and does
resolution depend on being inside this repository tree?

No recommendations appear in this document. Every claim is followed by an `Evidence:`
marker and the command output or `file:line` reference that produced it. Commands were run
from the worktree unless a different `cwd` is stated. Exit codes are the observed shell
exit codes.

---

## 0. Answer matrix (derived from the sections below)

| Tool | Priority order at runtime | Config filename | XDG subdir | Final fallback |
|---|---|---|---|---|
| `csg` | CLI `--config` → env → cwd traversal (3 parents) → XDG → package default | `settings.toml` | `color-scheme-generator` | `color_scheme_generator/defaults/settings.toml` inside the installed package |
| `weg` | CLI `--config` → env → cwd traversal (2 parents) → XDG → package default appended by `cli/main.py` | `settings.toml` | `weg` | `wallpaper_effects_generator/defaults/settings.toml` inside the installed package |
| `itr` | CLI `--config` → env → cwd traversal (2 parents) → XDG → package default | `settings.toml` | `itr` | `icon_templates_renderer/defaults/settings.toml` inside the installed package |

None of the three settings chains uses a repository-root marker. The only repo-root marker
in the inspected source is in `oci_runtime.source_locator`, which is used for container
build context, not settings (Section 6).

---

## 1. `src/shared/config-assembler-engine` — resolution strategies

All strategies implement `resolve(policy, explicit_path)` and are assembled by a composite
resolver that returns the **first** non-`None` result.

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/path_resolver.py:10-19
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath:
        for strategy in self._strategies:
            result = strategy.resolve(policy, explicit_path)
            if result is not None:
                return result
        raise PathResolutionError("No strategy found a config file")
```

### 1.1 `CliPathStrategy`

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/cli_path.py:10-21
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not explicit_path:
            return None
        path = Path(explicit_path).expanduser().resolve()
        check = path.is_file if self._kind == ResourceKind.FILE else path.is_dir
        if check():
            return ResolvedPath(path=path, source=PathSource.CLI_PATH, kind=self._kind)
        return None
```

- Takes the path handed in by the caller (`explicit_path`), expands `~`, resolves it.
- Returns `None` on empty/`None`, or when the path does not exist.
- No default path and no repo dependency.

`CliDirStrategy` is the same logic with `kind=DIRECTORY` (same file, lines 24-26).

### 1.2 `EnvPathStrategy`

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/env_path.py:12-25
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        env_key = f"{policy.env_prefix}_{self._var}"
        file_path = os.environ.get(env_key)
        if not file_path:
            return None
        path = Path(file_path).expanduser().resolve()
        check = path.is_file if self._kind == ResourceKind.FILE else path.is_dir
        if check():
            return ResolvedPath(path=path, source=PathSource.ENV_PATH, kind=self._kind)
        return None
```

- Env key is `"{policy.env_prefix}_{var}"`; default `var="CONFIG_FILE_PATH"` (line 8).
- For the three CLIs this yields `COLORSCHEME_CONFIG_FILE_PATH`,
  `WALLPAPER_CONFIG_FILE_PATH`, `ICON_RENDERER_CONFIG_FILE_PATH`.
- Path is taken from the environment verbatim (after `~` expansion); no repo relation.

### 1.3 `DirectoryTraversalStrategy` — no repository marker

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/directory.py:12-26
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        cwd = Path.cwd()
        for level in range(self._max_levels + 1):
            if level > 0 and level > len(cwd.parents):
                break
            check_dir = cwd.parents[level - 1] if level > 0 else cwd
            candidate = check_dir / self._filename
            check = candidate.is_file if self._kind == ResourceKind.FILE else candidate.is_dir
            if check():
                return ResolvedPath(path=candidate.resolve(), source=PathSource.DIRECTORY, kind=self._kind)
        return None
```

- Starts at `Path.cwd()` and checks `<dir>/<filename>` at cwd and up to `max_levels`
  ancestor directories.
- **The only marker is the filename itself** (`settings.toml` for all three CLIs). The
  strategy never looks for `.git`, `pyproject.toml`, or any repo-root sentinel. Grep for
  marker logic in this file returns no other names:

**Evidence:**
```
$ grep -n "marker\|\.git\|pyproject" src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/directory.py
(no output; exit 1)
```

- Because it is filename-based, it will match any ancestor `settings.toml` regardless of
  whether that ancestor is a repository (demonstrated in Section 5.4).

### 1.4 `XdgStrategy`

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/xdg.py:13-25
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not self._xdg_subdir:
            return None
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        candidate = xdg_home / self._xdg_subdir / self._filename
        check = candidate.is_file if self._kind == ResourceKind.FILE else candidate.is_dir
        if check():
            return ResolvedPath(path=candidate.resolve(), source=PathSource.XDG, kind=self._kind)
        return None
```

- `$XDG_CONFIG_HOME/<xdg_subdir>/<filename>`, falling back to `~/.config` only when
  `XDG_CONFIG_HOME` is unset.
- Reads XDG, not a "spine" variable. The spine becomes visible to this strategy through
  provisioning-created symlinks (Section 4).

### 1.5 `DefaultFileStrategy`

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/default_file.py:11-19
    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        check = self._path.is_file if self._kind == ResourceKind.FILE else self._path.is_dir
        if check():
            return ResolvedPath(path=self._path.resolve(), source=PathSource.DEFAULT, kind=self._kind)
        return None
```

- The path is supplied by the caller at construction time. There is no implicit location.
- In `csg` and `itr` the supplied path is an `importlib.resources` path inside the
  installed package (Section 2). In `weg` it is supplied by `cli/main.py` from
  `importlib.resources.files("wallpaper_effects_generator") / "defaults"`.
- It never points at the spine config dir.

### 1.6 Env section/key overrides

Overrides are read separately from file resolution:

**Evidence:**
```
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/env_reader.py:7-17
    SEPARATOR: ClassVar[str] = "__"

    def read(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix + self.SEPARATOR):
                continue
            config_key = key[len(prefix) + len(self.SEPARATOR) :].lower()
            result[config_key] = value
        return result
```

- Env overrides use `{PREFIX}__section__key` with `__` as separator; the matched prefix is
  the tool's `env_prefix`, not the config-file-path prefix.

---

## 2. Per-CLI wiring

### 2.1 `csg` (color-scheme-generator)

Factory:

**Evidence:**
```
src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py:67-68
def create_config_resolver() -> AssembledConfigResolver:
    return AssembledConfigResolver()
```

Resolver and exact priority list:

**Evidence:**
```
src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py:67-84
        strategies = [
            CliPathStrategy(kind=ResourceKind.FILE),
            EnvPathStrategy(kind=ResourceKind.FILE),
            DirectoryTraversalStrategy(filename="settings.toml", max_levels=3, kind=ResourceKind.FILE),
            XdgStrategy(xdg_subdir="color-scheme-generator", filename="settings.toml", kind=ResourceKind.FILE),
            DefaultFileStrategy(
                path=Path(resource_files("color_scheme_generator") / "defaults" / "settings.toml"),
                kind=ResourceKind.FILE,
            ),
        ]
        self._assembler = assembler or AssembleConfiguration(
            path_resolver=CompositePathResolver(strategies),
            parser=TomlConfigParser(),
            env_reader=OsEnvironmentReader(),
            validator=PydanticValidator(),
            coercer=PydanticTypeCoercer(),
        )
        self._policy = ResolutionPolicy(env_prefix="COLORSCHEME")
```

- Priority: CLI → env → traversal (`settings.toml`, 3 ancestors) → XDG
  (`~/.config/color-scheme-generator/settings.toml`) → packaged
  `color_scheme_generator/defaults/settings.toml`.
- Parser: TOML (`TomlConfigParser`).
- Env override prefix: `COLORSCHEME` (`COLORSCHEME__SECTION__KEY`).
- The help text states the same order:
  `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py:62-68`
  ("1. --config flag", "2. COLORSCHEME_CONFIG_FILE_PATH", "3. settings.toml in CWD or up
  to 3 parent levels", "4. XDG default", "5. Package-bundled defaults").
- `--config` is passed as `explicit_path` at
  `cli/main.py:175-177`, `cli/info_cmd.py:40-41`, `cli/show.py:35-36`,
  `cli/install_cmd.py:45`, `cli/uninstall_cmd.py:28`.
- Templates are resolved by a separate chain:
  `adapters/template_dir_resolver.py:16-30`
  (`CliDirStrategy` → `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` → `templates` dir traversal
  (3) → XDG `color-scheme-generator/templates` → packaged `defaults/templates`).

### 2.2 `weg` (wallpaper-effects-generator)

Factory:

**Evidence:**
```
src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py:68-71
def create_config_resolver(
    default_settings_path: Path | None = None,
) -> ConfigResolverPort:
    return AssembledConfigResolver(default_settings_path=default_settings_path)
```

Resolver and priority list:

**Evidence:**
```
src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/assembled_config_resolver.py:72-79
_STRATEGIES = [
    CliPathStrategy(kind=ResourceKind.FILE),
    EnvPathStrategy(kind=ResourceKind.FILE),
    DirectoryTraversalStrategy(
        filename=CONFIG_FILENAME, max_levels=CONFIG_TRAVERSAL_DEPTH, kind=ResourceKind.FILE
    ),
    XdgStrategy(xdg_subdir=CONFIG_XDG_SUBDIR, filename=CONFIG_FILENAME, kind=ResourceKind.FILE),
]

...:104-113
    def __init__(self, default_settings_path: Path | None = None) -> None:
        strategies = list(_STRATEGIES)
        if default_settings_path:
            strategies.append(
                DefaultFileStrategy(path=default_settings_path, kind=ResourceKind.FILE)
            )
        self._assembler = create_standard_assembler(
            parser=TomlConfigParser(),
            strategies=strategies,
        )
```

- Priority: CLI → env → traversal (`settings.toml`, 2 ancestors) → XDG
  (`~/.config/weg/settings.toml`) → **optional** packaged default.
- The packaged default is **not** part of `_STRATEGIES`; it is appended only when the
  caller supplies a path. The CLI supplies it:
  `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py:67-74`
  (`defaults_dir = package_files("wallpaper_effects_generator") / "defaults"`,
  `default_settings_path=defaults_dir / "settings.toml"`).
- Env override prefix: `WALLPAPER` (`WALLPAPER__SECTION__KEY`), set at
  `adapters/assembled_config_resolver.py:122`.
- Help text matches:
  `cli/main.py:50-62` ("1. WALLPAPER_CONFIG_FILE_PATH", "2. settings.toml in CWD or up to
  `CONFIG_TRAVERSAL_DEPTH` parent levels", "3. XDG default", "4. Package-bundled defaults").
- Effects resolve through a parallel chain:
  `adapters/yaml_effect_loader.py:_STRATEGIES` (lines 113-120) plus optional default at
  124-133; prefix `WALLPAPER_EFFECTS` (line 138). `cli/main.py:73` supplies
  `defaults/effects.yaml`.
- Constants: `constants.py:3-5` (`CONFIG_XDG_SUBDIR="weg"`, `CONFIG_FILENAME="settings.toml"`,
  `CONFIG_TRAVERSAL_DEPTH=2`).

### 2.3 `itr` (icon-templates-renderer)

Factory:

**Evidence:**
```
src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/factory.py:66-67
def create_config_resolver() -> AssembledConfigResolver:
    return AssembledConfigResolver()
```

Resolver and priority list:

**Evidence:**
```
src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/adapters/assembled_config_resolver.py:41-66
        strategies = [
            CliPathStrategy(kind=ResourceKind.FILE),
            EnvPathStrategy(kind=ResourceKind.FILE),
            DirectoryTraversalStrategy(
                filename=CONFIG_FILENAME,
                max_levels=CONFIG_TRAVERSAL_DEPTH,
                kind=ResourceKind.FILE,
            ),
            XdgStrategy(
                xdg_subdir=CONFIG_XDG_SUBDIR,
                filename=CONFIG_FILENAME,
                kind=ResourceKind.FILE,
            ),
            DefaultFileStrategy(
                path=Path(resource_files("icon_templates_renderer") / "defaults" / CONFIG_FILENAME),
                kind=ResourceKind.FILE,
            ),
        ]
        self._assembler = assembler or AssembleConfiguration(
            path_resolver=CompositePathResolver(strategies),
            parser=TomlConfigParser(),
            env_reader=OsEnvironmentReader(),
            validator=PydanticValidator(),
            coercer=PydanticTypeCoercer(),
        )
        self._policy = ResolutionPolicy(env_prefix="ICON_RENDERER")
```

- Priority: CLI → env → traversal (`settings.toml`, 2 ancestors) → XDG
  (`~/.config/itr/settings.toml`) → packaged
  `icon_templates_renderer/defaults/settings.toml`.
- Env override prefix: `ICON_RENDERER`.
- `--config` is passed as `explicit_path` at `cli/_helpers.py:45-46`.
- Constants: `constants.py:3-5` (`CONFIG_XDG_SUBDIR="itr"`, `CONFIG_FILENAME="settings.toml"`,
  `CONFIG_TRAVERSAL_DEPTH=2`).
- Help text matches:
  `cli/main.py:24-28`
  ("Settings discovery: ./settings.toml (up to 2 levels), XDG
  ~/.config/itr/settings.toml, then bundled defaults").
- Templates and color scheme have discovery-only chains with no env/CLI axis:
  `adapters/template_dir_resolver.py:28-40` (traversal `templates` ×3 → XDG
  `itr/templates`), `adapters/color_scheme_resolver.py:28-42` (traversal `colors.yaml` ×3 →
  XDG `itr/colors.yaml`).

### 2.4 Hardcoded paths in CLI source

Grep for repo/spine paths in the three CLI sources and three shared libraries:

**Evidence:**
```
$ grep -rn "/home/\|Development/\|dotfiles-v3\|src/cli-tools\|src/shared" \
    src/cli-tools/*/src src/shared/*/src
```

The hits are Dockerfile `COPY`/`HOME` lines and `oci_runtime/source_locator.py`
comments (Section 6). No Python module in `csg`/`weg`/`itr` hardcodes a dotfiles-repo or
spine path. The only absolute Python path fallback is:

**Evidence:**
```
src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/container_processor.py:159-161
            templates_dir = Path(
                "/usr/share/color-scheme-generator/templates"
            )
```

That branch is reached only when no CLI dir, resolver, or settings-adjacent path exists
(lines 150-158). The CLI calls `create_container_processor` without
`default_settings_path` (`cli/main.py:246-251`, `cli/_helpers.py:136-140`), so the
settings-adjacent branch at lines 154-157 is not populated by the CLI. `/usr/share` is
neither the repo nor the spine.

`_xdg_config_home` / `_xdg_settings_path` in `cli/main.py` (csg 55-56, weg 43-45) are used
only to render help text; resolution itself goes through `XdgStrategy`.

---

## 3. How settings/default files are packaged

### 3.1 Build configuration

| Project | Build include / wheel packages | File |
|---|---|---|
| `color-scheme-generator` | `include = ["src/color_scheme_generator/**"]`; wheel packages `src/color_scheme_generator` | `pyproject.toml:26-32` |
| `icon-templates-renderer` | `include = ["src/icon_templates_renderer/**"]`; wheel packages `src/icon_templates_renderer` | `pyproject.toml:23-29` |
| `wallpaper-effects-generator` | no `include` list; wheel packages `src/wallpaper_effects_generator` | `pyproject.toml:20-21` |

The `**` include and the wheel-package declaration both cover the `defaults/`
subdirectories. `wallpaper-effects-generator` has no explicit include list; its built wheel
nevertheless contained `defaults/settings.toml` and `defaults/effects.yaml` (observed
below).

### 3.2 Built wheels contain the defaults

**Evidence:**
```
$ uv build --wheel --out-dir /tmp/opencode/wheels <each project>   # exit 0 for all six
$ unzip -l /tmp/opencode/wheels/color_scheme_generator-0.1.0-py3-none-any.whl | grep defaults/
  1526  color_scheme_generator/defaults/backends.yaml
   396  color_scheme_generator/defaults/settings.toml
  5805  color_scheme_generator/defaults/templates/colors.adw.css.j2
   ...  (12 template files total)
$ unzip -l /tmp/opencode/wheels/icon_templates_renderer-0.1.0-py3-none-any.whl | grep defaults/
   379  icon_templates_renderer/defaults/settings.toml
$ unzip -l /tmp/opencode/wheels/wallpaper_effects_generator-0.1.0-py3-none-any.whl | grep defaults/
  4524  wallpaper_effects_generator/defaults/effects.yaml
   361  wallpaper_effects_generator/defaults/settings.toml
```

The wheel `RECORD` files list the same files (e.g.
`color_scheme_generator/defaults/settings.toml,sha256=FYTdhZc…`, `icon_templates_renderer/
defaults/settings.toml,sha256=JcaDPf…`, `wallpaper_effects_generator/defaults/settings.toml,
sha256=WZ3YWIX…`).

### 3.3 Runtime location of the packaged default

- `csg`: `importlib.resources.files("color_scheme_generator") / "defaults" / "settings.toml"`
  (`adapters/settings/config_resolver.py:73`).
- `itr`: `importlib.resources.files("icon_templates_renderer") / "defaults" / CONFIG_FILENAME`
  (`adapters/assembled_config_resolver.py:55`).
- `weg`: `importlib.resources.files("wallpaper_effects_generator") / "defaults"` in
  `cli/main.py:68`, passed as `default_settings_path` (line 71) and `default_effects_path`
  (line 73).
- `csg` backend catalog: `resource_files("color_scheme_generator.defaults") / "backends.yaml"`
  (`adapters/yaml_backend_catalog_loader.py:70`).
- `csg` templates: `Path(__file__).resolve().parent.parent / "defaults" / "templates"`
  (`adapters/template_dir_resolver.py:16-17`).

In an installed wheel these land in `site-packages/<package>/defaults/…`; in an editable or
source-tree install they land in `<repo>/src/cli-tools/<project>/src/<package>/defaults/…`.
They do **not** land in the provisioning spine.

Executed proof from a wheel-only virtualenv, `cwd=/tmp`, `HOME` and `XDG_CONFIG_HOME` set
to an empty temp home:

**Evidence:**
```
$ /tmp/opencode/venv/bin/python -c '<construct resolvers>'
cwd: /tmp
color_scheme_generator /tmp/opencode/venv/lib/python3.14/site-packages/color_scheme_generator/__init__.py
icon_templates_renderer /tmp/opencode/venv/lib/python3.14/site-packages/icon_templates_renderer/__init__.py
wallpaper_effects_generator /tmp/opencode/venv/lib/python3.14/site-packages/wallpaper_effects_generator/__init__.py
csg resolved: /tmp/opencode/venv/lib/python3.14/site-packages/color_scheme_generator/defaults/settings.toml | out: /tmp/color-scheme | backend: Backend.PYWAL
itr resolved: /tmp/opencode/venv/lib/python3.14/site-packages/icon_templates_renderer/defaults/settings.toml | out: /tmp/icon-templates-renderer | verbosity: Verbosity.NORMAL
weg resolved: /tmp/opencode/venv/lib/python3.14/site-packages/wallpaper_effects_generator/defaults/settings.toml | out: /tmp/wallpaper-effects
EXIT:0
```

`csg info` and `weg info`, run from `/tmp` against the wheel-only venv, report the
source paths explicitly:

**Evidence:**
```
$ cd /tmp && ... /tmp/opencode/venv/bin/csg info | grep -A2 sources
  "sources": [
    "settings: /tmp/opencode/venv/lib/python3.14/site-packages/color_scheme_generator/defaults/settings.toml",
    "templates: /tmp/opencode/venv/lib/python3.14/site-packages/color_scheme_generator/defaults/templates"
  ]

$ cd /tmp && ... /tmp/opencode/venv/bin/weg info
  "sources": [
    "settings: /tmp/opencode/fakehome/.config/weg/settings.toml",
    "effects: /tmp/opencode/venv/lib/python3.14/site-packages/wallpaper_effects_generator/defaults/effects.yaml"
  ]
```

(The `weg` settings source in that run was a temp XDG file; the effects source is the
packaged default.)

---

## 4. Provisioning → CLIs: how the spine reaches XDG

### 4.1 Where provisioning writes the settings

**Evidence:**
```
src/provisioning/ansible/roles/settings/vars/main.yml:62-69
# settings_spine_config_dir: the config-in-spine destination root
#   (<install>/config/). The settings files are rendered into
#   <install>/config/<tool>/settings.toml; the config-links role symlinks each
#   ~/.config/<tool> -> <install>/config/<tool>, so the tools' native XDG
#   discovery finds the rendered files through the link.
settings_spine_config_dir: "{{ install_dir | trim }}/config"

...:76-79
settings_config_dirs:
  - "{{ settings_spine_config_dir }}/color-scheme-generator"
  - "{{ settings_spine_config_dir }}/weg"
  - "{{ settings_spine_config_dir }}/itr"

...:87-90
settings_files:
  - { name: csg, template: csg-settings.toml.j2, dest: "{{ settings_spine_config_dir }}/color-scheme-generator/settings.toml" }
  - { name: weg, template: weg-settings.toml.j2, dest: "{{ settings_spine_config_dir }}/weg/settings.toml" }
  - { name: itr, template: itr-settings.toml.j2, dest: "{{ settings_spine_config_dir }}/itr/settings.toml" }
```

Render task:

**Evidence:**
```
src/provisioning/ansible/roles/settings/tasks/main.yml:75-91
- name: Ensure per-tool config dirs exist
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
  loop: "{{ settings_config_dirs }}"

- name: Ensure WEG cache dirs exist
  ...

- name: Render settings files
  ansible.builtin.template:
    src: "{{ item.template }}"
    dest: "{{ item.dest }}"
  loop: "{{ settings_files }}"
```

`install_dir` is resolved by the orchestrator as `$XDG_DATA_HOME/dotfiles` (default
`~/.local/share/dotfiles`):

**Evidence:**
```
src/provisioning/src/provisioning/application/use_cases.py:27-35
def resolve_install_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return (base / "dotfiles").expanduser().resolve()
```

### 4.2 How the spine becomes `~/.config/<tool>`

**Evidence:**
```
src/provisioning/ansible/roles/config_links/vars/main.yml:86-107
config_links_managed_dirs:
  - hypr
  ...
  - color-scheme-generator
  - weg
  - itr
  ...

src/provisioning/ansible/roles/config_links/tasks/_link_one.yml:36-40
- name: "config_links : Resolve expected spine target for {{ config_link_name }}"
  ansible.builtin.set_fact:
    config_links_spine_target: "{{ install_dir | trim }}/config/{{ config_link_name }}"

...:137-142
- name: "config_links : Symlink ~/.config/{{ config_link_name }} -> spine"
  ansible.builtin.file:
    path: "{{ config_links_xdg_config_home }}/{{ config_link_name }}"
    src: "{{ config_links_spine_target }}"
    state: link
    force: true
```

`config_links_xdg_config_home` honours `$XDG_CONFIG_HOME`, defaulting to
`$HOME/.config` (`config_links/vars/main.yml:42-46`).

### 4.3 Observed link on this machine

**Evidence:**
```
$ echo "XDG_CONFIG_HOME=$XDG_CONFIG_HOME"; echo "XDG_DATA_HOME=$XDG_DATA_HOME"
XDG_CONFIG_HOME=/home/inumaki/.config
XDG_DATA_HOME=/home/inumaki/.local/share
$ ls -la ~/.config/color-scheme-generator ~/.config/weg ~/.config/itr
lrwxrwxrwx ... /home/inumaki/.config/color-scheme-generator -> /home/inumaki/.local/share/dotfiles/config/color-scheme-generator
lrwxrwxrwx ... /home/inumaki/.config/weg -> /home/inumaki/.local/share/dotfiles/config/weg
lrwxrwxrwx ... /home/inumaki/.config/itr -> /home/inumaki/.local/share/dotfiles/config/itr
$ readlink -f ~/.local/share/dotfiles
/home/inumaki/.local/share/dotfiles
```

The XDG path the CLIs read (`xdg.py:20-21`) therefore resolves through the symlink to the
spine directory the settings role writes. This was also observed indirectly in the test
runs in Section 5.1/5.2, where the resolvers returned paths under
`/home/inumaki/.local/share/dotfiles/config/...` and `/home/inumaki/.cache/dotfiles/...`.

### 4.4 Rendered values are tool-consumable

Provisioning integration tests render into a throwaway `install_dir` and invoke the real
CLIs with `--config`:

**Evidence:**
```
$ uv run --directory src/provisioning pytest -q \
    tests/integration/test_settings_parity.py::TestSettingsFileParity
....                                                                     [100%]
4 passed in 17.66s
EXIT:0

$ uv run --directory src/provisioning pytest -q \
    tests/integration/test_settings_parity.py::TestSpineChain
.                                                                        [100%]
1 passed in 16.90s
EXIT:0
```

Those tests use a `tmp_path` install dir (`test_settings_parity.py:352-363`) and find
`ansible-playbook` on the `uv run` PATH:

**Evidence:**
```
$ cd src/provisioning && uv run which ansible-playbook
/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit/src/provisioning/.venv/bin/ansible-playbook
EXIT:0
```

---

## 5. Tests executed and what they prove

### 5.1 Per-tool resolution tests (repository environment, provisioned XDG present)

**Evidence:**
```
$ uv run --directory src/shared/config-assembler-engine --with pytest -- \
    pytest -q -k "strateg or resolv"
43 passed, 119 deselected in 0.36s
EXIT:0
```

**Evidence:**
```
$ uv run --directory src/cli-tools/wallpaper-effects-generator pytest -q -k "config or resolv"
52 passed, 292 deselected in 0.58s
EXIT:0
```

**Evidence:**
```
$ uv run --directory src/cli-tools/color-scheme-generator pytest -q -k "config or resolv"
1 failed, 82 passed, 553 deselected in 9.17s
EXIT:1
FAILED tests/unit/adapters/test_template_dir_resolver.py::TestTemplateDirResolver::test_resolve_falls_back_to_package_defaults
assert PosixPath('/home/inumaki/.local/share/dotfiles/config/color-scheme-generator/templates') ==
       PosixPath('<repo>/src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates')
```

**Evidence:**
```
$ uv run --directory src/cli-tools/icon-templates-renderer pytest -q -k "config or resolv"
1 failed, 67 passed, 218 deselected in 0.52s
EXIT:1
FAILED tests/unit/adapters/test_assembled_config_resolver.py::TestAssembledConfigResolver::test_resolves_bundled_default
assert PosixPath('/home/inumaki/.cache/dotfiles/itr-output') == Path('/tmp/icon-templates-renderer')
```

The two failures are evidence of the provisioning link, not of a broken resolver: with the
real `~/.config` present, XDG wins over the packaged default and returns the spine values.
Both tests pass when `XDG_CONFIG_HOME` is empty:

**Evidence:**
```
$ env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-csg \
    uv run --directory src/cli-tools/color-scheme-generator pytest -q \
    tests/unit/adapters/test_template_dir_resolver.py
4 passed in 0.02s
EXIT:0

$ env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-itr \
    uv run --directory src/cli-tools/icon-templates-renderer pytest -q \
    tests/unit/adapters/test_assembled_config_resolver.py
6 passed in 0.01s
EXIT:0
```

### 5.2 Shared-engine strategy tests

`test_strategies.py` builds temp files/dirs and chdirs into them, e.g.:

**Evidence:**
```
src/shared/config-assembler-engine/tests/unit/test_strategies.py:84-92
    def test_finds_file_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=0, kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.DIRECTORY
```

and XDG at lines 131-141, parent traversal at 94-103. These tests do not reference the
repository at all; they operate on `tmp_path`.

### 5.3 Which tests prove resolution outside a repo checkout

- `csg` and `weg` `tests/unit/adapters/.../test_config_resolution_chain.py` —
  every scenario creates files under `tmp_path` and `monkeypatch.chdir`s into a temp
  directory (e.g. csg lines 29-60, 112-143, 170-181; weg lines 14-136). They assert
  CLI/env/depth/XDG/package-default selection without any repo file.
- `csg`/`weg` package-default test (csg `test_config_resolution_chain.py:170-181`) chdirs
  to `tmp_path/empty_cwd` and sets `XDG_CONFIG_HOME` to a nonexistent dir; the resolver
  then returns the packaged defaults.
- `weg` `test_package_default_fallback_when_no_file_found`
  (`tests/unit/adapters/test_config_resolution_chain.py:130-136`) expects
  `ConfigAssemblerError` because it constructs `AssembledConfigResolver()` **without** a
  default path; the packaged fallback is wired only by `cli/main.py` (Section 2.2).
- `itr` `test_resolves_bundled_default`
  (`tests/unit/adapters/test_assembled_config_resolver.py:10-15`) does **not** chdir or set
  XDG; it is cwd/environment-sensitive. It passes only when XDG is empty (observed above)
  and fails against the provisioned spine.
- The wheel-only execution in Section 3.3 is a direct, non-test execution from `/tmp` with
  no repo on `sys.path`; all three resolvers selected files inside `site-packages`.

### 5.4 Directory traversal is filename-only (executed)

Temp trees were created outside the repo and the installed wheel was used:

**Evidence:**
```
# settings.toml at /tmp/opencode/trav-<tool>/settings.toml; cwd=/tmp/opencode/trav-<tool>/a/b
$ ... python -c '<resolve>'
csg depth2: /tmp/opencode/trav-csg/settings.toml /tmp/cwd-csg-out
weg depth2: /tmp/opencode/trav-weg/settings.toml /tmp/cwd-weg-out
itr depth2: /tmp/opencode/trav-itr/settings.toml /tmp/cwd-itr-out
EXIT:0
```

Depth boundary (cwd one level deeper, at `a/b/c`):

**Evidence:**
```
csg depth3: /tmp/opencode/trav-csg/settings.toml /tmp/cwd-csg-out
weg depth3: /tmp/opencode/venv/lib/python3.14/site-packages/wallpaper_effects_generator/defaults/settings.toml /tmp/wallpaper-effects
itr depth3: /tmp/opencode/venv/lib/python3.14/site-packages/icon_templates_renderer/defaults/settings.toml /tmp/icon-templates-renderer
EXIT:0
```

`csg` (max_levels=3) found the file 3 ancestors up; `weg`/`itr` (max_levels=2) did not and
fell through to package defaults. There was no marker directory in any of these trees.

Precedence (temp XDG present, cwd contains a different `settings.toml`, env points at a
third file):

**Evidence:**
```
csg env: /tmp/opencode/env-csg.toml /tmp/env-csg-out
weg env: /tmp/opencode/env-weg.toml /tmp/env-weg-out
itr env: /tmp/opencode/env-itr.toml /tmp/env-itr-out
EXIT:0
```

XDG versus packaged default (temp XDG contains settings, cwd `/tmp`):

**Evidence:**
```
csg XDG: /tmp/opencode/fakehome/.config/color-scheme-generator/settings.toml /tmp/xdg-csg-out Backend.CUSTOM
itr XDG: /tmp/opencode/fakehome/.config/itr/settings.toml /tmp/xdg-itr-out Verbosity.VERBOSE
weg XDG: /tmp/opencode/fakehome/.config/weg/settings.toml /tmp/xdg-weg-out
EXIT:0
```

### 5.5 Provisioning role unit tests

**Evidence:**
```
$ uv run --directory src/provisioning pytest -q tests/unit/test_settings_role.py
27 passed in 32.86s
EXIT:0
```

These assert the role's render contract (three files, install-dir-derived destinations,
no repo root key, template values), including
`test_settings_files_are_exactly_three`, `test_every_dest_parent_is_ensured_in_config_dirs`,
`test_no_settings_repo_root_key`.

### 5.6 Not executed

- Container-image tests (`TestPhase2InvocationContract`) require a podman/docker image;
  not run in this spike.
  `Evidence: MISSING — run uv run --directory src/provisioning pytest -q tests/integration/test_settings_parity.py::TestPhase2InvocationContract with a built csg image and a container engine`
- No test was run from a host where the provisioning spine is absent end-to-end with the
  `uv tool` installed binaries; the wheel-only venv plus temp XDG was used instead.
  `Evidence: MISSING — run the wheel-only venv scenario (Section 8.4) on a host with no ~/.config/* spine symlinks`

---

## Repo-relative path dependencies (if any)

Search over the three CLI sources and the shared libraries:

**Evidence:**
```
$ grep -rn "Path(__file__)\|Path.cwd()\|os.getcwd()\|parents\[" \
    src/cli-tools/*/src src/shared/*/src
src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/template_dir_resolver.py:16:_PACKAGE_DIR = Path(__file__).resolve().parent.parent
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/directory.py:17:        cwd = Path.cwd()
src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/directory.py:21:            check_dir = cwd.parents[level - 1] if level > 0 else cwd
```

**Evidence:**
```
$ grep -rn "importlib.resources\|resource_files\|package_files\|/ \"defaults\"\|defaults_dir" \
    src/cli-tools/*/src src/shared/*/src
csg config_resolver.py:3,73
csg container_processor.py:156
csg template_dir_resolver.py:17
csg yaml_backend_catalog_loader.py:4,70
csg cli/dump_config_cmd.py:3,18
csg cli/dump_templates_cmd.py:5,40
csg cli/install_cmd.py:4
itr assembled_config_resolver.py:3,55
weg cli/dump_config.py:3,15
weg cli/dump_effects.py:3,15
weg cli/install.py:4,67,99,109
weg cli/main.py:4,68,71,73
shared/oci-runtime source_locator.py:30,90,97
```

**Evidence:**
```
$ grep -rn "dotfiles" src/cli-tools/*/src src/shared/*/src --include='*.py'
(no output; exit 1)
```

| Hit | Context | Classification | Resolves inside an installed wheel? |
|---|---|---|---|
| `csg/adapters/template_dir_resolver.py:16-17` `_PACKAGE_DIR = Path(__file__).resolve().parent.parent`; `_DEFAULT_TEMPLATES_DIR = _PACKAGE_DIR / "defaults" / "templates"` | `DefaultDirStrategy` last in the templates chain (`template_dir_resolver.py:28`) | **packaged-resource** — `__file__` is the package module, so `.parent.parent` is `site-packages/color_scheme_generator` in a wheel | Yes. Observed `csg info` source: `…/site-packages/color_scheme_generator/defaults/templates` |
| `config-assembler-engine/adapters/strategies/directory.py:17,21` `Path.cwd()` / `cwd.parents[…]` | `DirectoryTraversalStrategy`, used for `settings.toml`, `templates/`, `effects.yaml`, `colors.yaml`, `backends.yaml` | **cwd-relative by design, not repo-relative** — no repo marker, just `<ancestor>/<filename>` | Yes, in the sense that it needs no repo; it resolves whatever ancestor contains the filename. It returns `None` when nothing matches and the chain continues to XDG/default |
| `shared/oci-runtime/source_locator.py:37-39` `_REPO_MARKER_DIRS = (("src","cli-tools"), ("src","shared"))`; `:50-61` walks `candidate, *candidate.parents` until both exist | `resolve_source_root()` used by `csg install` (`cli/install_cmd.py:63-66`) and `weg install` (`cli/install.py:59-62`) to find the container build context | **repo-relative** — requires an actual repo tree containing `src/cli-tools` and `src/shared` | **Not from the package path**: site-packages has no marker. It can still resolve via the PEP 610 `direct_url.json` written by `uv tool install <repo path>`, which records the source dir. If that dir is gone, it raises `SourceRootNotFoundError` |
| `csg/adapters/docker/Dockerfile.base:3-6`, `weg/adapters/docker/Dockerfile.imagemagick:9-12` `COPY src/cli-tools/...`, `COPY src/shared/...` | Docker build-time `COPY`; paths are relative to the build context supplied by `source_locator` | **repo-relative (build time)** | Not applicable to installed runtime; these lines are only interpreted by `docker/podman build` with the repo root as context |

Executed classification of the `oci_runtime` locator:

**Evidence:**
```
# Installed via `uv tool install` from the repo (this machine)
$ /home/inumaki/.local/share/uv/tools/color-scheme-generator/bin/python -c \
    "from oci_runtime import resolve_source_root; r=resolve_source_root(package='color_scheme_generator'); print(r.root, r.source)"
/home/inumaki/Development/dotfiles-v3 direct_url

# Wheel-only venv (no PEP 610 file:// dir pointing at a repo)
$ /tmp/opencode/venv/bin/python -c \
    "from oci_runtime import resolve_source_root; print(resolve_source_root(package='color_scheme_generator'))"
SourceRootNotFoundError Cannot locate the 'color_scheme_generator' source repo to use as a container build context.
```

The installer record that makes the first case work:

**Evidence:**
```
$ cat ~/.local/share/uv/tools/color-scheme-generator/lib/python3.14/site-packages/color_scheme_generator-0.1.0.dist-info/direct_url.json
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/cli-tools/color-scheme-generator","dir_info":{}}
```

Same shape for `weg` and `itr` (their own `direct_url.json` points at
`/home/inumaki/Development/dotfiles-v3/src/cli-tools/...`).

`source_locator.py:139-144` tries candidates in order and raises if none match:

**Evidence:**
```
    for source, candidate in candidates:
        root = _repo_root_from_candidate(candidate)
        if root is not None:
            return SourceRoot(root=root, source=source)

    raise SourceRootNotFoundError(package=package, env_var=env_var)
```

**Conclusion for this section:** settings, templates, effects, and the backend catalog have
no repo-relative runtime dependency. The only repo-tree dependency in the inspected code is
the container build-context locator used by `csg install` / `weg install`, and it has a
PEP 610 fallback to the original install path.

---

## Open questions

1. **Ancestor `settings.toml` in arbitrary user cwd.** `DirectoryTraversalStrategy` will
   pick any `settings.toml` in cwd or up to the configured number of ancestors. No test or
   guard limits this to a project root. Not observed in this repo (no root-level
   `settings.toml`; see below), but behavior in a user directory containing an unrelated
   `settings.toml` was not tested.
   **Evidence:**
   ```
   $ find . -name settings.toml -not -path '*/.venv/*' -not -path '*/node_modules/*'
   ./src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/settings.toml
   ./src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/defaults/settings.toml
   ./src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/settings.toml
   ```
2. **Lifetime of `direct_url.json`.** It survives the current `uv tool install`; behavior
   after `uv tool upgrade`, reinstall from a wheel, or deletion/move of the repo was not
   tested. The wheel-only venv demonstrates the failure mode when no repo path is recorded.
3. **`csg` `template_dir_resolver` packaged fallback under a provisioned XDG.** The unit
   test expects the packaged directory but gets the spine; whether the spine templates
   directory is always present on a provisioned machine was not tested here beyond the
   observed symlink and rendered settings.
4. **`csg` container `default_settings_path` branch.** `container_processor.py:154-157`
   computes `default_settings_path.parent / "defaults" / "templates"`, but the production
   callers (`cli/main.py:246-251`, `cli/_helpers.py:136-140`) do not pass
   `default_settings_path`, so the branch is not exercised by the CLI. Whether any other
   caller passes a path that makes that join correct was not established.
5. **Integration tests requiring a container.** `TestPhase2InvocationContract`
   (`test_settings_parity.py:707`, `:795`) was not executed; it requires a built
   `csg` image and a container engine. Evidence for template selection therefore comes
   from unit tests plus `csg info`, not from a container render.
6. **Windows / non-POSIX XDG behavior.** Not tested; `os.environ.get("XDG_CONFIG_HOME",
   Path.home() / ".config")` assumes POSIX-style paths.

---

## Verify

Reproduce the load-bearing observations.

### 8.1 Read the strategy code

**Evidence:**
```
cd /home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit
sed -n '1,30p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/cli_path.py
sed -n '1,30p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/env_path.py
sed -n '1,30p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/directory.py
sed -n '1,30p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/xdg.py
sed -n '1,25p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/default_file.py
sed -n '1,20p' src/shared/config-assembler-engine/src/config_assembler_engine/adapters/path_resolver.py
```

### 8.2 Read the per-CLI wiring

**Evidence:**
```
sed -n '65,90p' src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py
sed -n '60,75p' src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py
sed -n '70,130p' src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/assembled_config_resolver.py
sed -n '65,75p' src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py
sed -n '38,70p' src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/adapters/assembled_config_resolver.py
sed -n '60,70p' src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/factory.py
```

### 8.3 Run the resolution tests

**Evidence:**
```
cd /home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit
uv run --directory src/shared/config-assembler-engine --with pytest -- \
  pytest -q -k "strateg or resolv"
uv run --directory src/cli-tools/wallpaper-effects-generator pytest -q -k "config or resolv"
uv run --directory src/cli-tools/color-scheme-generator pytest -q -k "config or resolv"
uv run --directory src/cli-tools/icon-templates-renderer pytest -q -k "config or resolv"
```

Expected on this host: shared 43 pass; WEG 52 pass; CSG 82 pass / 1 fail
(`test_resolve_falls_back_to_package_defaults`, resolves the spine); ITR 67 pass / 1 fail
(`test_resolves_bundled_default`, resolves the spine-rendered settings). Re-run the two
failing tests with an empty XDG to see the packaged fallback:

**Evidence:**
```
env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-csg \
  uv run --directory src/cli-tools/color-scheme-generator pytest -q \
  tests/unit/adapters/test_template_dir_resolver.py
env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-itr \
  uv run --directory src/cli-tools/icon-templates-renderer pytest -q \
  tests/unit/adapters/test_assembled_config_resolver.py
```

### 8.4 Prove the wheel ships defaults and resolves outside the repo

**Evidence:**
```
cd /home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit
rm -rf /tmp/opencode/wheels /tmp/opencode/venv
mkdir -p /tmp/opencode/wheels
for d in src/cli-tools/color-scheme-generator \
         src/cli-tools/wallpaper-effects-generator \
         src/cli-tools/icon-templates-renderer \
         src/shared/cli-output src/shared/config-assembler-engine src/shared/oci-runtime; do
  uv build --wheel --out-dir /tmp/opencode/wheels "$d"
done
for w in /tmp/opencode/wheels/*.whl; do unzip -l "$w" | grep defaults/; done
uv venv --python 3.14 /tmp/opencode/venv
uv pip install --python /tmp/opencode/venv/bin/python /tmp/opencode/wheels/*.whl
mkdir -p /tmp/opencode/fakehome/.config
cd /tmp
env -u COLORSCHEME_CONFIG_FILE_PATH -u WALLPAPER_CONFIG_FILE_PATH \
    -u ICON_RENDERER_CONFIG_FILE_PATH \
    HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/fakehome/.config \
    /tmp/opencode/venv/bin/python - <<'PY'
import color_scheme_generator, icon_templates_renderer, wallpaper_effects_generator
print(color_scheme_generator.__file__)
from color_scheme_generator.adapters.settings.config_resolver import AssembledConfigResolver as CSG
r = CSG(); s = r.resolve(); print("csg:", r.last_result.resolved_path, s.output.directory)
from icon_templates_renderer.adapters.assembled_config_resolver import AssembledConfigResolver as ITR
i = ITR(); si = i.resolve(); print("itr:", i.get_resolved_path(), si.output.output_dir)
from wallpaper_effects_generator.cli.main import build_deps
d = build_deps(); w = d.config_resolver.resolve()
print("weg:", d.config_resolver.get_resolved_path(), w.output.directory)
PY
```

Expected: all three resolved paths are under `/tmp/opencode/venv/lib/python3.14/site-packages/…/defaults/settings.toml`.

### 8.5 Prove the provisioning link

**Evidence:**
```
ls -la ~/.config/color-scheme-generator ~/.config/weg ~/.config/itr
readlink -f ~/.config/weg
sed -n '62,90p' src/provisioning/ansible/roles/settings/vars/main.yml
sed -n '86,110p' src/provisioning/ansible/roles/config_links/vars/main.yml
sed -n '36,42p;137,142p' src/provisioning/ansible/roles/config_links/tasks/_link_one.yml
uv run --directory src/provisioning pytest -q tests/unit/test_settings_role.py
uv run --directory src/provisioning pytest -q \
  tests/integration/test_settings_parity.py::TestSettingsFileParity \
  tests/integration/test_settings_parity.py::TestSpineChain
```

Expected on this host: 27 passed for the role unit suite; 4 + 1 passed for the integration
classes; symlinks point into `/home/inumaki/.local/share/dotfiles/config/…`.

### 8.6 Prove the repo-relative container-build dependency

**Evidence:**
```
grep -rn "Path(__file__)\|Path.cwd()\|os.getcwd()\|parents\[" \
  src/cli-tools/*/src src/shared/*/src
grep -rn "dotfiles" src/cli-tools/*/src src/shared/*/src --include='*.py'
sed -n '37,61p;109,144p' src/shared/oci-runtime/src/oci_runtime/source_locator.py
/tmp/opencode/venv/bin/python -c \
  "from oci_runtime import resolve_source_root; print(resolve_source_root(package='color_scheme_generator'))"
```

Expected: `grep` finds only the `__file__` hit in CSG templates, the `Path.cwd()` pair in
the traversal strategy, and no `dotfiles` string in Python; the wheel-only venv raises
`SourceRootNotFoundError`.
