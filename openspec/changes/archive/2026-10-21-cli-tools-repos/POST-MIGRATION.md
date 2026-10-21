# Post-migration closure record — `cli-tools-repos`

Written 2026-10-21, after the umbrella change was archived and S6 merged to
`master`.

**This file is additive.** `tasks.md` in this directory is the point-in-time
record of the change as it stood when it was archived, and its ten open boxes
(0.1–0.6, 8.8, 9.1–9.3) are **deliberately left unticked**: an archive is a
snapshot, not a live checklist. This file is the live answer to "did those ten
actually land?", with the command and the observed result for each.

Re-run target: `master` at `1b2f644a` (`git rev-parse master` →
`1b2f644ab38778a573cf1951d8870c411eb73a68`), a clean checkout
(`git status --short` → empty; `git ls-files src/shared src/cli-tools` → 0
lines; `src/shared` + `src/cli-tools` absent).

## 1. Completion table

### The six extracted repos (0.1–0.6, and 9.3's tag chain)

Checked against a shallow clone of each repo at its released tag
(`git clone --depth 1 --branch <tag> …` → `HEAD` equals the peeled commit
below). "runs" is `gh run list -R RandomGenericUsername/<r> --limit 3 --json
status,conclusion,headBranch`; all six returned three `completed/success`
entries, including one on the tag's own branch.

| Repo | `gh api … --jq '{private,visibility}'` | Consumed tag | Annotated tag object | Peeled commit (`^{}`) | Latest runs | Release asset |
| --- | --- | --- | --- | --- | --- | --- |
| `cli-output` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `91489b73b54e6cd09dc54e360431a3ebb915fa05` | `ddae372786fd6053730133e82cf542a17e9a5ae5` | `success/main`, `success/v0.1.0`, `success/main` | `cli_output-0.1.0.tar.gz` |
| `config-assembler-engine` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `5c5cc84e4103f1135a717320cf7cb809487d6e5e` | `cad8a91c6bcbc4087209911bc36d82f8b6349f66` | `success/main`, `success/v0.1.0`, `success/main` | `config_assembler_engine-0.1.0.tar.gz` |
| `oci-runtime` | `{"private":false,"visibility":"public"}` | `v0.5.0` | `38ce267ce966a831ba0617bc5a97660564f7880a` | `b631dfa511f5710d6e171d2ac3f0cdf58bc738af` | `success/v0.5.0`, `success/main` | `oci_runtime-0.5.0.tar.gz` |
| `icon-templates-renderer` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `09271f64375ccfb2eeb36dc3c6b81a4b55b2bdd6` | `92895a068b7117832d0cbf2a5bfb158ca3fda68c` | `success/main`, `success/v0.1.0`, `success/main` | `icon_templates_renderer-0.1.0.tar.gz` |
| `wallpaper-effects-generator` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `093d405129ef34a7d1bd78c64b692bca17129cb9` | `9672d89c117709afa6eb5b574bd8fdb71469f801` | `success/main`, `success/v0.1.0`, `success/main` | `wallpaper_effects_generator-0.1.0.tar.gz` |
| `color-scheme-generator` | `{"private":false,"visibility":"public"}` | `v0.1.0` | `47afbbdf4b3d1d7a2ac6dbc9cfea3d6d4487b335` | `14f2faf590f503cc60baf0da81955076e9e42214` | `success/main`, `success/v0.1.0`, `success/main` | `color_scheme_generator-0.1.0.tar.gz` |
| `contracts` (the seventh, contract home) | `{"private":false,"visibility":"public"}` | `v0.1.0` | `6ea43dcb8864ae749d4912878d70dc91e7376969` | `48cf3cfed4b192b241505789409c4f282921c896` | (unchanged since S0a; `contract-drift` green) | — |

Tag-chain one-pass (9.3), anonymous:

```text
contracts: v0.1.0
cli-output: v0.1.0
config-assembler-engine: v0.1.0
oci-runtime: v0.5.0
icon-templates-renderer: v0.1.0
wallpaper-effects-generator: v0.1.0
color-scheme-generator: v0.1.0
```

One tag per repo, no tag listed twice, every consumed tag present
(`git ls-remote --tags --refs https://github.com/RandomGenericUsername/<r>`,
exit 0 each).

### Per-task state

