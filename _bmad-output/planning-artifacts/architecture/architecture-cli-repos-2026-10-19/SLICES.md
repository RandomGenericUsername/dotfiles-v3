# Migration Slices — six packages out of `dotfiles-v3`

Sequential, destructive-last. One slice per target (plus one prerequisite slice). No slice starts
before its predecessor is merged on `master`.

Conventions used below:

```bash
# Consumer-side variables. CLI_REPO_BASE is set once OPEN-1 (hosting) is resolved.
CLI_REPO_BASE="https://github.com/<owner>"
DTF=/home/inumaki/Development/dotfiles-v3            # main checkout
WT=$DTF/.worktrees/<slice-id>                        # this slice's worktree
```

Every acceptance gate is a command with an expected observable. “Expect exit 0” means the command
itself proves the claim; a passing gate that only greps prose is not used.

---

## S0 — Prerequisites in `dotfiles-v3` (no extraction)

**Scope.** Make the suites provably green and hermetic, add the `--version` handshake, land the
invocation contract inside the in-tree `cli-output`, and record the baseline. Nothing is deleted,
nothing is tagged.

**Entry criteria.**

- `master` clean; `make gates-ci` exit 0.
- Worktree created: `bash scripts/worktree-guard.sh create s0 cli-split-prereqs`.

**Steps.**

1. Add `tests/conftest.py` to each of the six packages with an autouse fixture that sets
   `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` to per-test temp
   dirs and `chdir`s to a temp dir (AD-8). Add one canary test per package asserting the fixture is
   active (`os.environ["XDG_CONFIG_HOME"]` is under the pytest tmp root). Add `pytest` (and
   `pytest-cov`) to the dev dependency group of `cli-output` and `config-assembler-engine`, which
   currently have none, so `uv run --directory <pkg> pytest` works uniformly.
2. Fix the two known environment-dependent tests **in the tests**, not the resolvers:
   `color-scheme-generator/tests/unit/adapters/test_template_dir_resolver.py::…::test_resolve_falls_back_to_package_defaults`
   and `icon-templates-renderer/tests/unit/adapters/test_assembled_config_resolver.py::…::test_resolves_bundled_default`.
3. Run the full six suites and record the baseline in the slice’s evidence block. Any failure other
   than the two above is triaged: fixed in this slice, or filed as a `bug` ticket and the affected
   package is **not** a valid extraction target until green (AD-12).
4. Add `--version` to `csg`, `weg`, `itr`: prints `<package-version> contract <cli-output-version>`
   (needed by AD-11 to assert both pins by execution).
5. Add `cli_output.invocation` (per-CLI record: argv template, env keys, required artifacts, exit
   semantics, timeout) and `cli_output.invocation.testkit` inside `src/shared/cli-output`; bump its
   version to `0.2.0` in-tree. Rewrite the runtime adapter contract tests to assert against the
   record instead of their own literals (`S1` §6.1).
6. Add `make hermetic` to the dotfiles `Makefile` (runs the six suites under a scrubbed env) — a
   developer target only, not added to `GATES`.

**Acceptance gates.**

```bash
cd "$WT"

# 1. Every suite is green in the ambient environment (was: 2 failures with a spine present).
for p in src/shared/cli-output src/shared/config-assembler-engine src/shared/oci-runtime \
         src/cli-tools/icon-templates-renderer src/cli-tools/wallpaper-effects-generator \
         src/cli-tools/color-scheme-generator; do
  uv run --directory "$p" pytest -q || exit 1
done
# expect: exit 0 for all six; record "<N> passed" per package

# 2. Hermetic: empty HOME + XDG, foreign cwd, still green.
env -u XDG_CONFIG_HOME HOME="$(mktemp -d)" TMPDIR=/tmp \
  make hermetic
# expect: exit 0; canary tests present in every package

# 3. Version handshake exists and is correct.
for b in itr weg csg; do "$b" --version; done
# expect: three lines "<pkg-version> contract <cli-output-version>", pkg 0.1.0, contract 0.2.0

# 4. Contract is consumed by the runtime, not duplicated.
uv run --directory src/runtime pytest tests/unit/test_csg_adapter.py \
  tests/unit/test_weg_adapter.py tests/unit/test_itr_adapter.py -q
# expect: exit 0; 33 passed (S1 §6.2) or more after migration

# 5. Repo gates unchanged.
make gates-ci && make deploy-coverage
# expect: exit 0, five gates, deploy-coverage PASS
```

