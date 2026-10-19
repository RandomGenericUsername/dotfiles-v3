# S4 — CLI / shared-library reference inventory & deletion blast radius

**Type:** evidence-only spike. **Scope:** `dotfiles-v3` @ `ticket/clirsplit-investigate-and-spine`
(worktree `/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit`), `master` = `fb94b64e`.
**Purpose:** enumerate every reference to the three CLI packages and three shared libraries, and
document how cross-package dependencies are declared and resolved **today**.

No recommendations appear in this document. Every claim is followed by the command output or
`file:line` that produced it.

---

## 0. Method and totals

Command (exactly as specified; run from the repo worktree):

```
rg -n --hidden -g '!.git' -g '!.worktrees' -g '!uv.lock' \
  -e 'src/cli-tools' -e 'src/shared' \
  -e 'color-scheme-generator' -e 'wallpaper-effects-generator' -e 'icon-templates-renderer' \
  -e 'cli-output' -e 'cli_output' \
  -e 'config-assembler-engine' -e 'config_assembler_engine' \
  -e 'oci-runtime' -e 'oci_runtime' .
```

Observed: **3346 matching lines across 635 unique files** (`wc -l /tmp/opencode/s4_hits.txt` → `3346`;
per-file tally script → `UNIQUE FILES: 635`).

Per-token line counts (a line can match several tokens; sum exceeds 3346):

| token | lines | token | lines |
|---|---|---|---|
| `oci_runtime` | 1174 | `config_assembler_engine` | 316 |
| `src/cli-tools` | 650 | `oci-runtime` | 316 |
| `color-scheme-generator` | 608 | `cli-output` | 228 |
| `wallpaper-effects-generator` | 372 | `cli_output` | 216 |
| `config-assembler-engine` | 199 | `src/shared` | 112 |
| `icon-templates-renderer` | 98 | | |

**Scope caveat (evidenced).** The 11 tokens above do **not** match the Ansible role name
`cli_tools` or the binaries `csg`/`weg`/`itr`. A supplementary search finds references the
specified pattern misses:

```
$ rg -n 'cli_tools|cli-tools' Makefile .github scripts bootstrap.sh dotfiles docs
Makefile:44:# cli_tools) and the provisioning SHAPE, which `deploy-coverage` asserts.
bootstrap.sh:46,54,167,182,207,222,408
dotfiles/provisioning/cli-tools.yaml:5,7,10,12,14
dotfiles/provisioning/assets.yaml:20
dotfiles/provisioning/packages.yaml:8
scripts/deploy-coverage.py:209,819
scripts/ansible-embedded-template-lint.py:40
docs/HANDOFF-ags-platform.md:197
(+ docs/01-… and docs/99-… tables)
```

---

## 1. Question 1 — references grouped by area

| # | Area | hits | unique files |
|---|---|---|---|
| 1 | `_bmad-output/` (historical planning artifacts) | 1120 | 139 |
| 2 | `src/shared/` (the libs themselves) | 1072 | 183 |
| 3 | `openspec/` (archived 422 + live 168) | 590 | 147 |
| 4 | `src/cli-tools/` (the CLIs themselves) | 300 | 78 |
| 5 | `src/runtime/` (code 28 / tests 86) | 114 | 53 |
| 6 | `src/provisioning/` (roles+code 38 / tests 38) | 76 | 18 |
| 7 | `docs/` | 53 | 3 |
| 8 | `spikes/` | 9 | 9 |
| 9 | `dotfiles/` manifests | 8 | 3 |
| 10 | `.opencode/plans/` | 2 | 1 |
| 11 | `.gitignore` | 2 | 1 |
| — | **`Makefile`** | **0** | 0 |
| — | **`scripts/`** | **0** | 0 |
| — | **`.github/workflows/`** | **0** | 0 |
| — | **`bootstrap.sh`** | **0** | 0 |
| — | **`pyproject.toml` files** (as a group) | 22 | 8 |

Split inside the two source trees:

| package | hits | files |
|---|---|---|
| `src/shared/oci-runtime/` | 835 | 124 |
| `src/shared/config-assembler-engine/` | 186 | 42 |
| `src/shared/cli-output/` | 51 | 17 |
| `src/cli-tools/color-scheme-generator/` | 163 | 39 |
| `src/cli-tools/wallpaper-effects-generator/` | 84 | 24 |
| `src/cli-tools/icon-templates-renderer/` | 53 | 15 |
| `openspec/changes/archive/` | 422 | 104 |

### 1.1 Makefile — 0 hits

The root `Makefile` contains **no** reference to any CLI package or shared lib by path or name:

```
$ rg -n 'color-scheme|wallpaper-effects|icon-templates|shared|cli-output|oci-runtime|config-assembler' Makefile
237:# (shared-ancestor for the platform, live-bar link + per-unit for the bar).
$ rg -n 'pytest' Makefile
14:	uv run --directory src/runtime pytest tests/unit/test_contract_schema_conformance.py … -q
```

`Makefile:14` is the **only** pytest invocation in the file, and it targets `src/runtime`. The
gate list is `GATES := contracts-check ansible-embedded-template-lint deploy-coverage ci-gates-parity per-app-drift-symbol-suites` (`Makefile:48-49`), i.e. **no gate runs csg / weg / itr / cli-output /
config-assembler-engine / oci-runtime tests.** The single `cli_tools` mention (`Makefile:44`) is prose.

### 1.2 scripts/ — 0 hits for the 11 tokens, 3 hits for the role name

```
scripts/deploy-coverage.py:209:CLI_TOOLS_ROLE_TASKS = "src/provisioning/ansible/roles/cli_tools/tasks/main.yml"
scripts/deploy-coverage.py:819:    # The retired copy task lived in cli_tools; a stale src reference would
scripts/ansible-embedded-template-lint.py:40:``packages.yaml``, ``roles/verify/tasks/main.yml``, ``roles/cli_tools/tasks/
```

`deploy-coverage.py:814-828` asserts `RETIRED_CAPTURE_TOOL_DIR` (`"src/gui-tools/capture-tool"`,
line 208) does **not** appear in the cli_tools role tasks — i.e. an absence guard aimed at the
`src/gui-tools` tree, not at `src/cli-tools`.

### 1.3 provisioning — 38 role/code + 38 test hits, 18 files

Role/code (all lines verified by `sed -n`):

