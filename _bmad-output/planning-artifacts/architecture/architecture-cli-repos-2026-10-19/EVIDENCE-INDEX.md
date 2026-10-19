# Evidence Index — one line per spine decision

Pointers are to `docs/investigation/S1…S4` sections, to files read (with line ranges), or to the
`Verify` blocks in those reports. A decision whose evidence is a *design consequence* rather than
an observed fact says so.

| Decision | Evidence pointer | Reproduce (one command) |
| --- | --- | --- |
| AD-1 one-way dependency | `S1` §1.1 (runtime imports none of the six; coupling is `subprocess.run`), `S4` §2.3 dependency matrix, `S4` §1.4 | `rg -n '^(from\|import) (color_scheme_generator\|wallpaper_effects_generator\|icon_templates_renderer\|config_assembler_engine\|oci_runtime)' src/runtime --glob '*.py'` → exit 1 |
| AD-2 one package per repo / repo root = package root | `S4` §2.1 (no root `pyproject.toml`, no workspace; 8 independent projects + 8 locks), `S2` §2.3 (`_REPO_MARKER_DIRS` assumes `src/cli-tools` + `src/shared`), `S4` §2.5 (Dockerfiles assume repo root) | `find . -name pyproject.toml -not -path './.git/*' \| sort` → 8; `ls pyproject.toml` → exit 2 |
| AD-3 consume by immutable tag only | `S2` §2.3 (installed tool envs carry absolute `.pth` + `direct_url.json` into the checkout), `S4` §2.4 (locks record `editable = "../../shared/…"`), `S4` §4 (nothing published), `S2` §5.1–5.2 (tag-clone precedent) | `find ~/.local/share/uv/tools/color-scheme-generator -name '*.pth' -exec cat {} \;` → three absolute `src/shared/*` paths |
| AD-4 `contracts` owns the invocation contract; `cli-output` is presentation-only | `S1` §1.3 (exact argv), §1.5 (exact env), §2.2 (artifact names + hashes), §6.1 (the same literals duplicated in three adapter test files); `contracts/README.md:5` (charter: “Single source of truth for the runtime ↔ AGS event seam”); `contracts` has **zero tags** (`git tag -l` → empty) and **no `pyproject.toml`** (`ls pyproject.toml` → exit 2), so the package + first tag are new work; `contracts/AGENTS.md` §2–§3 (never on `main`; ticket/OpenSpec routing) | `sed -n '778,818p' docs/investigation/S1-runtime-cli-addressing.md`; `cd /home/inumaki/Development/contracts && git tag -l \| wc -l && ls pyproject.toml; sed -n '5p' README.md` → `0`, exit 2, charter line |
| AD-5 image context = own repo root | `S2` §2.3 (Dockerfiles COPY repo-relative paths; external layout rejected), `S4` §2.5 (the only non-doc files naming `src/shared` are the two Dockerfiles + `source_locator.py`), `Dockerfile.base:3-7`, `Dockerfile.imagemagick:9-19` | `sed -n '1,10p' src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/docker/Dockerfile.base` |
| AD-6 `resolve_build_context` replaces the monorepo marker | `source_locator.py:37-39,50-61,109-144`; `S2` §2.3 executed probe (`marker on external layout: None`, `SourceRootNotFoundError`); `S3` closing paragraph (build context is the only repo-relative runtime dependency) | `uv run --directory src/cli-tools/color-scheme-generator python -c "from pathlib import Path; from oci_runtime.source_locator import _repo_root_from_candidate as f; print(f(Path('/tmp/opencode/s2-ext')))"` → `None` |
| AD-7 build ownership split; image tag = pin | `S2` §2.2 (`tasks/main.yml:328-340` builds via `<cli> install --source-root`), `S2` §2.1 (`cli_tools_image_builds` = csg, weg; itr absent), `S1` §3.2 (itr has no container mode), `S1` §4.5 + `csg-settings.toml.j2:26` (`image_tag = "latest"` — the stale-image risk the tag rule closes) | `sed -n '328,340p' src/provisioning/ansible/roles/cli_tools/tasks/main.yml`; `grep -n image_tag src/provisioning/ansible/roles/settings/templates/*.j2` |
| AD-8 tests hermetic, fix in tests | `S3` §5.1 (both failures resolve the provisioned spine; both pass with empty `XDG_CONFIG_HOME`), `S3` §5.3 (which tests are environment-sensitive), `S3` §1.4/§5.4 (XDG-over-default is intended) | `env HOME=/tmp/opencode/fakehome XDG_CONFIG_HOME=/tmp/opencode/emptyxdg-csg uv run --directory src/cli-tools/color-scheme-generator pytest -q tests/unit/adapters/test_template_dir_resolver.py` → 4 passed |
| AD-9 release ritual / tag ladder | `S4` §4 (no publish config, no classifiers, no README/CHANGELOG, no `[tool.uv]` index), `S1` §4.5 (`image_tag = "latest"`, unversioned `uv tool install`), `S2` §5.2 (tag pin + `pinned` file), `LESSONS` §5 (tag then bump pin in one change) | `rg -n 'pypi\|index-url\|registry\|extra-index\|publish' --glob 'pyproject.toml' .` → exit 1; `grep -n 'image_tag' src/provisioning/ansible/roles/settings/templates/*.j2` |
| AD-10 provisioning addresses `{name, repo, tag}` + checkout assets | `S2` §1.1 (manifest schema: `name`, `source`, optional `version`; no `repo`/`ref`), §1.2 (role mirrors the manifest), §3 (install from local path only), §7.1–7.2 (hard breaks incl. the csg template asset that the assets role synchronizes) | `sed -n '1,20p' dotfiles/provisioning/cli-tools.yaml`; `sed -n '38,44p' src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py`; `sed -n '99,103p' src/provisioning/ansible/roles/assets/tasks/main.yml` |
| AD-11 pins asserted by execution + one shape gate | `S2` §3 (verify checks only `command -v`; no symlink/pin assertion for csg/weg/itr), §5.4 (`ags-apps` capture-tool gets `islnk` + `lnk_target is search(version)`), §4 (deploy-coverage has no CLI install-shape assertion), §7.1 item 16 (parity test exists but is not gated) | `sed -n '381,401p' src/provisioning/ansible/roles/verify/tasks/main.yml`; `sed -n '1175,1205p' src/provisioning/ansible/roles/verify/tasks/main.yml` |
| AD-12 mu-strict birth | `mu/AGENTS.md` §1–§4, `mu/tickets/LIFECYCLE.md` (gate one-liners per kind), `mu/tickets/INDEX.md` (same-commit rule), `mu/tickets/_template/{epic,requirement,task,bug,ops-task,spike}.md`, `mu/scripts/worktree-guard.sh`, `mu/skills-lock.json` (7 skills), `mu/Makefile` (fresh-clone verbs); `GUIDE-ags-app-repos-refinement.md` §7 (harness/CI cost is why per-app splits were deferred) | `ls /home/inumaki/Development/mu/tickets/_template; python3 -c 'import json;print(len(json.load(open("/home/inumaki/Development/mu/skills-lock.json"))["skills"]))'` → 6 templates, 7 skills |
| AD-13 destructive-last per target | `S4` §5.2 (one deletion commit per app carrying source + gates), §5.3 (terminal catch-all commit + absence guard), §5.4 (merge adds nothing), §7 (blast radius checklist), `LESSONS` §1 (gate migration, never the steady-state ensure) | `git log --oneline -20 -- src/gui-tools`; `git show --stat 50641af0 \| tail -12` |
| AD-14 tests move and are gated there | `S4` §1.1 (`Makefile`, `scripts/`, CI carry zero references; `make gates-ci` runs five gates), `S4` §6 (sizes; the 253 figure counts all `.py` under `tests/`), `Makefile:14,48-49` | `git ls-files 'src/cli-tools/*' 'src/shared/*' \| grep -E '/tests/.*test_[^/]*\.py$' \| wc -l` → 195; per package 49/30/32/8/16/60 |
| AD-15 OpenSpec ownership follows code | `S4` §1.6 (590 hits, 147 files; which live specs name the packages), §7.9 item 4 (nested root, explicitly not an install target), nested proposal Impact lists only `color_scheme_generator` paths | `find src/cli-tools/openspec -type f \| sort`; `sed -n '1,40p' src/cli-tools/openspec/changes/fix-container-engine-plumbing/proposal.md` |
| AD-16 backward compat is behavioral | `S1` §1.5/§3.3 (runtime supplies only PATH/HOME/XDG + tool env keys), §2.4 (error mapping and loud failures), `S2` §2.3 (`SourceRootNotFoundError` executed), `S3` closing paragraph (no repo-relative settings/templates dependency) | `grep -rn "cwd=\|stdin=" src/runtime/src/runtime/adapters/{csg,weg,itr}_adapter.py` → exit 1; see `S2` §2.3 probe output |