**Rollback.** Revert the slice branch; no external artifact exists.

**Deletion step.** None.

---

## Slice template (applies to S1–S6)

Each target slice executes the same loop (AD-13):

1. **Create** the repo from the birth checklist (`ARCHITECTURE-SPINE.md` § Repo Birth Checklist).
2. **Import** the package tree at its current path as the repo root; harness files from `mu`.
3. **Repoint** in-repo dependencies from path sources to git tags (AD-3); regenerate locks.
4. **Green + tag**: `make gates` green on a fresh clone → tag `vX.Y.Z` → CI release artifacts.
5. **Rewire** `dotfiles-v3` consumption to the tag.
6. **Prove by execution** (install, run, and — for container CLIs — build an image).
7. **Delete** the in-tree copy plus every reference the deletion orphaned.
8. **Merge**. Next slice only after this merge.

Rollback for every slice: bump the consumer pin back to the previous tag (or none) and
`git revert` the deletion commit. A published tag is never deleted or moved.

---

## S1 — `cli-output` → its own repo

**Scope.** Extract `src/shared/cli-output` (8 test files, 461 src lines). Consumers: runtime,
provisioning, csg, weg, itr (all five today). It also carries the invocation contract from S0.

**Entry criteria.** S0 merged; OPEN-1 (hosting), OPEN-4 (names), OPEN-5 (license) and OPEN-7
(`cli-output` charter) resolved; repo created with the birth checklist; `master` green.

**Steps.**

1. Import tree: `pyproject.toml`, `src/cli_output/`, `tests/`, `uv.lock` as repo root. Add harness.
2. Re-point `cli_output`’s own `[tool.uv.sources]` to empty (it has no sibling deps).
3. Bump version to `0.2.0` (carries the invocation contract added in S0) and tag `v0.2.0`.
4. In `dotfiles-v3`, replace every `cli-output` path source with a git source at `v0.2.0`:
   `src/runtime/pyproject.toml`, `src/provisioning/pyproject.toml`, and each still-in-tree CLI’s
   `pyproject.toml`; regenerate all five locks.
5. Delete `src/shared/cli-output/`.
6. Update the two architecture-test forbidden sets
   (`src/runtime/tests/architecture/test_layering.py:101`, `src/provisioning/tests/architecture/test_layering.py:97`)
   so `cli_output` remains the one allowed sibling root but is resolved as a git dependency
   (`_allowed_third_party_roots()` reads `[tool.uv.sources]`, so it must accept a git source, not
   only a path).

**Acceptance gates.**

```bash
cd "$WT"

# New repo, fresh clone.
git clone "$CLI_REPO_BASE/cli-output" /tmp/opencode/cli-output && cd /tmp/opencode/cli-output
make sync && make gates && make hermetic && uv lock --check && uv build
# expect: exit 0; dist contains cli_output-0.2.0-*.whl + .tar.gz
cd "$WT"

git ls-remote --tags "$CLI_REPO_BASE/cli-output" v0.2.0
# expect: exactly one line, peeled tag + commit

# No path/editable pin survives anywhere.
rg -n 'cli-output = \{ path|path = "\.\./shared/cli-output"|editable = true' src --glob 'pyproject.toml'
# expect: exit 1 (no matches)

# Consumers resolve the published package, not a checkout.
uv run --directory src/runtime python -c \
  "import cli_output, pathlib; p=pathlib.Path(cli_output.__file__).resolve(); print(p); assert 'src/shared' not in str(p)"
# expect: path under .venv/lib/.../site-packages/cli_output, exit 0

# Runtime + provisioning suites.
uv run --directory src/runtime pytest tests/ -q
uv run --directory src/provisioning pytest tests/unit tests/integration/test_settings_parity.py -q
# expect: exit 0

make gates-ci && make deploy-coverage
# expect: exit 0

# Deletion proof.
test ! -e src/shared/cli-output && echo "ABSENT"
# expect: ABSENT
```