```
src/provisioning/ansible/roles/cli_tools/vars/main.yml:57  - { name: csg, source: src/cli-tools/color-scheme-generator }
src/provisioning/ansible/roles/cli_tools/vars/main.yml:58  - { name: weg, source: src/cli-tools/wallpaper-effects-generator }
src/provisioning/ansible/roles/cli_tools/vars/main.yml:59  - { name: itr, source: src/cli-tools/icon-templates-renderer }
src/provisioning/ansible/roles/assets/vars/main.yml:37      #   config/color-scheme-generator/templates and weg-effects at config/weg.
src/provisioning/ansible/roles/assets/vars/main.yml:42    - config/color-scheme-generator/templates
src/provisioning/ansible/roles/assets/vars/main.yml:63      #   <install>/csg-templates to <install>/config/color-scheme-generator/templates
src/provisioning/ansible/roles/assets/vars/main.yml:65      #   ~/.config/color-scheme-generator -> <install>/config/color-scheme-generator,
src/provisioning/ansible/roles/assets/vars/main.yml:72    - { name: csg-templates, kind: csg-template,
                                                            source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/,
                                                            target: config/color-scheme-generator/templates }
src/provisioning/ansible/roles/filesystem/vars/main.yml:45  # csg-templates moved to config/color-scheme-generator/templates
src/provisioning/ansible/roles/filesystem/vars/main.yml:56  - config/color-scheme-generator
src/provisioning/ansible/roles/filesystem/vars/main.yml:57  - config/color-scheme-generator/templates
src/provisioning/ansible/roles/config_links/vars/main.yml:62 #   - assets       → color-scheme-generator (templates/), weg (effects.yaml)
src/provisioning/ansible/roles/config_links/vars/main.yml:77 #   - settings     → color-scheme-generator, weg, itr
src/provisioning/ansible/roles/config_links/vars/main.yml:101  - color-scheme-generator
src/provisioning/ansible/roles/settings/vars/main.yml:77   - "{{ settings_spine_config_dir }}/color-scheme-generator"
src/provisioning/ansible/roles/settings/vars/main.yml:88   - { name: csg, template: csg-settings.toml.j2, dest: "{{ settings_spine_config_dir }}/color-scheme-generator/settings.toml" }
src/provisioning/ansible/roles/settings/tasks/main.yml:24   #   the per-tool config subdirs (color-scheme-generator/weg/itr) are ensured
src/provisioning/ansible/roles/verify/vars/main.yml:88      #   config/color-scheme-generator/templates
src/provisioning/ansible/roles/verify/vars/main.yml:94    - config/color-scheme-generator
src/provisioning/ansible/roles/verify/vars/main.yml:95    - config/color-scheme-generator/templates
src/provisioning/ansible/roles/verify/vars/main.yml:140  - config/color-scheme-generator/templates
src/provisioning/ansible/roles/verify/vars/main.yml:216  verify_cli_tools:      # → csg, weg, itr  (lines 216-219)
src/provisioning/ansible/roles/verify/vars/main.yml:339  - { name: csg, dest: "{{ install_dir | trim }}/config/color-scheme-generator/settings.toml" }
src/provisioning/ansible/roles/verify/vars/main.yml:366  #   config/weg/effects.yaml (also in verify_install_spine_files).
src/provisioning/ansible/roles/verify/vars/main.yml:381  - config/color-scheme-generator/templates
src/provisioning/ansible/roles/verify/vars/main.yml:808  - color-scheme-generator
src/provisioning/ansible/roles/verify/tasks/main.yml:672   path: "{{ install_dir | trim }}/config/color-scheme-generator/templates/{{ item }}"
src/provisioning/ansible/roles/verify/tasks/main.yml:682   {{ install_dir | trim }}/config/color-scheme-generator/templates/
src/provisioning/ansible/roles/verify/tasks/main.yml:765   (expected color-scheme-generator/weg/itr settings.toml — done-criterion 5
src/provisioning/ansible/roles/verify/tasks/main.yml:854   - "{{ verify_xdg_config_home }}/color-scheme-generator/settings.toml"
src/provisioning/src/provisioning/cli/main.py:21-24  from cli_output.adapters.factory / domain.enums / domain.views / ports.renderer
src/provisioning/src/provisioning/cli/options.py:5,12  (``cli_output`` documented + imported)
src/provisioning/src/provisioning/__init__.py:3
src/provisioning/pyproject.toml:9   "cli-output",
src/provisioning/pyproject.toml:25  cli-output = { path = "../shared/cli-output", editable = true }
```

Tests (38 hits, 8 files) — the most load-bearing is `tests/architecture/test_layering.py` (17 hits):

```
src/provisioning/tests/architecture/test_layering.py:29-32  Rule 5 (cross-package, §11 boundary):
   "No source file may import any dotfiles-sibling package except cli_output.
    The forbidden set is: core, infrastructure, color_scheme_generator,
    wallpaper_effects_generator, icon_templates_renderer,
    config_assembler_engine, oci_runtime."
src/provisioning/tests/architecture/test_layering.py:104-114  _FORBIDDEN_CROSS_PACKAGE = frozenset({...})
src/provisioning/tests/architecture/test_layering.py:472-492  _allowed_third_party_roots() /
   _import_root() — derives allowed roots from [project].dependencies + [tool.uv.sources]
   and hard-adds {"cli_output"}.
```

Remaining: `tests/unit/test_verify_role.py` (8: `:253`, `:488`, `:1317`, `:1963-1965`,
`:3041`, `:2731`, `:2785`, `:3097-3175`, `:3548`), `tests/integration/test_settings_parity.py` (9),
`tests/unit/test_settings_role.py` (2), `tests/unit/test_assets_role.py:123`,
`tests/unit/adapters/test_yaml_manifest_reader.py:255` (fixture writes
`source: src/cli-tools/color-scheme-generator`).

### 1.4 runtime — 28 code + 86 test hits, 53 files

Runtime imports **none** of the six packages (verified):

```
$ rg -n '^(from|import) (color_scheme_generator|wallpaper_effects_generator|icon_templates_renderer|config_assembler_engine|oci_runtime)' src/runtime --glob '*.py'
EXIT=1        # no matches
```

Coupling is (a) `cli_output` imports, (b) subprocess to the installed binaries, (c) dev-checkout
path fallbacks:

```
src/runtime/src/runtime/cli/main.py:257  from runtime.adapters.csg_adapter import CsgAdapter
src/runtime/src/runtime/cli/main.py:260  from runtime.adapters.itr_adapter import ItrAdapter
src/runtime/src/runtime/cli/main.py:263  from runtime.adapters.weg_adapter import WegAdapter
src/runtime/src/runtime/cli/main.py:275  csg = CsgAdapter(templates_dir=find_templates_dir(install_spine))
src/runtime/src/runtime/cli/main.py:276  weg = WegAdapter()
src/runtime/src/runtime/cli/main.py:277  itr = ItrAdapter()
src/runtime/src/runtime/adapters/csg_adapter.py:141  bin_name = self._csg_bin or "csg"
src/runtime/src/runtime/adapters/csg_adapter.py:155-156  shutil.which(bin_name)
src/runtime/src/runtime/adapters/csg_adapter.py:304  result = subprocess.run(
src/runtime/src/runtime/adapters/weg_adapter.py:208,220-221,364
src/runtime/src/runtime/adapters/itr_adapter.py:132,144-145,423
src/runtime/src/runtime/application/derive.py:158  install_spine / "config" / "color-scheme-generator" / "templates"
src/runtime/src/runtime/application/derive.py:162  "src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates"
src/runtime/src/runtime/application/derive.py:166  Path("src/cli-tools/color-scheme-generator/defaults/templates")
src/runtime/src/runtime/application/derive.py:174  "src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml"
src/runtime/src/runtime/application/derive.py:179  Path("src/cli-tools/wallpaper-effects-generator/defaults/effects.yaml")
src/runtime/src/runtime/application/derive.py:187  install_spine / "config" / "icon-templates-renderer" / "templates"
src/runtime/src/runtime/application/derive.py:195  install_spine / "config" / "icon-templates-renderer" / "icons.yaml"
src/runtime/src/runtime/pyproject.toml:8   "cli-output",
src/runtime/src/runtime/pyproject.toml:25  cli-output = { path = "../shared/cli-output", editable = true }
```

Note the two shapes per input at `derive.py:158-183`: the first candidate is the **spine** path
(deployed), the second is a **repo-relative** `src/cli-tools/...` path (dev checkout only).

Runtime also carries the same §11 rule as provisioning:

```
src/runtime/tests/architecture/test_layering.py:28-32   Rule 5 … except cli_output
src/runtime/tests/architecture/test_layering.py:101-110 _FORBIDDEN_CROSS_PACKAGE = frozenset(…"config_assembler_engine", "oci_runtime"…)
src/runtime/tests/architecture/test_layering.py:806-858 Rule-5 test methods
```

### 1.5 docs/ — 53 hits, 3 files