## Design consequences (no observations yet — stated as consequences, not facts)

| Item | Why it is a consequence |
| --- | --- |
| AD-4 contract package does not exist yet | The `contracts` repo has zero tags and no `pyproject.toml`; S0a creates the `cli-invocation-contract` package and tags `v0.1.0`. The *drift it prevents* is observed (`S1` §6.1 duplicates), the package + kit are the remedy — no consumer reads the record until S0b. |
| AD-5/AD-6 build model is untested end-to-end | `S2` §2.3 proves the *failure* of the current model on an external layout; no image has been built from a single-repo context. Slice S3 is the first executed proof (both images, both context roots). |
| AD-5 image builds need git + network for pinned deps | Consequence of choosing git tags as the only pin channel (`S4` §4: no registry/index). The build stage installs `git` and CA certificates; a moved/unreachable tag fails the build rather than resolving something newer. |
| AD-7 image tag equals the pin | `S1` §4.5 observes today’s `image_tag = "latest"`; the tag rule is the remedy. No tag-qualified image has been built yet — proven in S3/S5/S6. |
| AD-9 release CI | No workflow publishes today (`S4` §4); the ritual is new machinery, proven in S1’s release gate. |
| AD-11 `--version` assertions | No CLI exposes a version handshake today (`S1` §4.1: `grep -- "--version"` → exit 1); S0b adds `<version> contract <contracts-version>`, and `contracts v0.1.0` (S0a) supplies the token. |