**Rollback.** Revert the pin commit and the deletion commit; restore
`src/shared/cli-output` from the merge base. The repo and tag `v0.2.0` stay published (harmless).

**Deletion step.** `git rm -r src/shared/cli-output`; remove its lock entries; update the two
architecture-test copies.

---

## S2 — `config-assembler-engine` → its own repo

**Scope.** Extract `src/shared/config-assembler-engine` (16 test files, 880 src lines). Consumers:
csg, weg, itr.

**Entry criteria.** S1 merged; repo created with the birth checklist; `master` green.

**Steps.**

1. Import tree as repo root; add harness; `[tool.uv.sources]` empty.
2. Tag `v0.1.0` (version continuity).
3. Repoint csg/weg/itr `pyproject.toml` to `git = …/config-assembler-engine, tag = "v0.1.0"`;
   regenerate the three locks.
4. Delete `src/shared/config-assembler-engine/`.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$CLI_REPO_BASE/config-assembler-engine" /tmp/opencode/cae && cd /tmp/opencode/cae
make sync && make gates && make hermetic && uv lock --check
# expect: exit 0
cd "$WT"

rg -n 'config-assembler-engine = \{ path|path = "\.\./shared/config-assembler-engine"' src --glob 'pyproject.toml'
# expect: exit 1

for p in src/cli-tools/icon-templates-renderer src/cli-tools/wallpaper-effects-generator \
         src/cli-tools/color-scheme-generator; do
  uv run --directory "$p" pytest -q -k "config or resolv or strateg" || exit 1
done
# expect: exit 0 for all three (was 82/1 fail and 67/1 fail on this host before S0)

make gates-ci && make deploy-coverage
# expect: exit 0