```
docs/01-dotfiles-provisioning-phase1-plan.md:32,33,34,35,36,37  layout table (all six packages)
docs/01-dotfiles-provisioning-phase1-plan.md:70   §11 boundary statement
docs/01-dotfiles-provisioning-phase1-plan.md:202  "mirrors oci-runtime hexagon + Rule 5 cross-package §11 forbidden set"
docs/01-dotfiles-provisioning-phase1-plan.md:293  scaffold recipe ("deps: typer, pydantic, cli-output, ansible-core; uv.sources for cli-output")
docs/99-dotfiles-hexagonal-architecture.md:248,249,250  csg/weg/itr table
docs/99-dotfiles-hexagonal-architecture.md:654-662      src/ tree (cli-tools/ + shared/)
docs/99-dotfiles-hexagonal-architecture.md:1066         "They stay standalone packages under src/cli-tools/."
docs/02-config-in-spine-pattern.md:22,28,63,68,84,93,190,193,194,217  config-in-spine paths
```

### 1.6 openspec — 590 hits (422 archive / 168 live)

Live specs that describe the current packages: `openspec/specs/cli-runtime-engine-scope/`
(19 hits: `investigation-report.md:5-7,25,84-86`; `investigate-and-design.md:5,30,64,100,161,185,225,234,241,260,265`),
`openspec/specs/cli-output/spec.md` (8), `openspec/specs/oci-strict-hexagonal-layering/spec.md` (13),
`openspec/changes/cli-output-cli-integration/` (35 hits across design 14 / tasks 8 / spec 6 /
proposal 5 / README 2), `openspec/changes/add-icon-templates-renderer/` (44 hits across design 19 /
proposal 11 / specs 8 / tasks 4 / README 2).
Archive is dominated by the oci-runtime remediation series (6 archived changes, ~140 hits).
Full archive tally is in the table above; 104 files.

### 1.7 dotfiles manifests — 8 hits, 3 files

```
dotfiles/provisioning/cli-tools.yaml:5   # … src/cli-tools/openspec/ is NOT an install target and
dotfiles/provisioning/cli-tools.yaml:10    source: src/cli-tools/color-scheme-generator
dotfiles/provisioning/cli-tools.yaml:12    source: src/cli-tools/wallpaper-effects-generator
dotfiles/provisioning/cli-tools.yaml:14    source: src/cli-tools/icon-templates-renderer
dotfiles/provisioning/filesystem.yaml:7,24,25   config/color-scheme-generator[/templates]
dotfiles/provisioning/assets.yaml:20     source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates
```

`dotfiles/provisioning/cli-tools.yaml` is 16 lines and holds **four** entries, the fourth being
`dotfiles-runtime → src/runtime` (lines 15-16), which is a different package from this spike.

### 1.8 `.gitignore` — 2 stale-looking refs

```
.gitignore:17  /src/cli-tools/wallpaper-effects-generator/feedback.md
.gitignore:18  /src/cli-tools/wallpaper-effects-generator/test.sh
```

Both target paths do not exist today:

```
$ ls src/cli-tools/wallpaper-effects-generator/{feedback.md,test.sh}
ls: cannot access '…/feedback.md': No such file or directory
ls: cannot access '…/test.sh': No such file or directory
$ ls src/cli-tools/wallpaper-effects-generator/
docs  pyproject.toml  src  tests  uv.lock
```

### 1.9 `_bmad-output/` — 1120 hits, 139 files

Historical planning/implementation artifacts (`implementation-artifacts/`,
`planning-artifacts/`, `archive/`). No build, gate, or provisioning path reads them. Top files:
`implementation-artifacts/gt-1-1-colorformat-adw-css-template.md` (43),
`implementation-artifacts/1-3-hexagonal-boundary-lock.md` (39),
`archive/review-diff-3.3.txt` (36).

---

## 2. Question 2 — how cross-package dependencies are declared TODAY

### 2.1 No workspace, no root project

```
$ ls pyproject.toml uv.toml .python-version
ls: cannot access 'pyproject.toml': No such file or directory     (exit 2)

$ rg -n 'tool\.uv\.workspace|^\[workspace\]|workspace\.members|members *=' --glob '*.toml' .
EXIT=1        # no matches anywhere
```

There is **no root `pyproject.toml`** and **no `[tool.uv.workspace]`** table in any of the eight
pyprojects. Each of the eight packages is an independent uv project with its own committed
`uv.lock`:

```
$ find . -name pyproject.toml -not -path './.git/*' | sort
./src/cli-tools/color-scheme-generator/pyproject.toml
./src/cli-tools/wallpaper-effects-generator/pyproject.toml
./src/cli-tools/icon-templates-renderer/pyproject.toml
./src/provisioning/pyproject.toml
./src/runtime/pyproject.toml
./src/shared/cli-output/pyproject.toml
./src/shared/config-assembler-engine/pyproject.toml
./src/shared/oci-runtime/pyproject.toml

$ find . -name uv.lock -not -path './.git/*' | sort      # 8 files, one per pyproject
```

### 2.2 Mechanism: bare name in `[project].dependencies` + **relative path** in `[tool.uv.sources]`

The pattern is consistent: the dependency is declared as a **bare name** (sometimes with a version
floor) and then **re-pointed** to a sibling directory by a relative filesystem path with
`editable = true`. There is no version pinning of the internal packages beyond the floor strings, and
no index/registry involvement.

**csg — `src/cli-tools/color-scheme-generator/pyproject.toml:6-14` (verbatim):**

```toml
dependencies = [
    "typer>=0.12",
    "config-assembler-engine",
    "oci-runtime",
    "cli-output",
    "pydantic>=2.0",
    "jinja2>=3.1",
    "rich>=13.0",
]
```

`…/pyproject.toml:39-42` (verbatim):

```toml
[tool.uv.sources]
cli-output = { path = "../../shared/cli-output", editable = true }
config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
oci-runtime = { path = "../../shared/oci-runtime", editable = true }
```

**weg — `src/cli-tools/wallpaper-effects-generator/pyproject.toml:6-14`:**

```toml
dependencies = [
    "cli-output>=0.1.0",
    "config-assembler-engine>=0.1.0",
    "oci-runtime>=0.3.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "typer>=0.27.0",
    "rich>=13.0",
]
```

`…/pyproject.toml:26-29`:

```toml
[tool.uv.sources]
cli-output = { path = "../../shared/cli-output", editable = true }
config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
oci-runtime = { path = "../../shared/oci-runtime", editable = true }
```

**itr — `src/cli-tools/icon-templates-renderer/pyproject.toml:6-14`:**

```toml
dependencies = [
    "typer>=0.12",
    "config-assembler-engine",
    "cli-output",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "ruamel.yaml>=0.18",
    "rich>=13.0",
]
```

`…/pyproject.toml:36-38` — **only two** sources (itr is the one CLI with no `oci-runtime` dependency):

```toml
[tool.uv.sources]
cli-output = { path = "../../shared/cli-output", editable = true }
config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
```

**Shared libs declare no intra-repo deps at all.** Each has an empty `[tool.uv.sources]` table and
no dotfiles-sibling in `dependencies`:

```
src/shared/cli-output/pyproject.toml:6-8            dependencies = ["rich>=13.0"]
src/shared/cli-output/pyproject.toml:17-18          [tool.uv.sources]   (empty)
src/shared/config-assembler-engine/pyproject.toml:6-9   dependencies = ["pydantic>=2.0","pyyaml>=6.0.3"]
src/shared/config-assembler-engine/pyproject.toml:22-23 [tool.uv.sources] (empty)
src/shared/oci-runtime/pyproject.toml:6             dependencies = []
src/shared/oci-runtime/pyproject.toml:22-23         [tool.uv.sources]   (empty)
```

**Two more packages consume `cli-output` the same way** (both outside this spike's deletion set, but
they share the lib):

```
src/runtime/pyproject.toml:8,25        "cli-output",  /  cli-output = { path = "../shared/cli-output", editable = true }
src/provisioning/pyproject.toml:9,25   "cli-output",  /  cli-output = { path = "../shared/cli-output", editable = true }
```