| Task (as archived) | Was | Now | Evidence |
| --- | --- | --- | --- |
| 0.1 harness byte-identical to `mu` | open | **satisfied** | In all six pinned checkouts: `diff -r /home/inumaki/Development/mu/<path> <path>` over the eight copied paths (`_bmad`, `.agents/skills`, `.opencode`, `scripts/worktree-guard.sh`, `skills-lock.json`, `tickets/_template`, `tickets/_fixtures`, `tickets/LIFECYCLE.md`) → 0 differing paths per repo (`harness_diff_failures=0`). `mu` ships no hash-recompute script, so byte-equality is the proof every `computedHash` matches. |
| 0.2 verbs resolve paths from any caller dir | open | **satisfied** | From `/tmp/opencode` (a foreign cwd): `make -C <repo> gates` → exit 0 for all six, suites `63` / `163` / `288` / `349` / `639` / `1107 passed, 2 skipped`. `rg -n '$(PWD)\|$(shell pwd)' <repo>/Makefile` → exit 1 for all six (`$(CURDIR)` only). |
| 0.3 CI parity runs before the first push | open | **satisfied** | `make -C <repo> ci-gates-parity` → exit 0, `PASS gates=[...] jobs=[...] exempt=[...]` for all six (weg/csg declare `image` + `release` exempt). `.github/workflows/gates.yml` present in all six; latest runs above are green. |
| 0.4 hermetic fixture and canary exist | open | **satisfied** | `rg -l 'XDG_CONFIG_HOME' <repo>/tests/conftest.py` → match (exit 0) in all six; `uv run pytest -q -k canary` at the pinned checkout → `1 passed` in each (`62`/`162`/`1108`/`287`/`348`/`638` deselected). |
| 0.5 pin channel is anonymous | open | **satisfied** | `gh api repos/…/<r> --jq '{private,visibility}'` → `private:false, public` (table above), and the credential-free probe `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote …/<r> 'refs/tags/<tag>'` → exit 0, exactly one line, for all six **and** `contracts`. |
| 0.6 visibility decision + consequence recorded | open | **satisfied in the record, stale in the birth tickets** — *closed by addendum A2* | This repo's S-slice logs + this file state the channel (anonymous `https`, no credential helper) and the consequence (a private repo would break `ansible.builtin.git`'s anonymous fetch). The per-repo birth tickets are **not** updated — see gap (g). |
| 8.8 Merge S6 to `master` | open | **done** | `master` = `1b2f644a` (`chore(openspec): archive the cli-tools-repos umbrella change`); `git rev-list --parents -n1 1b2f644a` → one parent `980365fc`, i.e. a single-commit-tip **fast-forward** of the S6 branch (`ticket/clitools-s6-consume-csg-final` = `1b2f644a`) over `6e0633ba`; the range `6e0633ba..1b2f644a` is 4 commits (`1d8d4fc8`, `8e8de381`, `980365fc`, `1b2f644a`). Push: `git ls-remote origin refs/heads/master` → `1b2f644ab38778a573cf1951d8870c411eb73a68  refs/heads/master`, exit 0. Post-merge gates on the merged tree: `make gates-ci` exit 0, `make hermetic` exit 0, `make deploy-coverage` exit 0. |
| 9.1 terminal gates + reference scan | open | **satisfied, with one recorded deviation** | `make gates-ci` → exit 0 (five gates: `contracts-check`, `ansible-embedded-template-lint`, `deploy-coverage`, `ci-gates-parity`, `per-app-drift-symbol-suites`). `make deploy-coverage` → exit 0 and the terminal line quoted below. `rg -n '^    source:' dotfiles/provisioning/cli-tools.yaml` → **exactly one** match, `34:    source: src/runtime`. `test ! -e src/cli-tools && test ! -e src/shared` → exit 0. `git ls-files 'src/cli-tools/*' 'src/shared/*'` → 0 lines. The literal `rg -n "src/cli-tools\|src/shared" src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs` is **exit 0, not 1** — 338 lines in 9 files, all of them either the guard, its negative tests/fixtures, or read-only investigation docs (gap (f)). |
| 9.2 installed-tool + pin checks | open | **satisfied for the pins, host tools still stale** — *host tools closed by addendum A1* | `uv tool list` → `color-scheme-generator v0.1.0`, `icon-templates-renderer v0.1.0`, `wallpaper-effects-generator v0.1.0` (matching the manifest pins). But `command -v itr/weg/csg` resolve to `~/.local/bin/*` and each exits 1 at import (`ModuleNotFoundError: No module named 'cli_output'` / `'config_assembler_engine'` / `'oci_runtime'`) — gap (b). Contract-pin scan `rg -n 'cli-invocation-contract = .*contracts", tag = "v[0-9]' src --glob 'pyproject.toml'` → **1** match, `src/runtime/pyproject.toml:27` (the three CLI consumers left this repo; their own `pyproject.toml`s carry the same tag). |
| 9.3 tag chain in one pass | open | **satisfied** | The seven-line output above, anonymous, exit 0. |

### Headline gate output (verbatim, on `1b2f644a`)

```text
$ make deploy-coverage   # exit 0
deploy-coverage: PASS -- six packages are consumed from their pinned repos (cli-output, config-assembler-engine, oci-runtime, itr, weg, csg); src/cli-tools/ and src/shared/ are retired, and the CLI manifest carries exactly ONE in-repo source (dotfiles-runtime -> src/runtime)
```

```text
$ make hermetic          # exit 0
hermetic: PASS -- no in-repo package sources; the six extracted
  packages (cli-output, config-assembler-engine, oci-runtime,
  itr, weg, csg) run their own 'make hermetic' in their pinned
  repos; this repo's src/runtime + src/provisioning are covered
  by 'make gates-ci'
```

`openspec validate --all` → **exit 1, `Totals: 104 passed, 27 failed (131
items)`**. The 27 failures are the pre-existing legacy set, unchanged:
`openspec validate --all` at pre-merge base `6e0633ba` → `99 passed, 27 failed
(126 items)`, and the 27 failing item names are **identical** (`diff` of the
sorted names → empty). Composition: 19 legacy **change**-level defects
(`add-bluetooth-bar-popup`, `add-mic-live-dot-backdrop-state`,
`ags-apps-bar-first`, `ags-remove-bar-bridge`,
`declare-capture-test-dependencies`, `enhance-ags-bar`,
`gtk-theming-consumer`, `redesign-ags-audio-panel`, and eleven `wifi-*`
changes — mostly `Change must have at least one delta`, some a requirement
without a scenario, some a SHALL only in the header) and 8 pre-existing
**spec** shape defects (`cli-runtime-engine-scope`,
`container-image-engine-tagging`, `csg-image-naming`, `oci-doc-cleanup-v3`,
`oci-exec-semantics`, `oci-pipe-reader-port`, `oci-test-contracts`,
`oci-version-error-contract` — missing `## Purpose`, requirement outside
`## Requirements`, requirement without a scenario). The passing count rose
99 → 104 because the archive added five capability specs to
`openspec/specs/`.