test ! -e src/shared/config-assembler-engine && echo "ABSENT"
```

**Rollback.** Revert the pin + deletion commits.

**Deletion step.** `git rm -r src/shared/config-assembler-engine`; drop lock entries.

---

## S3 — `oci-runtime` → its own repo (build-context cutover)

**Scope.** Extract `src/shared/oci-runtime` (60 test files, 4 806 src lines), replace the monorepo
locator with the repo-root locator (AD-6), **and** cut both container CLIs over to the new build
model (AD-5/AD-7). The cutover must happen here: `oci-runtime` is the last shared lib, so deleting
`src/shared/` breaks every Dockerfile that still `COPY`s it.

**Entry criteria.** S2 merged; repo created with the birth checklist; `master` green; a container
engine available (`podman` or `docker`).

**Steps.**

1. Import `oci-runtime` as repo root (package version `0.4.0`); add harness.
2. Add `resolve_build_context` with the new marker (`pyproject.toml` + `src/<import_name>`); keep
   `resolve_source_root` as a deprecated alias accepting either marker set (AD-6, AD-16).
3. Migrate the locator tests: keep the legacy-marker fixtures (deprecated path) and add
   single-repo-root fixtures (`S4` §7.4 lists the old fixtures:
   `tests/unit/domain/test_source_locator.py:19,21,31,39,116,142,186`).
4. Bump the version to `0.5.0` (forward-only continuity) and tag `v0.5.0`; csg and weg pin
   `v0.5.0` by git tag.
5. Rewrite both in-tree Dockerfiles to the single-package context: `COPY pyproject.toml uv.lock`
   and `COPY src ./src`, then install from the lock with the pinned `uv` (plus `git` and CA
   certificates). Remove every `COPY src/shared/...` and `COPY src/cli-tools/...` line.
6. Change the build verb in csg and weg: `--context` (alias `--source-root`) points at the package
   root; the internal call becomes `resolve_build_context`; Dockerfiles resolve relative to the
   context. Provisioning’s build task passes `<dotfiles>/src/cli-tools/<pkg>` until that package’s
   own slice moves it to the pinned checkout.
7. Delete `src/shared/oci-runtime/` and the now-empty `src/shared/`.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$CLI_REPO_BASE/oci-runtime" /tmp/opencode/oci && cd /tmp/opencode/oci
make sync && make gates && uv lock --check
# expect: exit 0 (engine-dependent tests stay marked/skipped, never silently absent)
cd "$WT"

# New locator accepts a single-repo root and still accepts a legacy monorepo root.
uv run --directory src/cli-tools/color-scheme-generator python -c "
from pathlib import Path
from oci_runtime import resolve_build_context
import tempfile
root = Path(tempfile.mkdtemp())
(root/'pyproject.toml').write_text('[project]\nname=\"x\"\n')
(root/'src'/'x').mkdir(parents=True)
print(resolve_build_context(package='x', override=root))
"
# expect: BuildContextRoot(root=<tmp>, source='override'); exit 0

uv run --directory src/cli-tools/color-scheme-generator python -c \
  "from oci_runtime import resolve_source_root; print(resolve_source_root.__name__)"
# expect: resolve_source_root (deprecated alias still importable)

# No Dockerfile names a sibling repo any more.
rg -n "src/shared|src/cli-tools" \
  src/cli-tools/*/src/*/adapters/docker/
# expect: exit 1

# Both images build from a single package dir, with no monorepo in the context.
for p in color-scheme-generator wallpaper-effects-generator; do
  case $p in
    color-scheme-generator)            df=src/color_scheme_generator/adapters/docker/Dockerfile.base ;;
    wallpaper-effects-generator)       df=src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick ;;
  esac
  ( cd "src/cli-tools/$p" && podman build -t "${p}-local:test" -f "$df" . ) || exit 1
done
podman run --rm color-scheme-generator-local:test csg --version
podman run --rm wallpaper-effects-generator-local:test weg --version
# expect: both builds exit 0; both print "0.1.0 contract 0.2.0"

# Real generation still works in container mode through the runtime and through the CLI.
cd src/cli-tools/color-scheme-generator
uv run csg install --container-engine podman \
  --context "$WT/src/cli-tools/color-scheme-generator"
# expect: exit 0; images exist (base + backends)
cd "$WT"
uv run --directory src/runtime pytest tests/integration/test_csg_determinism.py -q -rs
# expect: no failures (container_mode true, engine podman — record the JSON)

make gates-ci && make deploy-coverage
test ! -e src/shared/oci-runtime && test ! -e src/shared && echo "ABSENT"
```

**Rollback.** Revert the pin commit, the Dockerfile/build-verb commit and the deletion commit
together: deleting the tree while the old Dockerfiles are restored is not a valid half-state.
Because `v0.5.0` is the repo’s first tag, rollback means restoring `src/shared/oci-runtime` from the
merge base and re-pointing the two consumers at the path source for this slice only — the
deprecated alias keeps that state buildable.

**Deletion step.** `git rm -r src/shared/oci-runtime`; remove `src/shared/`; drop lock entries;
remove the `oci-runtime` entry from the architecture-test forbidden sets if it is now a valid
third-party root (it is a real dependency of csg/weg, so keep it forbidden to others).

---

## S4 — `icon-templates-renderer` (`itr`) → its own repo

**Scope.** Extract the first CLI. 32 test files, 3 375 src lines, no container mode, no
`oci-runtime` dependency.

**Entry criteria.** S3 merged; repo created with the birth checklist; `master` green.