### 2.3 Dependency graph as declared

| consumer | `cli-output` | `config-assembler-engine` | `oci-runtime` |
|---|---|---|---|
| `color-scheme-generator` (csg) | path dep | path dep | path dep |
| `wallpaper-effects-generator` (weg) | path dep | path dep | path dep |
| `icon-templates-renderer` (itr) | path dep | path dep | — |
| `dotfiles-runtime` | path dep | — | — |
| `dotfiles-provision` | path dep | — | — |
| `cli-output` | — | — | — |
| `config-assembler-engine` | — | — | — |
| `oci-runtime` | — | — | — |

Leaf-first order is enforced only by the absence of cycles: the three libs depend on nothing
in-repo, the CLIs depend on the libs, and runtime/provisioning depend on `cli-output` only.

### 2.4 Resolution is frozen into committed locks

Every consumer's `uv.lock` records the resolution as a **relative editable path**, not a registry
entry:

```
src/cli-tools/color-scheme-generator/uv.lock:26   source = { editable = "../../shared/cli-output" }
src/cli-tools/color-scheme-generator/uv.lock:65-69  { name = "cli-output", editable = "../../shared/cli-output" },
                                                    { name = "config-assembler-engine", editable = "../../shared/config-assembler-engine" },
                                                    { name = "oci-runtime", editable = "../../shared/oci-runtime" },
src/cli-tools/color-scheme-generator/uv.lock:233  source = { editable = "../../shared/oci-runtime" }
src/cli-tools/wallpaper-effects-generator/uv.lock:26,49,169,479-481   (same three)
src/cli-tools/icon-templates-renderer/uv.lock:26,49,88-89             (two)
```

Because `uv.lock` was excluded from the reference scan, note that the path relationship **also**
exists in 8 lock files; moving any package requires regenerating every consumer's lock.

### 2.5 Container builds re-declare the same coupling a second time, by COPY path

The two container-mode CLIs ship Dockerfiles **inside** their package tree but address the
**monorepo root** as build context:

`src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base:1-10`:

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY src/cli-tools/color-scheme-generator /app/csg
COPY src/shared/config-assembler-engine /app/config-assembler-engine
COPY src/shared/oci-runtime /app/oci-runtime
COPY src/shared/cli-output /app/cli-output
RUN pip install --no-cache-dir /app/config-assembler-engine /app/oci-runtime /app/cli-output /app/csg && \
```

`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick:9-19`:

```dockerfile
COPY src/shared/config-assembler-engine /app/shared/config-assembler-engine
COPY src/shared/oci-runtime /app/shared/oci-runtime
COPY src/shared/cli-output /app/shared/cli-output
COPY src/cli-tools/wallpaper-effects-generator /app/wallpaper-effects-generator
RUN pip install --no-cache-dir \
    typer pyyaml rich pydantic \
    /app/shared/config-assembler-engine \
    /app/shared/oci-runtime \
    /app/shared/cli-output \
    /app/wallpaper-effects-generator
```

These are the **only** non-doc, non-test code files that reference `src/shared` (verified):

```
$ rg -l 'src/shared' --glob '!*.md' --glob '!*.txt' --glob '!uv.lock' src scripts dotfiles bootstrap.sh Makefile
src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base
src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick
src/shared/oci-runtime/src/oci_runtime/source_locator.py
```

### 2.6 The monorepo layout is a hard-coded runtime assumption in one lib

`src/shared/oci-runtime/src/oci_runtime/source_locator.py:37-39`:

```python
# The monorepo layout marker: a repo root contains both `src/cli-tools` and
# `src/shared` as directories.
_REPO_MARKER_DIRS = ("src", "cli-tools"), ("src", "shared")
```

`…/source_locator.py:50-61` walks up from a candidate until **both** marker dirs exist; `:109-144`
resolves in priority order `--source-root` override → env var (`CSG_SOURCE_ROOT` /
`WEG_SOURCE_ROOT`) → PEP 610 `direct_url.json` → package-location walk, and raises
`SourceRootNotFoundError` otherwise. This is what makes `<cli> install --source-root <repo>` work
from an installed tool (`src/shared/oci-runtime/src/oci_runtime/source_locator.py:1-22`).

### 2.7 Boundary is enforced by two *independent* copy-pasted rule sets

```
src/provisioning/tests/architecture/test_layering.py:104-114  _FORBIDDEN_CROSS_PACKAGE
src/runtime/tests/architecture/test_layering.py:101-110       _FORBIDDEN_CROSS_PACKAGE
```

Both forbid importing `color_scheme_generator`, `wallpaper_effects_generator`,
`icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`, and both allow `cli_output`.
Neither test file imports the other; the sets are duplicated literals.

### 2.8 Docs call these "workspace" dependencies; no workspace exists

`src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md:543-544`:

```
| `config-assembler-engine` | >= 0.1.0 | … | workspace, editable `../../shared/config-assembler-engine` |
| `oci-runtime` | >= 0.3.0 | … | workspace, editable `../../shared/oci-runtime` |
```

`src/cli-tools/wallpaper-effects-generator/docs/ARCHITECTURE_PLAN.md:416-417, 595-596` say
`workspace` / `workspace (>= 0.1.0)`. The actual mechanism is `[tool.uv.sources]` path deps
(§2.2); `[tool.uv.workspace]` does not exist anywhere in the tree (§2.1).

---

## 3. Question 3 — how each package is installed

**All three CLIs are installed with `uv tool install` from a local repo-relative path.** There is no
`pip install` from an index and no published artifact.

Install loop — `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:98-109`:

```yaml
- name: Install csg/weg/itr via uv tool install
  ansible.builtin.command: "uv tool install --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'"
  args:
    creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"
  environment:
    UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"
  loop: "{{ cli_tools }}"
```

Upgrade-every-run loop — `…/cli_tools/tasks/main.yml:117-122`:

```yaml
- name: Upgrade csg/weg/itr tool envs from current repo source
  ansible.builtin.command: "uv tool install --force --no-cache '{{ cli_tools_repo_root }}/{{ item.source }}'"
  environment:
    UV_TOOL_BIN_DIR: "{{ cli_tools_bin_dir }}"
  loop: "{{ cli_tools }}"
  when: not ansible_check_mode
```

Presence check — `…/cli_tools/tasks/main.yml:124-129` (`command -v {{ item.name }}` with
`PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"`).

The loop source of truth — `…/cli_tools/vars/main.yml:56-60`:

```yaml
cli_tools:
  - { name: csg, source: src/cli-tools/color-scheme-generator }
  - { name: weg, source: src/cli-tools/wallpaper-effects-generator }
  - { name: itr, source: src/cli-tools/icon-templates-renderer }
  - { name: dotfiles-runtime, source: src/runtime }
```

and its mirror manifest — `dotfiles/provisioning/cli-tools.yaml:7-16` (`kind: cli-tools`, same four
entries). The comment at `…/vars/main.yml:50-55` states: *"cli_tools: install specs mirroring
dotfiles/provisioning/cli-tools.yaml … Parity with the manifest is locked by a structural test."*

Repo root derivation — `…/cli_tools/vars/main.yml:3-8`:

```yaml
cli_tools_repo_root: "{{ playbook_dir }}/../../../.."
```

Binary dir resolution — `…/cli_tools/vars/main.yml:19-21`: `UV_TOOL_BIN_DIR` → `XDG_BIN_HOME` →
`$HOME/.local/bin`.

**Container images are a second install step** for csg and weg only —
`…/cli_tools/tasks/main.yml:328-340`:

```yaml
- name: Build container images for the container-mode CLIs
  ansible.builtin.command:
    argv:
      - "{{ item.name }}"
      - install
      - "--container-engine"
      - "{{ container_runtime_engine }}"
      - "--source-root"
      - "{{ cli_tools_repo_root }}"
  loop: "{{ cli_tools_image_builds }}"
```