### The post-merge failure that was found and fixed (operational note)

8.8's **first** post-merge `make deploy-coverage` on `master` failed even
though the merge was green in the worktree. Cause: the main checkout still
held untracked/ignored residue under `src/shared/` and `src/cli-tools/`
(most likely `.venv/` / `__pycache__` content left by earlier slices' runs).
No file was tracked — `git ls-files src/shared src/cli-tools` → 0 — but the
**directories still existed**, and the terminal guards assert directory
absence, so they fired. `rm -rf src/shared src/cli-tools` cleared it and every gate then
passed.

Reproduced on the merged tree to pin the exact messages (create an
ignored-only leftover, run the guard, remove it, run again):

```text
$ mkdir -p src/cli-tools/__pycache__ && touch src/cli-tools/__pycache__/x.pyc
$ git status --ignored --short src/cli-tools
!! src/cli-tools/
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 1
FAIL: the retired package root src/cli-tools/ still exists — every CLI tool and shared library is consumed from its pinned repo (spine AD-10); delete the directory
$ rm -rf src/cli-tools

$ mkdir -p src/shared/.venv && touch src/shared/.venv/marker
$ git status --ignored --short src/shared
?? src/shared/                       # (0 tracked files; only ignored content)
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 1
FAIL: the retired shared-library root src/shared/ still exists — every shared library is consumed from its pinned repo; delete the directory (an empty leftover must not become a new home for a vendored copy)
$ rm -rf src/shared
$ uv run --directory src/provisioning python ../../scripts/deploy-coverage.py   # exit 0
deploy-coverage: PASS -- six packages are consumed from their pinned repos …
```

**For future migrations:** a worktree merge and a main-checkout merge are not
the same evidence. Worktrees are created from a commit and carry no
untracked/ignored leftovers; the long-lived main checkout can, and the
absence guards look at the filesystem, not at `git ls-files`. After any
tree-deletion merge, `rm -rf` the retired roots in the checkout you are about
to gate, then run `make deploy-coverage` there before believing the merge.

## 2. What the repository looks like now (facts for future readers)

- **Seven pinned repos, one contract package.** `contracts` (tag `v0.1.0`)
  owns the invocation contract; the six extracted packages own their code:
  `cli-output`, `config-assembler-engine`, `oci-runtime` (tag `v0.5.0`),
  `icon-templates-renderer`, `wallpaper-effects-generator`,
  `color-scheme-generator` (all `v0.1.0`). Every one is public and fetched
  anonymously by tag.
- **Two consumption shapes only:**
  - the three **shared libraries** (`cli-output`, `config-assembler-engine`,
    `oci-runtime`) plus `cli-invocation-contract` are consumed as git-tag pins
    in each consumer's `pyproject.toml` `[tool.uv.sources]`
    (`{ git = "…/repo", tag = "vX.Y.Z" }`), and the resolved commit is what
    `uv.lock` records;
  - the three **CLIs** (`csg`, `weg`, `itr`) are consumed as
    `{name, repo, tag}` entries in `dotfiles/provisioning/cli-tools.yaml`
    (+ the `roles/cli_tools/vars/main.yml` mirror). The role shallow-clones
    `<repo>@<tag>` into `<install>/cli-tools/<name>/<tag>/`, drops `.git`,
    writes the `pinned` record, and installs **from that checkout** (never
    from a `git+…@tag` URL) so PEP 610 records a tag-bearing path.
- **The only in-repo Python is `src/runtime/` and `src/provisioning/`.**
  There are no in-repo package sources for anything extracted: `cli-tools/`
  and `shared/` package roots are retired and gated absent, and
  `dotfiles/provisioning/cli-tools.yaml` carries exactly one local
  `source:` (`dotfiles-runtime -> src/runtime`, line 34). `HERMETIC_PACKAGES`
  is empty, which is why `make hermetic` prints an explicit PASS.
- **Image tags are pins, never `latest`.** `weg`'s image tag is an argv tag;
  `csg`'s four images take the pin through
  `COLORSCHEME__CONTAINER__IMAGE_TAG` (see gap (c)).

## 3. Known gaps / follow-ups

Each item is a real, observed limitation. As written, none was redressed in this
record; the 2026-10-21 addendum later closed (b) and (g) and half of (a), so each
item now opens with a **status line** naming the addendum section that changed
it. The bodies below are left as written.

**Status (addendum A1): PARTIALLY RESOLVED** — the real **host** run is done and
recorded in A1; the disposable-**VM** run is still not done, so the VM half of
this gap stays open.

**(a) No real VM provisioning run (no incus on this host).** `command -v incus`
→ nothing. The roles' behaviour is proven by **simulation + `--check`** on the
merged tree, not by provisioning a machine:

```text
$ cd src/provisioning/ansible
$ ANSIBLE_COLLECTIONS_PATH=$HOME/.ansible/collections ../.venv/bin/ansible-playbook \
    playbooks/cli-tools.yaml --check -e install_dir=/tmp/opencode/close-scratch
localhost : ok=16 changed=4 unreachable=0 failed=0 skipped=21   # exit 0
$ ls -d /tmp/opencode/close-scratch        # dry run created nothing
No such file or directory
$ ANSIBLE_COLLECTIONS_PATH=$HOME/.ansible/collections ../.venv/bin/ansible-playbook \
    playbooks/assets.yaml --check -e install_dir=/tmp/opencode/close-scratch
localhost : ok=4 changed=1 unreachable=0 failed=0 skipped=12    # exit 0
```

`ansible-playbook` is not on the host `PATH`; it lives in
`src/provisioning/.venv/bin/`. `ANSIBLE_COLLECTIONS_PATH` is required because
the scrubbed `HOME` otherwise hides the installed collections. Syntax checks:
both playbooks `--syntax-check` exit 0. Follow-up: run
`playbooks/bootstrap.yaml` + `cli-tools.yaml` + `assets.yaml` for real on a
disposable VM and record the recap.

**Status (addendum A1): RESOLVED** — the host binaries were re-installed from the
pinned checkouts by the host provisioning run; all three now print
`0.1.0 contract 0.1.0` (A1). Body preserved as the "before" side of that record.

**(b) The host's `~/.local/bin/{csg,weg,itr}` are stale pre-migration uv-tool
envs.** `uv tool list` reports the right versions but the envs point at the
retired trees:

```text
$ uv tool list | grep -E 'color-scheme-generator|wallpaper-effects-generator|icon-templates-renderer'
color-scheme-generator v0.1.0
icon-templates-renderer v0.1.0
wallpaper-effects-generator v0.1.0
$ cat ~/.local/share/uv/tools/color-scheme-generator/…/color_scheme_generator-0.1.0.dist-info/direct_url.json
{"url":"file:///home/inumaki/Development/dotfiles-v3/src/cli-tools/color-scheme-generator","dir_info":{}}
   # same shape for weg (…/src/cli-tools/wallpaper-effects-generator), itr (…/icon-templates-renderer);
   # the bundled cli-output dep points at …/src/shared/cli-output
$ itr --version   # exit 1
ModuleNotFoundError: No module named 'config_assembler_engine'
$ weg --version   # exit 1
ModuleNotFoundError: No module named 'cli_output'
$ csg --version   # exit 1
ModuleNotFoundError: No module named 'oci_runtime'
```

The designed path is the next real bootstrap's `uv tool install --force` from
the pinned checkout (proven in isolated `UV_TOOL_DIR`s during S2/S6:
`csg --version` → `0.1.0 contract 0.1.0`). Fix = a real provisioning run, out
of scope here. Consequence while stale: `src/runtime`'s
`test_weg_adapter_integration_real_binary` does not skip (it only checks
`shutil.which("weg")`) and fails on the stale binary — see (d).

**Status: STILL OPEN, re-measured on the fresh binary** — `csg install --image-tag
v9.9.9` against the re-installed `v0.1.0` still exits with
`No such option: --image-tag`. Unchanged by the host run.

**(c) `csg install` has no `--image-tag` option.** The pin travels via the
setting, `COLORSCHEME__CONTAINER__IMAGE_TAG`, which provisioning renders into
`[container] image_tag`. So `csg install --image-tag v9.9.9` is rejected by
the CLI parser (`No such option: --image-tag`, exit 2) — that is *option
validation*, not the tag gate. The "nonexistent tag fails" gate is therefore
enforced upstream, at clone/verify (clone probe quoted from the S6 log in
`tasks.md` §8; the README line is re-read from the pinned checkout):

```text
$ git clone --depth 1 --branch v9.9.9 <csg repo>   # exit 128
Remote branch v9.9.9 not found; checkout NOT created
$ rg -n 'there is no separate' <csg checkout>/README.md
64:`COLORSCHEME__CONTAINER__IMAGE_TAG`); there is no separate `--image-tag` flag because the setting is
```

`verify` asserts each of the four images exists at the tag-qualified
reference, so a mistyped pin fails there rather than at install-time option
parsing. Recorded so nobody "fixes" the missing flag without also adding a
negative test for the setting path.

**Status: STILL OPEN — unchanged and not re-measured for the addendum.** Failure
1 (the moved-bar hard-coded path) is untouched. Failure 2's *cause* — the stale
host `weg` — was removed by A1, so it should now skip; but this record did not
re-run the suite, so do not quote a new count until someone does.

**(d) Pre-existing failures unrelated to this migration.**
`uv run --directory src/runtime pytest -q` → **exit 1, `2 failed, 2122
passed, 4 skipped` in 78 s**:

1. `tests/unit/test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop`
   — `FileNotFoundError` on
   `dotfiles/config/ags/bar/widgets/recording.tsx`. The bar moved to the
   external `ags-apps` unit (this repo's bar sources are retired), so the
   test's hard-coded path is stale. Pre-existing and outside this migration.
2. `tests/integration/test_weg_adapter_integration.py::test_weg_adapter_integration_real_binary`
   — caused by the stale host `weg` from gap (b); it **skips** once the stale
   dir is off `PATH`.

With the stale `~/.local/bin` off `PATH` (the designed environment):

```text
$ src/runtime/.venv/bin/python -m pytest -q src/runtime/tests   # exit 1
FAILED tests/unit/test_recording_indicator.py::TestNoPollingInvariant::test_bar_widget_has_no_poll_loop
1 failed, 2122 passed, 5 skipped, 6 warnings in 73.19s
```

so exactly one known, pre-existing failure remains.

Provisioning side: `tests/unit/test_verify_role.py -k TestVerifyRuntime` →
**exit 1, `6 failed, 3 passed, 82 deselected` in 194 s**, and the *same six*
fail at pre-merge base `6e0633ba` (`6 failed, 3 passed, 80 deselected` in
202 s) — pre-existing, not caused by the merge. The cause is no longer the
120 s timeouts the S2 log recorded: the real `verify.yaml` run now fails fast
because the simulated "provisioned machine" fixture does not create
`<install>/cli-tools/itr/pinned`, which the verify role's pinned-checkout task
reads (`Task failed: Module failed: File not found:
…/install/cli-tools/itr/pinned`). Follow-up: extend
`_build_provisioned_layout` with the three pin records (and any other
pinned-checkout artifacts verify now requires) so this execution guard is
green again rather than permanently red.

**Status: STILL OPEN — unchanged.** The addendum did not re-run
`openspec validate --all`; the 27-item legacy set is untouched by either the
host run or the ticket closure.

**(e) `openspec validate --all` keeps 27 pre-existing failures.** `104 passed,
27 failed (131 items)`, exit 1; identical failing-item set at base
`6e0633ba` (`99 passed, 27 failed (126 items)`). Not delta-less-only: 19
legacy change-level defects **plus** 8 pre-existing spec shape defects (the
names and the error mix are in the 9.1 row). None is `cli-tools-repos`; the
archived specs validate. Follow-up: sweep them under their own change, or set
`skip_specs: true` on the pure-docs changes.

**Status: STILL OPEN — unchanged.** Re-measured on `master` at `56fc4b7e`:
`rg -n "src/cli-tools|src/shared" …` → still **338 lines in 9 files**, same
carve-outs (guard, negative tests/fixtures, historical investigation docs).

**(f) Literal stale-path `rg` residue remains.** `rg -n "src/cli-tools|src/shared"
src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs` → exit 0,
338 lines in 9 files, all expected:

- `scripts/deploy-coverage.py` — the guard must name the paths it asserts
  absent;
- `src/provisioning/tests/unit/{test_compositor_configs_role,test_assets_role,test_cli_tools_role}.py`
  and `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` —
  the guard's negative tests/fixtures, which must construct the retired paths
  to prove rejection;
- `docs/investigation/{S1,S2,S3,S4}-*.md` — read-only historical evidence, out
  of scope by rule (same carve-out the S4/S5 logs record).

**Status (addendum A2): RESOLVED** — all six birth tickets are now `done`, with
acceptance ticked, Closeout evidence, INDEX under Done, and `repo-birth` archived
under `openspec/changes/archive/2026-10-21-repo-birth/`. Body preserved as the
"before" side of that record.

**(g) Birth-ticket bookkeeping is stale in five of six repos** (this is the
one place 0.6's "recorded" half falls short). The tickets were written before
the remotes existed and never closed out:
`cli-output` 8 unchecked / 0 checked acceptance boxes, `icon-templates-renderer`
8 / 0, `color-scheme-generator` 10 / 0, `wallpaper-effects-generator` 5 / 5
with a Closeout that still says `pending (blocked: no remote)` for
`gh run list`, the annotated tag, the anonymous fetch and the release assets,
`config-assembler-engine` 3 / 5 with two `pending` lines; only `oci-runtime`
is fully closed (0 / 10). The gates themselves are green (section 1) — only
the per-repo paperwork lags. Related: every released repo attaches the
**sdist only** (`*.tar.gz`) to its GitHub Release, while the birth acceptance
text asks for wheel + sdist; consumption is by git tag, so nothing is broken,
but the asset expectation and the CI `release` job disagree. Follow-up: close
each birth ticket against section 1's table, and either add the wheel to the
`release` job or relax the ticket text.

## 4. Verification log for this record

| Command | Observed |
| --- | --- |
| `git rev-parse master`; `git ls-remote origin refs/heads/master` | `1b2f644ab38778a573cf1951d8870c411eb73a68` both, exit 0 |
| `git status --short`; `git ls-files src/shared src/cli-tools` | empty; 0 lines |
| `test ! -e src/cli-tools && test ! -e src/shared` | exit 0 (both absent) |
| `rg -n '^    source:' dotfiles/provisioning/cli-tools.yaml` | one match, `34:    source: src/runtime` |
| `make gates-ci` | exit 0 — `contracts-check`, `ansible-embedded-template-lint` (`PASS`), `deploy-coverage` (`PASS`), `ci-gates-parity` (`PASS`), `per-app-drift-symbol-suites` (`OK`) |
| `make deploy-coverage` | exit 0, terminal `PASS -- six packages are consumed from their pinned repos …` |
| `make hermetic` | exit 0, `hermetic: PASS -- no in-repo package sources …` |
| `uv run --directory src/runtime pytest -q` | exit 1, `2 failed, 2122 passed, 4 skipped` (failure 2 = stale host `weg`) |
| same suite with `~/.local/bin` off `PATH` | exit 1, `1 failed, 2122 passed, 5 skipped` (only the bar-path failure) |
| `uv run --directory src/provisioning pytest tests/unit/test_verify_role.py -q -k TestVerifyRuntime` | exit 1, `6 failed, 3 passed, 82 deselected` in 194 s; same six at base `6e0633ba` in 202 s |
| `openspec validate --all` | exit 1, `104 passed, 27 failed (131 items)`; base `6e0633ba` → `99 passed, 27 failed (126 items)`, identical names |
| `diff -r mu/<8 paths>` ×6 repos | 0 differences per repo |
| `make -C <repo> gates` ×6 from `/tmp/opencode` | exit 0 each; `63`/`163`/`288`/`349`/`639`/`1107+2skip` passed |
| `make -C <repo> ci-gates-parity` ×6 | exit 0 each, `PASS …` |
| `uv run pytest -q -k canary` ×6 | `1 passed` each |
| `gh api repos/…/<r> --jq '{private,visibility}'` ×7 | all `private:false, visibility:public` |
| `git ls-remote --tags … 'refs/tags/v*'` and `'refs/tags/<tag>*'` ×7 | one tag each; annotated object + `^{}` commit as tabled |
| `gh run list -R … --limit 3 --json status,conclusion,headBranch` ×6 | all `completed/success` |
| `gh release view <tag> --json tagName,assets` ×6 | `tagName` matches; one asset, the sdist |
| anonymous `GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote` ×7 | exit 0, one line each |
| `ansible-playbook … --syntax-check` (cli-tools, assets) | exit 0 / exit 0 |
| `ansible-playbook … --check -e install_dir=<scratch>` | exit 0, `ok=16 changed=4 failed=0 skipped=21` / `ok=4 changed=1 failed=0 skipped=12`; scratch dir not created |
| `command -v incus` | absent |
| `uv tool list`; `{itr,weg,csg} --version` | three entries at `v0.1.0`; each binary exit 1 with `ModuleNotFoundError` |

## Addendum — 2026-10-21 (host run + ticket closure)

Appended after the record above was merged (`master` at `56fc4b7e`). Two of §3's
gaps are now closed **by execution**, not by argument:

- **gap (b)** — the host's stale `~/.local/bin/{csg,weg,itr}`. A real
  provisioning run re-installed all three from the pinned checkouts; they now
  serve actual work (A1).
- **gap (g)** — the stale per-repo birth-ticket bookkeeping. All six birth
  tickets are `done`, ticked, evidenced, indexed under Done, and their
  `repo-birth` change is archived (A2).

Gap (a) is now **half** resolved: the host run happened, the disposable-VM run
still has not. Everything else in §3 is unchanged; the per-item status lines
there say which. §4's table above is left as the pre-addendum measurement — this
addendum carries its own evidence table at A4.

### A1. Host provisioning run — resolves gap (b), and the non-VM half of gap (a)

The playbooks were driven the way `AnsibleExecutor` drives them
(`src/provisioning/src/provisioning/adapters/ansible_executor.py:269-287`:
`ansible-playbook -i <inventory> --tags <tags> --extra-vars <json> <playbook>` —
note the flags, and that the playbook path comes **last**), with the two locked
seam extra-vars from `_seam_extra_vars()`
(`src/provisioning/src/provisioning/application/use_cases.py:38-48`).
`install_dir` is `resolve_install_dir()` = `$XDG_DATA_HOME/dotfiles`
(`use_cases.py:27-35`), re-checked on this host:

```text
$ src/provisioning/.venv/bin/python -c \
    'from provisioning.application import resolve_install_dir; print(resolve_install_dir())'
/home/inumaki/.local/share/dotfiles      # the "<spine>" in the commands below
```

`ansible-playbook` is still not on `PATH` (gap (a)); the binary used is
`src/provisioning/.venv/bin/ansible-playbook`. The shape, once per playbook:

```text
$ ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg \
    src/provisioning/.venv/bin/ansible-playbook \
    -i src/provisioning/ansible/inventory/localhost.yaml \
    --tags all \
    --extra-vars '{"install_dir": "/home/inumaki/.local/share/dotfiles", "os_family": "arch"}' \
    src/provisioning/ansible/playbooks/<playbook>.yaml
```

Order: `cli-tools`, `filesystem`, `assets`, `settings`, `config-links`,
`verify`. The `become` stages (`packages`, `bootstrap`, `display-manager`, …)
were **excluded on purpose**: sudo needs a password on this host and an
unattended run cannot supply one.

#### A1.1 First-run recaps (verbatim `PLAY RECAP` counters)

| Playbook | ok | changed | failed | skipped |
| --- | --- | --- | --- | --- |
| `cli-tools` | 34 | 11 | 0 | 3 |
| `assets` | 15 | 1 | 0 | 1 |
| `settings` | 7 | 1 | 0 | 0 |
| `config-links` | 155 | 0 | 0 | 162 |
| `verify` | 153 | 0 | 0 | 2 |

`verify` exited 0 only after the Bluetooth fix in A1.6. `filesystem` also ran
(second in the order); its first-run recap was not transcribed, so the assertion
used for it is the second run's `changed=0` below.

#### A1.2 Before / after on the host binaries

Before (gap (b) restated — this is why no real request could be served on this
host before the run):

```text
$ csg --version   # exit 1
ModuleNotFoundError: No module named 'oci_runtime'
$ weg --version   # exit 1
ModuleNotFoundError: No module named 'cli_output'
$ itr --version   # exit 1
ModuleNotFoundError: No module named 'config_assembler_engine'
```

After the run (re-measured 2026-10-21 on the live host):

```text
$ csg --version; weg --version; itr --version    # all exit 0
0.1.0 contract 0.1.0
0.1.0 contract 0.1.0
0.1.0 contract 0.1.0
```

Checkouts and pin records:

```text
$ ls -d ~/.local/share/dotfiles/cli-tools/*/
…/cli-tools/csg/  …/cli-tools/itr/  …/cli-tools/weg/
$ ls ~/.local/share/dotfiles/cli-tools/csg
pinned
v0.1.0
$ cat ~/.local/share/dotfiles/cli-tools/{csg,weg,itr}/pinned
v0.1.0
v0.1.0
v0.1.0
```

Precision worth keeping: `pinned` sits at `<install>/cli-tools/<name>/pinned`,
**next to** the `<tag>/` checkout directory — not inside it. That is the exact
path gap (d)'s verify-role follow-up reads, and the reason its simulated layout
must create it.

#### A1.3 Images and settings carry the pin, never `latest`

The configured engine is podman (`[container] engine = "podman"` in the rendered
csg settings), and it holds exactly five tag-qualified images:

```text
$ podman images --format '{{.Repository}}:{{.Tag}}' | rg 'csg|weg'
localhost/csg-base-podman:v0.1.0
localhost/csg-custom-podman:v0.1.0
localhost/csg-pywal-podman:v0.1.0
localhost/csg-wallust-podman:v0.1.0
localhost/weg-podman:v0.1.0
```

Four `csg` + one `weg`, every one at `:v0.1.0`. No new `:latest` was produced:
`docker images` still shows only the pre-run `*-docker:latest` set, all six days
old, untouched by this run (the two runtimes are separate stores on this host).

Settings agree with the images (AD-7: the tag *is* the pin):

```text
$ rg -n '^image_tag' ~/.config/color-scheme-generator/settings.toml \
      ~/.local/share/dotfiles/config/weg/settings.toml
/home/inumaki/.config/color-scheme-generator/settings.toml:29:image_tag = "v0.1.0"
/home/inumaki/.local/share/dotfiles/config/weg/settings.toml:32:image_tag = "v0.1.0"
```

`csg`'s templates were deployed **from the pinned checkout**, byte-identical:

```text
$ diff -r \
    ~/.local/share/dotfiles/cli-tools/csg/v0.1.0/src/color_scheme_generator/defaults/templates \
    ~/.local/share/dotfiles/config/color-scheme-generator/templates
# exit 0, no output — identical (12 templates)
```

#### A1.4 The binaries do real work (not just `--version`)

| Command | Observed |
| --- | --- |
| `csg generate` | exit 0, **8/8** artifacts: `colors.adw.css`, `colors.btop.theme`, `colors.conf`, `colors.gtk.css`, `colors.kitty`, `colors.rasi`, `colors.sequences`, `colors.yaml` |
| `weg batch all` | exit 0, **20** files under `default/{composite,effect,preset}` |
| `itr render` | exit 0, **136** SVGs |
| `itr list <manifest>` | exit 0 (re-run against `icon-mappings/*.yaml`) |

The artifact counts are reproducible from the run's output tree:

```text
$ ls /tmp/opencode/cli-proof/csg | wc -l            # 8
$ ls /tmp/opencode/cli-proof/itr | wc -l            # 136
$ find /tmp/opencode/cli-proof/weg -type f | wc -l  # 20
```

This is the difference between gap (b) as recorded ("the designed path is proven
in isolated `UV_TOOL_DIR`s") and what is proven now: the **live** host binaries,
against the **live** spine, produce the artifacts.

#### A1.5 Idempotency: the second run

A second pass of the same six playbooks is what separates "it worked" from "it
converges". `cli-tools` reported `changed=7`, and all seven are enumerated,
non-state changes:

1. the three `pinned` record writes (the role rewrites the assertion on every
   pass — by design, it is the claim being asserted);
2. one `uv tool install --force` of `dotfiles-runtime` (`--force` means it always
   reports changed);
3. one transient smoke-probe tempfile, created and removed inside the run;
4. the two by-design image build loops (`csg` base+backend, `weg`).

Item 4 is the one that looks like a bug and is not; the role states the semantics
in its own words
(`src/provisioning/ansible/roles/cli_tools/tasks/main.yml:304-311`): *"NO
`creates:` on these tasks: image EXISTENCE does not imply FRESHNESS. A stale
image … must be rebuilt, so the task runs every apply; the container engine's
content-addressed cache makes an unchanged rebuild cheap and correct. … (idempotency
= no STATE drift, not no CHANGED report). Do NOT reintroduce an existence gate."*

`filesystem`, `assets`, `settings` and `config-links` re-ran with **`changed=0`**,
i.e. the deployed state converged. The first pass had `failed=0` everywhere; the
second pass's only non-zero counter was `cli-tools`'s `changed=7` above.

#### A1.6 One host change outside the migration's scope

`verify` initially failed on the Bluetooth soft-block. It was cleared with an
unprivileged `rfkill unblock bluetooth`, after which `verify` exited 0
(`ok=153 changed=0 failed=0 skipped=2`). Recorded because it is a host-state
change an auditor will otherwise trip over when re-running the sequence, and
because "verify green" is only true **after** it.

### A2. Birth tickets closed — resolves gap (g)

All six repos now have their birth ticket at `status: done`, every acceptance box
ticked, a Closeout with evidence, the ticket moved to the INDEX's Done section,
and the `repo-birth` OpenSpec change archived under
`openspec/changes/archive/2026-10-21-repo-birth/`. Active changes are now **zero**
in each repo (`ls <repo>/openspec/changes` → `archive` only).

Main HEADs at closure:

| Repo | `main` HEAD | Ticket |
| --- | --- | --- |
| `cli-output` | `ec7defe` | `REQ-001-repo-birth` → `done` |
| `config-assembler-engine` | `8896880` | `REQ-001-repo-birth` → `done` |
| `oci-runtime` | `3aa88a2` | `REQ-001-repo-birth` → `done` |
| `icon-templates-renderer` | `2543c00` | `REQ-001-repo-birth` → `done` |
| `wallpaper-effects-generator` | `be0bbd6` | `REQ-001-repo-birth` → `done` |
| `color-scheme-generator` | `1b235b5` | `REQ-001-repo-birth` → `done` |

All six working trees were clean at closure (`git status --porcelain` → empty),
and `rg -c '^\s*[-*] \[ \]' <archive>/2026-10-21-repo-birth/*.md` → no matches,
so no unticked box survives in the archived change.

**Two corrections this pass found.** Both were paperwork diverging from reality,
not code problems:

1. **`oci-runtime` was reported as closed but was not.** At `3aa88a2^` the ticket
   still read `status: in-progress` and its `## Closeout` was a placeholder
   ("Filled after the gates, CI and tag" — the evidence wall was empty). `3aa88a2`
   filled it, flipped the status, moved the INDEX entry and archived the change.
   The acceptance audit itself was re-run against the published repo, so the
   closeout is measured, not transcribed. The failure mode here: reading "closed"
   from the *narrative* (gates/CI/tag all existed) instead of from `status:`.
2. **`wallpaper-effects-generator`'s closeout still said `pending (blocked: no
   remote)`** for the CI runs, the annotated tag, the anonymous fetch and the
   release assets — text written at `5a35456`, when there genuinely was no remote.
   It was refreshed at `27305bd`/`94b6d5a`, then pinned to its measurement commit
   at `be0bbd6`. `rg "pending \(blocked|blocked: no remote"` on the current ticket
   matches only the sentence explaining that the old text belonged to `5a35456`
   and no longer describes the tree.

**Libraries have no console script — `uv tool install` exits 2 by design.** This
looks like a failure and is not: `cli-output`, `config-assembler-engine` and
`oci-runtime` are libraries, so they declare no `[project.scripts]` and uv
refuses to cut a tool shim. Measured:

```text
$ UV_TOOL_DIR=/tmp/opencode/addendum-tooldir2 uv tool install /home/inumaki/Development/config-assembler-engine
 + config-assembler-engine==0.1.0 (from file:///home/inumaki/Development/config-assembler-engine)
No executables are provided by package `config-assembler-engine`; removing tool
error: Failed to install entrypoints for `config-assembler-engine`     # uv exit 2
```

Install proof for a library therefore uses an isolated environment, not a tool
shim (`uvx --from` / a throwaway venv):

```text
$ uvx --from /home/inumaki/Development/cli-output python -c \
    "import cli_output, importlib.metadata as m; print('cli_output', m.version('cli-output'))"
cli_output 0.1.0                                                        # exit 0
```

Anyone "fixing" the exit 2 by adding a console script would be changing the
public surface of a library to satisfy a provisioning check; the right fix, if
one is wanted, is for the check to use the venv form for libraries and the tool
form for the three CLIs.

### A3. Gap status after this addendum

| Gap | Status | Closed by / note |
| --- | --- | --- |
| (a) no real provisioning run | **half closed** | Host run done (A1). Disposable-VM run **still not done** — `command -v incus` is still absent. |
| (b) stale host `~/.local/bin/{csg,weg,itr}` | **closed** | A1: re-installed from the pinned checkouts; `0.1.0 contract 0.1.0` ×3, real artifacts produced. |
| (c) `csg install` has no `--image-tag` | **open** | Re-measured on the fresh binary: still `No such option: --image-tag`. |
| (d) pre-existing test failures | **open, unchanged** | Not re-run for this addendum. Failure 1 is untouched; failure 2's cause (stale `weg`) is gone, so expect it to skip — re-measure before quoting. |
| (e) `openspec validate --all` 27 failures | **open, unchanged** | Not re-run. Legacy change-level + spec-shape set, none of it `cli-tools-repos`. |
| (f) literal stale-path `rg` residue | **open, unchanged** | Re-measured on `56fc4b7e`: 338 lines in 9 files, same carve-outs. |
| (g) stale birth-ticket bookkeeping | **closed** | A2: all six `done`, ticked, evidenced, indexed, archived; active changes zero. |

The wheel-vs-sdist half of (g)'s closing paragraph is **not** addressed by A2:
every release still attaches the sdist only, and the birth acceptance text still
asks for wheel + sdist. Consumption is by git tag, so nothing is broken — but the
expectation mismatch is still there for whoever reconciles the `release` job.

### A4. Evidence re-measured while writing this addendum

Everything below was re-executed on the merged `master` line and/or the live host
on 2026-10-21, so the addendum does not rest on the transcript of the run alone.

| Command | Observed |
| --- | --- |
| `src/provisioning/.venv/bin/python -c 'from provisioning.application import resolve_install_dir; …'` | `/home/inumaki/.local/share/dotfiles` |
| `{csg,weg,itr} --version` | `0.1.0 contract 0.1.0` ×3, exit 0 each |
| `cat <install>/cli-tools/{csg,weg,itr}/pinned` | `v0.1.0` ×3 |
| `podman images … \| rg 'csg\|weg'` | exactly 4 `csg` + 1 `weg`, all `:v0.1.0` |
| `docker images … \| rg 'csg\|weg'` | only the pre-existing `*-docker:latest` set, six days old |
| `rg -n '^image_tag' <csg,weg settings>` | `v0.1.0` in both (`settings.toml:29`, `weg/settings.toml:32`) |
| `diff -r <pinned csg templates> <deployed templates>` | exit 0, identical, 12 files |
| `ls /tmp/opencode/cli-proof/{csg,itr}` / `find …/weg -type f` | 8 / 136 / 20 artifacts |
| `itr list ~/.local/share/dotfiles/icon-mappings/icons.yaml` | exit 0 |
| `UV_TOOL_DIR=… uv tool install <library>` | exit 2, `No executables are provided …` |
| `uvx --from <cli-output> python -c '…version…'` | `cli_output 0.1.0`, exit 0 |
| `csg install --image-tag v9.9.9` | `No such option: --image-tag` (gap (c) still open) |
| `git -C <each of six> rev-parse --short HEAD` | `ec7defe`, `8896880`, `3aa88a2`, `2543c00`, `be0bbd6`, `1b235b5` |
| `rg -n '^status:' <each>/tickets/REQ-001-repo-birth/ticket.md` | `status: done` ×6 |
| `ls <each>/openspec/changes` | `archive` only in all six; archived dir = `2026-10-21-repo-birth` |
| `rg -c '^\s*[-*] \[ \]' <archive>/2026-10-21-repo-birth/*.md` ×6 | no matches (nothing unticked) |
| `rg -n "src/cli-tools\|src/shared" src dotfiles scripts Makefile .github bootstrap.sh AGENTS.md docs` | 338 lines in 9 files (gap (f) unchanged) |