**Steps.**

1. Import tree as repo root (`pyproject.toml`, `src/icon_templates_renderer/`, `tests/`,
   `Makefile`, `uv.lock`); add harness; add the hermetic fixture if not imported.
2. Repoint `cli-output` `v0.2.0` and `config-assembler-engine` `v0.1.0` to git tags.
3. Migrate itr’s tests to the invocation contract kit (`cli_output.invocation.testkit`) in place of
   the local literal assertions (`S1` §6.1 itr block).
4. Tag `v0.1.0`.
5. Provisioning: change the itr manifest entry to `{name: itr, repo: <url>, tag: v0.1.0}` (the
   schema change lands with S4 because it is the first CLI; the other two entries keep their
   `source:` until their own slices, and the role handles both shapes during the window).
6. Delete `src/cli-tools/icon-templates-renderer/`.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$CLI_REPO_BASE/icon-templates-renderer" /tmp/opencode/itr && cd /tmp/opencode/itr
make sync && make gates && make hermetic && uv lock --check && uv build
# expect: exit 0; dist has icon_templates_renderer-0.1.0-*.whl
cd "$WT"

# Isolated install from the tag (does not touch the developer's tools).
UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin \
  uv tool install --force "git+$CLI_REPO_BASE/icon-templates-renderer@v0.1.0"
/tmp/opencode/uvbin/itr --version
# expect: "0.1.0 contract 0.2.0"; the contract token must equal the cli-output tag dotfiles pins

# Real render against the rendered settings (S1 §6.2 harness shape).
uv run --directory src/provisioning pytest -q \
  tests/integration/test_settings_parity.py::TestSettingsFileParity
# expect: exit 0; itr parses its rendered settings (4 passed baseline)

# Provisioning-side addressing + tests.
rg -n "src/cli-tools/icon-templates-renderer" src dotfiles scripts Makefile .github docs \
  --glob '!**/uv.lock'
# expect: exit 1 (only historical dirs _bmad-output/ and openspec/changes/archive/ may still name it)
uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py tests/unit/test_verify_role.py -q
# expect: exit 0 after the manifest/role/verify mirrors are updated together

make gates-ci && make deploy-coverage
test ! -e src/cli-tools/icon-templates-renderer && echo "ABSENT"
```

**Rollback.** Revert the manifest/pin commit and the deletion commit; restore the tree.

**Deletion step.** `git rm -r src/cli-tools/icon-templates-renderer`; remove the runtime
`derive.py` repo-relative candidate for `icon_templates`/`icon_mappings` dev fallbacks; update
`docs/99-dotfiles-hexagonal-architecture.md` and `docs/01-…` tables; drop stale `.gitignore` lines.

---

## S5 — `wallpaper-effects-generator` (`weg`) → its own repo

**Scope.** Extract the first container-mode CLI. 30 test files, 4 398 src lines. This slice proves
AD-5 + AD-7 end-to-end.

**Entry criteria.** S4 merged; repo created with the birth checklist; `master` green; a container
engine available (`podman` or `docker`).

**Steps.**

1. Import tree as repo root; add harness; repoint `cli-output`, `config-assembler-engine`,
   `oci-runtime` to tags.
2. Confirm the S3 cutover holds at the new repo root: Dockerfile copies only `pyproject.toml`,
   `uv.lock`, `src/`; the build verb resolves Dockerfiles relative to `--context`.
3. Tag `v0.1.0`.
4. Provisioning: `{name: weg, repo, tag}`; clone at tag into `<install>/cli-tools/weg/<tag>`;
   install from the checkout; build with `--context <checkout>`; render `image_tag = v0.1.0`
   (not `latest`).
5. Delete `src/cli-tools/wallpaper-effects-generator/`.

**Acceptance gates.**

```bash
cd "$WT"

git clone "$CLI_REPO_BASE/wallpaper-effects-generator" /tmp/opencode/weg && cd /tmp/opencode/weg
make sync && make gates && make hermetic && uv lock --check
# expect: exit 0