with `cli_tools_image_builds: [{name: csg}, {name: weg}]` (`…/cli_tools/vars/main.yml:46-48`;
comment at `:40-45` states itr is deliberately absent — no container mode).

The shared libs are **not installed standalone**: they reach the host only as transitive editable
deps of the tool install (`uv tool install <path>` resolves the consumer's `[tool.uv.sources]`), and
inside containers only via the Dockerfile `pip install /app/…` lines (§2.5).

`src/cli-tools/openspec/` is explicitly **not** an install target (`dotfiles/provisioning/cli-tools.yaml:5-6`:
*"src/cli-tools/openspec/ is NOT an install target and must not be listed here"*). It contains only
`changes/` and `specs/` directories.

---

## 4. Question 4 — are any of these published anywhere?

**No.** Evidence:

```
$ rg -n 'pypi|index-url|registry|extra-index|publish|\[tool\.uv\]|index' --glob 'pyproject.toml' .
EXIT=1        # zero matches in all 8 pyprojects

$ rg -n -i 'uv publish|twine|testpypi|index-url|extra-index-url|classifiers' --glob '!uv.lock' --glob '!*.md' .
EXIT=1        # zero matches
```

- No `[tool.uv]` index configuration, no `[[tool.uv.index]]`, no `publish` settings.
- No `classifiers`, no `[project.urls]`, no `license`, no `readme` field in any of the six
  pyprojects (each `[project]` table is name/version/description/requires-python/dependencies only —
  see §2.2 excerpts).
- No `README.md` / `CHANGELOG.md` in any of the six package roots:
  `find src/cli-tools src/shared -maxdepth 2 -iname 'README*' -o -iname 'CHANGELOG*'` → no output.
- The only `pypi` strings in the tree are third-party resolution records inside `uv.lock`
  (`source = { registry = "https://pypi.org/simple" }`, e.g.
  `src/shared/oci-runtime/uv.lock:8`, `src/cli-tools/wallpaper-effects-generator/uv.lock:8`).
- `.github/workflows/gates.yml` has five jobs (`contracts`, `ansible-embedded-template-lint`,
  `deploy-coverage`, `ci-gates-parity`, `per-app-drift-symbol-suites`; the `on:` block is at
  `:52-56`); none publishes.
- No requirements/constraints files: `find . -maxdepth 3 -name 'requirements*.txt' -o -name 'constraints*.txt'` → no output.

The ARCHITECTURE_PLAN tables distinguish the two categories explicitly — internal deps are labelled
`workspace` and third-party ones `PyPI` (`src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md:543-551`).

**Consequence stated factually:** the only distribution channel in use is the repo checkout itself,
consumed by `uv tool install <local path>` (§3) and by `pip install /app/...` inside the two
Dockerfiles (§2.5).

---

## 5. Question 5 — the deletion ritual actually used for `src/gui-tools`

### 5.1 History of the directory

```
$ git -C /home/inumaki/Development/dotfiles-v3 log --oneline -20 -- src/gui-tools
651d4ec5 feat(provisioning): install capture-tool CLI from the pinned ags-apps unit
8d733b3f chore(btop-theme-studio): delete the in-repo source and assert the consumption shape
8ec816f6 feat(ags_apps): consume icme from the unit + bump pin to v0.3.7
52654621 chore(wallpaper-selector): delete the in-repo source and retire its drift suite
71958a50 chore(capture-tool): delete the AGS GUI source and retire its gates
bb2291dc refactor(gui_tools): retire per-file notifications placement
f5cf4037 retire the per-file hypr-pano deploy; delete the in-repo source
18851222 slice 3: retire the bar-only parity, audio and symbol gates
1981fba2 Merge feat/btop-themes: add btop-theme-studio
7a2a168a feat(REQ-010): install the platform as one versioned unit; delete the in-place copy (AD-17/AD-23)
85b84623 feat(gui-tools): add btop theme studio app, key→widget map and live engine
0d52e47d feat(REQ-009): extract the platform in-place into the ags-platform package (AD-1/AD-2/AD-17/AD-20)
d843d672 feat(REQ-005): one event client
36be78f4 feat(harden-extraction-gates): widen ags-typecheck, add bar-typecheck CI job, wire per-app suites
0a70dee5 feat(REQ-004): vendor generated contract bindings + cross-repo gate (slice 1)
4d31ac17 … (pre-split app work)
```

### 5.2 The pattern: one deletion commit per app, each carrying source + gates + a guard

| commit | stat (head) | what it shows |
|---|---|---|
| `71958a50` `chore(capture-tool): delete the AGS GUI source and retire its gates` | `.github/workflows/gates.yml \| 62 +-` / `.gitignore \| 29 +-` / `Makefile \| 234 ++------` | source removal + gate retirement in the same commit |
| `f5cf4037` `retire the per-file hypr-pano deploy; delete the in-repo source` | `Makefile \| 4 +-` / `src/gui-tools/hypr-pano/Makefile \| 12 -` / `…/app.tsx \| 16 -` | per-app dir deletion |
| `bb2291dc` `refactor(gui_tools): retire per-file notifications placement` | `src/gui-tools/notifications/Makefile \| 9 -` / `app.tsx \| 88 -` / `lib/icon-registry.ts \| 39 -` | per-app dir deletion |
| `52654621` `chore(wallpaper-selector): delete the in-repo source and retire its drift suite` | `Makefile \| 7 +-` / `src/gui-tools/wallpaper-selector/Makefile \| 13 -` / `README.md \| 57 --` | source + drift-suite retirement |
| `8ec816f6` `feat(ags_apps): consume icme from the unit + bump pin to v0.3.7` | fixture move + `src/gui-tools/icon-color-mapping-editor/Makefile \| 18 -` / `README.md \| 81 ---` | consume-then-delete |
| `8d733b3f` `chore(btop-theme-studio): delete the in-repo source and assert the consumption shape` | `scripts/deploy-coverage.py \| 149 +-` / `src/gui-tools/btop-theme-studio/Makefile \| 31 -` / `README.md \| 59 -` | **"and assert the consumption shape"** — guard added with the deletion |
| `651d4ec5` `feat(provisioning): install capture-tool CLI from the pinned ags-apps unit` | `.gitignore \| 17 -` / `Makefile \| 9 +-` / `src/gui-tools/capture-tool/README.md \| 51 -` | last app's source + the backend handoff |

### 5.3 The final catch-all commit

`50641af0` (`chore: remove the now-empty src/gui-tools …`) is the terminal step. Its own message
documented the ritual and is quoted verbatim:

> The directory was empty and untracked after the last app moved into the pinned ags-apps unit, so
> Git could not record the removal (it is removed from the filesystem). This commit retires the
> remaining dead references and turns the absence into a hard guard:
> - deploy-coverage asserts src/gui-tools/ itself does not exist (catch-all for any reappearance), with a negative test.
> - gui_tools role tests pin the same absence.
> - drop the runtime selector audit that read the moved WallpaperSelectorWindow.tsx …
> - refresh stale prose in the gui_tools vars, Makefile, AGENTS.md and docs …

Its diffstat is **9 files, +112 / −65**, and **contains no source deletions** — the sources were
already gone:

```
$ git show --stat 50641af0 | tail -12
 AGENTS.md                                          |  5 ++-
 Makefile                                           |  6 +--
 docs/101-ags-platform-architecture.md              |  3 +-
 docs/HANDOFF-ags-platform.md                       |  5 ++-
 scripts/deploy-coverage.py                         | 29 +++++++++++++
 .../ansible/roles/gui_tools/vars/main.yml          | 29 ++++++++-----
 .../tests/unit/test_compositor_configs_role.py     | 30 +++++++++++--
 src/provisioning/tests/unit/test_gui_tools_role.py | 21 ++++++++--
 .../tests/unit/test_wallpaper_visible_first.py     | 49 ++++------------------
 9 files changed, 112 insertions(+), 65 deletions(-)
```

### 5.4 The merge commit adds nothing beyond its second parent

```
$ git log --oneline -1 fb94b64e
fb94b64e merge ticket/guitoolsrm-delete: remove src/gui-tools and add the absence guard

$ git show --stat fb94b64e | head -3
Merge: 4e84f7f4 50641af0
$ git diff --stat 4e84f7f4 fb94b64e      # identical 9-file / +112 / -65 stat
```

So the merge is a pure fast-forward-equivalent integration of a branch whose single payload commit
was `50641af0`; the merge itself introduced no additional edits.

### 5.5 Current state of the target directory

```
$ ls src/gui-tools
ls: cannot access 'src/gui-tools': No such file or directory
```

The absence is now asserted by `scripts/deploy-coverage.py:808-828` (plus the `RETIRED_*_DIR`
constants at `:208`, `:213`, `:223`, `:231` region) and by the gui_tools role tests
(`src/provisioning/tests/unit/test_gui_tools_role.py`, `test_compositor_configs_role.py`).

### 5.6 What the ritual did **not** do

- It did not add any gate that *runs the moved app's tests in this repo*; the gates were **retired**
  (`Makefile:40-44`, `96-104`, `.github/workflows/gates.yml:21-41`).
- It did not introduce a workspace or a packaging change — the apps moved to an external "unit"
  (`ags-apps`) pinned by tag, consumed by the `ags_apps` role.
- It did **not** touch the Python CLI packages: `src/cli-tools/` and `src/shared/` are untouched by
  every commit in §5.2/§5.3 (diffstats list only `src/gui-tools/**`, `Makefile`,
  `.github/workflows/gates.yml`, `.gitignore`, `scripts/deploy-coverage.py`, `docs/`,
  `src/provisioning/**`).

---

## 6. Question 6 — package sizes (factual)

`src` = `*.py` under `<pkg>/src`; `tests` = `*.py` under `<pkg>/tests`; "all files" = every tracked
or untracked file under the package dir (includes `uv.lock`, YAML defaults, Dockerfiles, docs).

| package | src files | src lines | test files | test lines | all files |
|---|---|---|---|---|---|
| `src/cli-tools/color-scheme-generator` | 60 | 4 684 | 59 | 11 765 | 1 665 |
| `src/cli-tools/wallpaper-effects-generator` | 55 | 4 398 | 39 | 6 473 | 1 622 |
| `src/cli-tools/icon-templates-renderer` | 50 | 3 375 | 44 | 4 756 | 1 514 |
| `src/shared/cli-output` | 12 | 461 | 9 | 496 | 47 |
| `src/shared/config-assembler-engine` | 30 | 880 | 19 | 1 544 | 423 |
| `src/shared/oci-runtime` | 67 | 4 806 | 83 | 13 352 | 288 |
| *(context)* `src/runtime` | 108 | 24 988 | 133 | 42 951 | 2 961 |
| *(context)* `src/provisioning` | 17 | 1 348 | 54 | 22 316 | 4 521 |

Reproduce:

```
for p in src/cli-tools/*/ src/shared/*/; do
  s=$(find $p/src -name '*.py' | wc -l); sl=$(find $p/src -name '*.py' -print0 | xargs -0 cat | wc -l)
  t=$(find $p/tests -name '*.py' | wc -l); tl=$(find $p/tests -name '*.py' -print0 | xargs -0 cat | wc -l)
  echo "$p src:$s/$sl tests:$t/$tl all:$(find $p -type f | wc -l)"
done
```

Total for the six deletion candidates: **274 src files / 19 604 src lines**, **253 test files /
38 386 test lines**. (`oci-runtime` alone is 4 806 src lines / 13 352 test lines — larger than any
single CLI.)

One structural asymmetry: **csg and weg have no `Makefile`; itr does.**

```
$ ls src/cli-tools/*/Makefile src/shared/*/Makefile
src/cli-tools/icon-templates-renderer/Makefile
src/shared/config-assembler-engine/Makefile
src/shared/oci-runtime/Makefile
```

`src/shared/cli-output` also has none. The three that exist expose `test`/`lint`/`format`/`build`
targets, e.g. `src/cli-tools/icon-templates-renderer/Makefile:1-4`
(`test: uv run pytest tests/ -v`, `lint: uv run ruff check src/ tests/`). csg/weg tests are runnable
only by invoking `uv run pytest` by hand from the package dir; nothing in the repo does it (see §1.1).

---

## 7. Deletion blast radius

Checklist of every `file:line` that names one of the six packages **and** must change if the package
moves out of this repo. Grouped by what kind of edit it is. Items with `(parity)` are locked by a
test that will fail if only one side is edited.

### 7.1 Install / provisioning shape (per-package)

- [ ] `dotfiles/provisioning/cli-tools.yaml:9-14` — `source: src/cli-tools/<pkg>` entries; entry must
      move to the new distribution channel (4 entries incl. `dotfiles-runtime` at `:15-16`).
- [ ] `src/provisioning/ansible/roles/cli_tools/vars/main.yml:56-60` — `cli_tools` install list;
      `(parity)` with the manifest above, locked by
      `src/provisioning/tests/unit/test_cli_tools_role.py:692-702`
      (`test_cli_tools_parity_with_manifest`, asserts exact `(name, source)` set equality).
- [ ] `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:98-109` — `uv tool install --no-cache
      '<repo>/{{ item.source }}'`; local-path form only.
- [ ] `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:117-122` — `uv tool install --force`.
- [ ] `src/provisioning/ansible/roles/cli_tools/tasks/main.yml:328-340` — `<cli> install
      --source-root {{ cli_tools_repo_root }}`; depends on the monorepo marker (§7.4).
- [ ] `src/provisioning/ansible/roles/cli_tools/vars/main.yml:40-48` — `cli_tools_image_builds`
      (csg, weg) and the itr-exemption comment.
- [ ] `src/provisioning/ansible/roles/cli_tools/vars/main.yml:8` — `cli_tools_repo_root` derivation.

### 7.2 Deployed artifacts sourced from package trees

- [ ] `src/provisioning/ansible/roles/assets/vars/main.yml:72` — csg templates copied from
      `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/`.
- [ ] `dotfiles/provisioning/assets.yaml:20` — same source path in the manifest `(parity)` with `:72`.
- [ ] `src/provisioning/ansible/roles/assets/vars/main.yml:37,42,63,65` — target paths and prose
      (spine `config/color-scheme-generator/templates`).
- [ ] `src/runtime/src/runtime/application/derive.py:158-183` — dev-checkout fallback candidates
      hard-code `src/cli-tools/...`; the spine candidate stays, the repo candidate dies.
- [ ] `src/runtime/src/runtime/application/doctor_check` paths — `src/runtime/tests/unit/test_doctor_check.py:543,548`
      assert both repo paths exist.
- [ ] `src/runtime/tests/unit/test_derive_input_provenance.py:41,49,136` — asserts the repo-relative
      candidates and notes *"The removed implicit walk searched install_spine.parents for
      src/cli-tools"*.

### 7.3 Spine / config directories named after the tools (survive a repo move, but readers will look)

- [ ] `src/provisioning/ansible/roles/filesystem/vars/main.yml:45,56,57` — spine dirs
      `config/color-scheme-generator[/templates]`.
- [ ] `dotfiles/provisioning/filesystem.yaml:7,24,25` — same, manifest side `(parity)`.
- [ ] `src/provisioning/ansible/roles/config_links/vars/main.yml:62,77,101` — `~/.config/<tool>`
      symlink names.
- [ ] `src/provisioning/ansible/roles/settings/vars/main.yml:77-80` (`settings_config_dirs`, three
      per-tool subdirs) and `:88-91` (`settings_files`, three rendered `settings.toml` destinations).
- [ ] `src/provisioning/ansible/roles/settings/tasks/main.yml:24` — prose.
- [ ] `src/provisioning/ansible/roles/verify/vars/main.yml:88,94,95,140,216-219,339,366,381,808-810`
      — spine dirs, `verify_cli_tools: [csg, weg, itr]`, settings dests, asset dirs, config-link names.
- [ ] `src/provisioning/ansible/roles/verify/tasks/main.yml:672,682,765,854` — template file asserts,
      settings parse gates, `~/.config/color-scheme-generator/settings.toml`.

### 7.4 Container build context (the hardest coupling)

- [ ] `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base:3-7`
      — four `COPY src/...` lines assume repo-root context and the sibling `src/shared` layout.
- [ ] `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick:9-19`
      — same four-way assumption.
- [ ] `src/shared/oci-runtime/src/oci_runtime/source_locator.py:37-39,50-61` — `_REPO_MARKER_DIRS`
      requires **both** `src/cli-tools` and `src/shared` to exist under one root.
- [ ] `src/shared/oci-runtime/tests/unit/domain/test_source_locator.py:19,21,31,39,116,142,186` —
      fixtures build a fake monorepo with exactly those two dirs.
- [ ] `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_image_lifecycle.py:283-285` —
      asserts `Dockerfile.<suffix>` exists next to the adapter module.

### 7.5 Dependency declarations (each move = new source spec in every consumer)

- [ ] `src/cli-tools/color-scheme-generator/pyproject.toml:8-10` + `:39-42`
- [ ] `src/cli-tools/wallpaper-effects-generator/pyproject.toml:7-9` + `:26-29`
- [ ] `src/cli-tools/icon-templates-renderer/pyproject.toml:8-9` + `:36-38`
- [ ] `src/cli-tools/*/uv.lock` — 3 lock files record `editable = "../../shared/<lib>"` (lines cited
      in §2.4); a lib move invalidates all three.
- [ ] `src/shared/cli-output/uv.lock`, `src/shared/config-assembler-engine/uv.lock`,
      `src/shared/oci-runtime/uv.lock` — 3 more locks.
- [ ] `src/runtime/pyproject.toml:8,25` and `src/provisioning/pyproject.toml:9,25` — `cli-output`
      path dep in the two packages that stay behind.

### 7.6 Architecture / boundary tests that will fail first

- [ ] `src/provisioning/tests/architecture/test_layering.py:29-32,104-114,472-492` — Rule 5 forbidden
      set lists all five sibling import roots; `_allowed_third_party_roots()` reads
      `[tool.uv.sources]` keys.
- [ ] `src/runtime/tests/architecture/test_layering.py:28-32,101-110,806-858` — duplicate of the same
      rule (independent literal).
- [ ] `src/runtime/tests/integration/test_csg_adapter_integration.py:59,68,78,108` and
      `test_itr_adapter_integration.py:25,34` and `test_csg_determinism.py:278,288,329` — fixtures
      locate `src/cli-tools/<pkg>/defaults/templates` by walking parents.
- [ ] `src/runtime/tests/unit/test_csg_adapter.py:170,178,436,444`,
      `test_itr_adapter.py:180,188,488,496`, `test_weg_adapter.py:139,147,386,392` — same pattern.
- [ ] `src/provisioning/tests/unit/test_assets_role.py:123` and
      `test_yaml_manifest_reader.py:255` — asset relocation map + a fixture that writes
      `source: src/cli-tools/color-scheme-generator`.
- [ ] `src/provisioning/tests/unit/test_verify_role.py:1963-1965` — pins `verify_cli_tools ==
      ["csg","weg","itr"]`.

### 7.7 Documentation (no gate, will silently rot)

- [ ] `docs/01-dotfiles-provisioning-phase1-plan.md:32-37,70,202,293` — layout + §11 + scaffold recipe.
- [ ] `docs/99-dotfiles-hexagonal-architecture.md:248-250,654-662,1066` — csg/weg/itr table, src tree,
      *"They stay standalone packages under src/cli-tools/."*
- [ ] `docs/02-config-in-spine-pattern.md:22,28,63,68,84,93,190,193,194,217`.
- [ ] `src/cli-tools/*/docs/ARCHITECTURE_PLAN.md` (§11 dependency tables at csg `:543-544`, weg
      `:416-417,595-596`) — these move with the packages, but their "workspace" wording is already
      wrong (§2.8).
- [ ] `openspec/specs/cli-runtime-engine-scope/*` (19 hits), `openspec/specs/cli-output/spec.md` (8),
      `openspec/specs/oci-strict-hexagonal-layering/spec.md` (13) — live specs naming the paths.
- [ ] `openspec/changes/cli-output-cli-integration/**` (35), `openspec/changes/add-icon-templates-renderer/**` (44).
- [ ] `spikes/btop-theme-prototype/README.md:9`, `FINDINGS.md:144` — reference the csg paths/templates.
- [ ] `.opencode/plans/csg-fix-known-bugs.md:7,84` — names the package dir and `uv run pytest` cwd.

### 7.8 Things that need **no** change (verified)

- [ ] `Makefile` — 0 references (§1.1). No gate to retire.
- [ ] `.github/workflows/gates.yml` — 0 references; six jobs, none package-specific.
- [ ] `bootstrap.sh` — 0 path references; 7 prose mentions of the `cli_tools` role
      (`:46,54,167,182,207,222,408`) hold as long as the role name survives.
- [ ] `scripts/*.py` — only the role name (`deploy-coverage.py:209,819`,
      `ansible-embedded-template-lint.py:40`).
- [ ] `src/runtime` source — imports none of the six (§1.4); subprocess + `shutil.which` is
      already the boundary.
- [ ] `_bmad-output/` (1120 hits) — historical artifacts; nothing reads them at build or gate time.

### 7.9 Stale references present **today** (independent of any split)

- [ ] `.gitignore:17,18` — ignores `src/cli-tools/wallpaper-effects-generator/{feedback.md,test.sh}`;
      neither file exists (§1.8).
- [ ] `src/cli-tools/*/docs/ARCHITECTURE_PLAN.md` — calls path deps "workspace" while no
      `[tool.uv.workspace]` exists (csg `:543-544`, weg `:416-417,595-596`).
- [ ] `src/runtime/src/runtime/application/derive.py:162,166,174,179` — dev fallbacks point at
      `src/cli-tools/.../defaults/...` while the packaged defaults live at
      `.../src/<pkg>/defaults/...`; both variants are kept, one per package.
- [ ] `src/cli-tools/openspec/` — a second, nested OpenSpec root inside the CLI tree that is
      explicitly not a package (5 files: `changes/fix-container-engine-plumbing/{proposal,design,tasks}.md`
      + `.openspec.yaml`, and `specs/no-spec-changes.md`).

---

## 8. Open questions

Facts that the evidence above does not settle, each stated as a question:

1. **Split granularity.** `cli-output` has 5 in-repo consumers (3 CLIs + runtime + provisioning);
   `config-assembler-engine` has 3; `oci-runtime` has 2. If the libs move separately from the CLIs,
   none of the current `[tool.uv.sources]` relative paths (`../../shared/...`, `../shared/...`) can
   remain — what channel replaces them is not decided anywhere in the tree (§4 shows no publishing
   config exists).
2. **Container build context.** `Dockerfile.base` / `Dockerfile.imagemagick` copy from the repo
   root, and `source_locator._REPO_MARKER_DIRS` requires `src/cli-tools` **and** `src/shared` under
   one root. No document states how the build context would be assembled from separate repos.
3. **No test gate covers these packages.** `make gates-ci` runs five gates, none of which touches
   `src/cli-tools/*` or `src/shared/*` (§1.1). Whether the 253 test files / 38 386 lines currently
   pass is not asserted by anything this repo runs.
4. **csg / weg have no `Makefile`.** itr, config-assembler-engine and oci-runtime do (§6). Whether
   that is intentional or drift is not recorded.
5. **`src/cli-tools/openspec/`** lives inside the CLI tree but is explicitly not installable
   (`dotfiles/provisioning/cli-tools.yaml:5-6`). Its ownership after a split is unstated.
6. **`derive.py` dual candidates.** Two repo-relative fallbacks per input kind
   (`:162` vs `:166`, `:174` vs `:179`) suggest a layout that changed; which is authoritative is not
   documented.
7. **Delete-and-assert ritual scope.** The `src/gui-tools` ritual ended with a catch-all
   "directory must not exist" guard (`scripts/deploy-coverage.py:808-828`) plus a negative test. No
   equivalent guard shape exists for `src/cli-tools` or `src/shared`, and `deploy-coverage.py` has no
   constant naming those trees.
8. **`_bmad-output/` (1120 hits) and `openspec/changes/archive/` (422 hits)** — whether either is
   in scope for reference cleanup is not stated in AGENTS.md or in any spec read here.

---

## 9. Verify

Every command below was run from `/home/inumaki/Development/dotfiles-v3` (repo) or
`/home/inumaki/Development/dotfiles-v3/.worktrees/clirsplit` (worktree), as noted. Each is
independently re-runnable.

```bash
# --- V1: totals (3346 lines / 635 files) ---
cd /home/inumaki/Development/dotfiles-v3
rg -n --hidden -g '!.git' -g '!.worktrees' -g '!uv.lock' \
  -e 'src/cli-tools' -e 'src/shared' -e 'color-scheme-generator' \
  -e 'wallpaper-effects-generator' -e 'icon-templates-renderer' \
  -e 'cli-output' -e 'cli_output' -e 'config-assembler-engine' \
  -e 'config_assembler_engine' -e 'oci-runtime' -e 'oci_runtime' . \
  > /tmp/opencode/s4_hits.txt
wc -l /tmp/opencode/s4_hits.txt          # expect: 3346
cut -d: -f1 /tmp/opencode/s4_hits.txt | sort -u | wc -l   # expect: 635

# --- V2: Makefile / scripts / CI carry no path references ---
rg -n 'color-scheme|wallpaper-effects|icon-templates|shared|cli-output|oci-runtime|config-assembler' Makefile
rg -n 'pytest' Makefile                  # expect: exactly one line, Makefile:14, src/runtime
rg -c 'src/cli-tools|src/shared' scripts/*.py .github/workflows/gates.yml   # expect: no output
grep -n '^GATES :=' -A2 Makefile

# --- V3: no workspace, no root project ---
ls pyproject.toml uv.toml .python-version            # expect: all "No such file"
rg -n 'tool\.uv\.workspace|^\[workspace\]' --glob '*.toml' .   # expect: exit 1, no matches
find . -name pyproject.toml -not -path './.git/*' | sort       # expect: 8 files
find . -name uv.lock -not -path './.git/*' | sort              # expect: 8 files

# --- V4: dependency declarations ---
rg -n -A5 '\[tool\.uv\.sources\]' --glob 'pyproject.toml' .
sed -n '6,14p;39,42p' src/cli-tools/color-scheme-generator/pyproject.toml
sed -n '6,14p;26,29p' src/cli-tools/wallpaper-effects-generator/pyproject.toml
sed -n '6,14p;36,38p' src/cli-tools/icon-templates-renderer/pyproject.toml
rg -n 'editable = "\.\./\.\./shared' src/cli-tools/*/uv.lock

# --- V5: install mechanism ---
sed -n '98,109p;117,122p;124,129p;328,340p' \
  .worktrees/clirsplit/src/provisioning/ansible/roles/cli_tools/tasks/main.yml
sed -n '56,60p' .worktrees/clirsplit/src/provisioning/ansible/roles/cli_tools/vars/main.yml
cat -n .worktrees/clirsplit/dotfiles/provisioning/cli-tools.yaml

# --- V6: nothing published ---
rg -n 'pypi|index-url|registry|extra-index|publish|\[tool\.uv\]|index' --glob 'pyproject.toml' .   # exit 1
rg -n -i 'uv publish|twine|testpypi|index-url|extra-index-url|classifiers' \
   --glob '!uv.lock' --glob '!*.md' .                                                             # exit 1
find src/cli-tools src/shared -maxdepth 2 \( -iname 'README*' -o -iname 'CHANGELOG*' \)           # empty
grep -n '^  [a-z0-9-]*:$' .worktrees/clirsplit/.github/workflows/gates.yml                        # 5 jobs

# --- V7: gui-tools deletion ritual ---
git log --oneline -20 -- src/gui-tools
git show --stat 50641af0 | tail -12          # 9 files, +112/-65, no source deletions
git diff --stat 4e84f7f4 fb94b64e            # identical stat
git show --name-status 50641af0 | grep '^D'  # expect: no output
ls src/gui-tools                             # expect: No such file or directory

# --- V8: sizes ---
for p in src/cli-tools/*/ src/shared/*/; do
  s=$(find $p/src -name '*.py' | wc -l); sl=$(find $p/src -name '*.py' -print0 | xargs -0 cat | wc -l)
  t=$(find $p/tests -name '*.py' | wc -l); tl=$(find $p/tests -name '*.py' -print0 | xargs -0 cat | wc -l)
  echo "$p src:$s/$sl tests:$t/$tl all:$(find $p -type f | wc -l)"
done
ls src/cli-tools/*/Makefile src/shared/*/Makefile   # 3 files: itr, config-assembler-engine, oci-runtime

# --- V9: runtime imports none of the six; coupling is subprocess ---
rg -n '^(from|import) (color_scheme_generator|wallpaper_effects_generator|icon_templates_renderer|config_assembler_engine|oci_runtime)' \
   src/runtime --glob '*.py'                    # expect: exit 1
rg -n 'subprocess.run|shutil.which' src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py

# --- V10: monorepo marker is a runtime assumption ---
sed -n '37,61p' src/shared/oci-runtime/src/oci_runtime/source_locator.py
sed -n '1,19p' src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base
sed -n '9,19p' src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick

# --- V11: local-hole references that are already stale ---
ls src/cli-tools/wallpaper-effects-generator/{feedback.md,test.sh}   # expect: both absent
sed -n '543,544p' src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md
rg -n 'workspace' src/cli-tools/*/docs/ARCHITECTURE_PLAN.md | head
```

**Exit codes / observations recorded during this investigation**

| check | result |
|---|---|
| `wc -l /tmp/opencode/s4_hits.txt` | `3346` |
| unique files in hit list | `635` |
| `rg 'tool\.uv\.workspace'` | exit 1, no matches |
| `ls pyproject.toml` | exit 2, absent |
| `rg pypi/registry/publish --glob pyproject.toml` | exit 1, no matches |
| `rg '^  [a-z0-9-]+:$' .github/workflows/gates.yml` | 6 matches = `push:` plus 5 job keys (`contracts`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`, `per-app-drift-symbol-suites`) |
| `rg 'pytest' Makefile` | 1 line (`Makefile:14`, `src/runtime` only) |
| `git show --name-status 50641af0 \| grep '^D'` | no output (no deletions in the terminal commit) |
| `ls src/gui-tools` | `No such file or directory` |
| runtime imports of the six packages | exit 1, none |
| `ls src/cli-tools/*/Makefile src/shared/*/Makefile` | 3 files (itr, config-assembler-engine, oci-runtime) |