## Measured counts used in this spine

```bash
# tracked test modules (the number the spine uses)
git ls-files 'src/cli-tools/*' 'src/shared/*' | grep -E '/tests/.*test_[^/]*\.py$' | wc -l   # 195

# all tracked .py under tests/ (the number S4 §6 calls "test files")
git ls-files 'src/cli-tools/*' 'src/shared/*' | grep -E '/tests/.*\.py$' | wc -l             # 253

# raw find (the orchestrator's 199): contaminated by 4 untracked package .venv files
find src/cli-tools src/shared -name 'test_*.py' | wc -l                                      # 199
find src/cli-tools src/shared -name 'test_*.py' -path '*/.venv/*' | wc -l                   # 4
```

## Reports read in full

- `docs/investigation/S1-runtime-cli-addressing.md` (1–1116)
- `docs/investigation/S2-provisioning-addressing.md` (1–1161)
- `docs/investigation/S3-config-flow.md` (1–1072)
- `docs/investigation/S4-reference-inventory.md` (1–1068)
- `AGENTS.md` (dotfiles-v3), `docs/101-ags-platform-architecture.md`,
  `docs/GUIDE-ags-app-repos-refinement.md`, `docs/LESSONS-ags-apps-migration.md`
- `/home/inumaki/Development/mu/AGENTS.md`, `/home/inumaki/Development/mu/tickets/LIFECYCLE.md`,
  `/home/inumaki/Development/mu/tickets/INDEX.md`, `/home/inumaki/Development/mu/Makefile`,
  `/home/inumaki/Development/mu/skills-lock.json`, `/home/inumaki/Development/mu/scripts/worktree-guard.sh`
- `/home/inumaki/Development/contracts/README.md`, `contracts/AGENTS.md`, `contracts/Makefile`
  (charter line, worktree/ticket routing, existing gates) — facts re-verified 2026-10-19:
  clean `main`, `git tag -l` empty, no `pyproject.toml`, HEAD `2cfd403`
- Code read directly: `src/shared/oci-runtime/src/oci_runtime/source_locator.py` (1–144),
  `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/install_cmd.py` (1–124),
  both Dockerfiles, `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/container_processor.py` (1–80, 120–230),
  `src/shared/*/pyproject.toml`, `scripts/deploy-coverage.py` (80–180, 780–850),
  `scripts/contract-pin-check.py` (1–80), `.github/workflows/gates.yml` (1–60), `Makefile` (1–60).