# The invariant: no sibling-repo path in the Dockerfile.
rg -n "src/shared|src/cli-tools|\.\./" src/wallpaper_effects_generator/adapters/docker/
# expect: exit 1

# Build from the repo root only (no monorepo present).
podman build -t weg-local:test -f src/wallpaper_effects_generator/adapters/docker/Dockerfile.imagemagick .
podman run --rm weg-local:test weg --version
# expect: build exit 0; prints "0.1.0 contract 0.2.0"
cd "$WT"

# Isolated install + real batch run (S1 argv: batch all -- <wallpaper>).
UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin \
  uv tool install --force "git+$CLI_REPO_BASE/wallpaper-effects-generator@v0.1.0"
rm -rf /tmp/opencode/weg-out && mkdir -p /tmp/opencode/weg-out
WALLPAPER__OUTPUT__DIRECTORY=/tmp/opencode/weg-out \
  /tmp/opencode/uvbin/weg batch all -- "$(find . -name '*.png' -path '*test*' | head -1)"
# expect: exit 0; at least one image under /tmp/opencode/weg-out

# Runtime adapter still passes against the installed tool.
uv run --directory src/runtime pytest tests/integration/test_weg_adapter_integration.py -v -rs
# expect: 1 passed

# Provisioned image is tag-qualified: no `latest`, the pin is the tag.
podman images --format '{{.Repository}}:{{.Tag}}' | grep -E 'weg.*:v0\.1\.0$'
# expect: at least one line per backend; no `:latest` line for a weg image
make gates-ci && make deploy-coverage
test ! -e src/cli-tools/wallpaper-effects-generator && echo "ABSENT"
```

**Rollback.** Revert the pin commit + deletion commit; restore the Dockerfile from the merge base if
the new context model fails.

**Deletion step.** `git rm -r src/cli-tools/wallpaper-effects-generator`; remove the runtime
`weg_effects` repo candidate; update docs tables; remove stale `.gitignore` lines
(`feedback.md`, `test.sh`).

---

## S6 — `color-scheme-generator` (`csg`) → its own repo

**Scope.** Extract the last CLI, including its template catalog (consumed by provisioning’s
`assets` role) and the nested OpenSpec root. 49 test files, 4 684 src lines. After this slice,
`src/cli-tools/` is empty and both retired trees are gone.

**Entry criteria.** S5 merged; repo created with the birth checklist; `master` green; container
engine available.

**Steps.**

1. Import tree as repo root; add harness; repoint `cli-output`, `config-assembler-engine`,
   `oci-runtime`.
2. Confirm the S3 cutover holds at the new repo root (Dockerfiles copy only in-repo paths; the
   per-backend Dockerfiles keep their `ARG BASE_IMAGE`).
3. Move `src/cli-tools/openspec/changes/fix-container-engine-plumbing/` into the csg repo as
   `openspec/changes/archive/fix-container-engine-plumbing/`; drop
   `specs/no-spec-changes.md` (placeholder) and the nested `.openspec.yaml` scaffolding.
4. Tag `v0.1.0`.
5. Provisioning: `{name: csg, repo, tag}`; clone/install/build from the checkout; render
   `image_tag = v0.1.0`. Re-address the templates asset: `dotfiles/provisioning/assets.yaml` and
   `roles/assets/vars/main.yml:72` read
   `<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates/` instead of
   `src/cli-tools/...`, and depend on the `fetch` task list (AD-10).
6. Delete `src/cli-tools/color-scheme-generator/`, then `src/cli-tools/` (empty), and
   `src/cli-tools/openspec/` (already moved).

**Acceptance gates.**

```bash
cd "$WT"

git clone "$CLI_REPO_BASE/color-scheme-generator" /tmp/opencode/csg && cd /tmp/opencode/csg
make sync && make gates && make hermetic && uv lock --check
# expect: exit 0

rg -n "src/shared|src/cli-tools" src/color_scheme_generator/adapters/docker/
# expect: exit 1

podman build -t csg-base-local:test -f src/color_scheme_generator/adapters/docker/Dockerfile.base .
podman run --rm csg-base-local:test csg --version
# expect: build exit 0; prints "0.1.0 contract 0.2.0"
cd "$WT"

# Real generation through the runtime's exact argv (S1 §1.3): eight --format flags, env output dir.
UV_TOOL_DIR=/tmp/opencode/uvtools UV_TOOL_BIN_DIR=/tmp/opencode/uvbin \
  uv tool install --force "git+$CLI_REPO_BASE/color-scheme-generator@v0.1.0"
rm -rf /tmp/opencode/csg-out && mkdir -p /tmp/opencode/csg-out
COLORSCHEME__OUTPUT__DIRECTORY=/tmp/opencode/csg-out COLORSCHEME__OUTPUT__OVERWRITE=true \
  /tmp/opencode/uvbin/csg generate "$(find . -name '*.png' -path '*test*' | head -1)" \
  --format yaml --format conf --format gtk.css --format adw.css \
  --format sequences --format rasi --format kitty --format btop.theme
ls /tmp/opencode/csg-out
# expect: exit 0; colors.yaml colors.conf colors.gtk.css colors.adw.css colors.sequences
#         colors.rasi colors.kitty colors.btop.theme

# Templates asset resolves from the pinned checkout.
uv run --directory src/provisioning pytest tests/unit/test_assets_role.py -q
# expect: exit 0 (parity test updated to the checkout source)

# Runtime adapter + determinism.
uv run --directory src/runtime pytest tests/integration/test_csg_adapter_integration.py \
  tests/integration/test_csg_determinism.py -v -rs
# expect: no failures (xfail may XPASS; record the observed line)

# Images are tag-qualified, never `latest`.
podman images --format '{{.Repository}}:{{.Tag}}' | grep -E '(csg|color-scheme).*:v0\.1\.0$'
# expect: base + each built backend at :v0.1.0; no `:latest` for a csg image

make gates-ci && make deploy-coverage
# expect: exit 0, including the new absence guards for src/cli-tools/ and src/shared/
test ! -e src/cli-tools && test ! -e src/shared && echo "RETIRED TREES ABSENT"
```

**Rollback.** Revert the pin commit and the deletion commit; restore
`src/cli-tools/color-scheme-generator`, the nested openspec, and the old asset source. If the
deletion is already merged and the new wiring fails later, the rollback is a pin bump to the last
good tag plus a revert of the deletion commit — never a retag.

**Deletion step.** `git rm -r src/cli-tools/color-scheme-generator src/cli-tools/openspec`;
remove `src/cli-tools/` when empty; remove the runtime `csg_templates` repo candidate; update
`docs/01-…`, `docs/99-…`, `docs/02-config-in-spine-pattern.md`; update the two architecture-test
forbidden sets to drop the now-external import roots; remove the `.gitignore` entries.

---

## Post-migration verification (after S6 merges)

```bash
cd "$DTF"
make gates-ci && make deploy-coverage
# expect: exit 0; deploy-coverage reports the six pinned tools and zero local sources

rg -n "src/cli-tools|src/shared" src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs
# expect: exit 1 (historical dirs _bmad-output/ and openspec/changes/archive/ are out of scope by rule)

git ls-files 'src/cli-tools/*' 'src/shared/*'
# expect: empty

for t in itr weg csg; do command -v "$t" && "$t" --version; done
# expect: three binaries; each line "<pkg-version> contract 0.2.0" with the tag version

uv tool list | grep -E "color-scheme-generator|wallpaper-effects-generator|icon-templates-renderer"
# expect: three entries with versions matching the pins
```

If any command above contradicts the expected observable, the migration is not done — the gate is
execution, not this document.
