# Post-migration closure record — `assets-repo-split`

Written 2026-10-22, after S0–S6 landed on `master` (base `fca6552c`) and S7 was
executed in `.worktrees/S7/` on `ticket/S7-composition-closeout`.

**This file is additive.** `tasks.md` in this directory is the point-in-time
record of the change as it was archived; this file is the live answer to "did
S7 actually close the composition repo?", with the command and the observed
result for each claim. The change is a **retrospective** record of a migration
whose planning lived in the spine/slices: the assets split never had an
OpenSpec change before this one.

Re-run target: `fca6552c` plus the S7 commits (`ticket/S7-composition-closeout`).
The merge to `master` is a fast-forward of that branch tip, so after it
`git rev-parse master` equals the planning commit SHA named in the merge report;
`git merge-base --is-ancestor fca6552c master` exits 0.

Authoritative companions:

- spine: `_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/ARCHITECTURE-SPINE.md` (AD-1…AD-17)
- slices: `…/SLICES.md` (S0–S7)
- **residual ledger: `…/RESIDUALS.md`** — R-15/R-16/R-17 were added by this closeout (§3 below); R-01…R-14 are unchanged
- pin table: `ARCHITECTURE.md` §4.1

## 1. Completion table

### The slices (S0–S6, landed before this change was written)

| Slice | Landed as | Evidence anchor |
| --- | --- | --- |
| S0 — birth `dotfiles-assets` (`v0.1.0`) | sibling repo | its own birth ticket + `validate`/`lint`/`hermetic` gates in that repo |
| S1 — icons + content (`v0.2.0`) | `899c3f1a` (pin/fetch), `a0e4ada2` (deletion+guard) | `make deploy-coverage` exit 0; runtime icon tests |
| S2 — configs (`v0.3.0`) | `a3220b80` (consumer cut), `7d0ad759` (deletion) | byte-identical import proven before deletion; `deploy-coverage` exit 0 |
| S3 — templates (`v0.4.0`) | `b38cf302` (render cut), `1f6c2f12` (docs/parity), `0a33a1da` (test seed), `2f5ee95e` (spine fixes) | required-var parity test; `deploy-coverage` exit 0 |
| S4 — desktop (`v0.5.0`) | `3cb965f0` (contract+deploy), `2318d1c3` (deletion+guard) | `deploy-coverage` asserts the three layers; `verify` re-asserts the deployed set |
| S5 — schema window + pinned content | `854bac08` | `assets_schema_support` on fetch + verify; `deploy-coverage` asserts the windows equal |
| S6 — engine extraction (`dotfiles-provision v0.1.0`) | `fca6552c` (cutover + `src/provisioning` deletion) | `bootstrap.sh` installs the pinned checkout editable; both composition gates read `.dev/dotfiles-provision-v0.1.0/` |

### Per-task state (S7, as archived)

Every box in `tasks.md` is ticked; the archive tool reported **Task status:
✓ Complete**. The table below is the executed evidence, not a restatement.

| Task | Now | Evidence |
| --- | --- | --- |
| Finalize the pin set in one place | **satisfied** | `ARCHITECTURE.md` §4.1 (7 rows: installer, assets, 3 CLIs, `cli-output`, `cli-invocation-contract`, plus the honest not-pinned-here row) + `assert_pin_set` in `scripts/deploy-coverage.py` |
| Composition catch-all | **satisfied** | `assert_composition_only`: `src/` allowlist = `runtime`; `dotfiles/` allowlist = `config`, `provisioning`; `dotfiles/config/` = exactly `btop/active-theme`; `src/provisioning/`, `dotfiles/assets/`, `dotfiles/applications/`, `dotfiles/scripts/` absent. The one local `source:` and installer-not-a-tool checks already existed (`assert_manifest_source_scope`) |
| `gates-ci` stays six targets; parity green | **satisfied** | `make gates-ci` exit 0; `ci-gates-parity` printed `authoritative gates-ci set (6)` = `workflow jobs (6)`, one declared rename (`contracts-check->contracts`) |
| Product metadata | **satisfied** | `LICENSE` (MIT) + `CHANGELOG.md` (five 0.x entries citing the spine/slices/ledger/closure record) |
| Docs true | **satisfied** | `ARCHITECTURE.md` §1/§2/§4.1/§5/§6.1/§6.6/§9/§10/§11/§12/§13, `AGENTS.md` §2, `docs/02-config-in-spine-pattern.md`; the literal doc scan exits 1 |
| Archive + `POST-MIGRATION.md` | **satisfied** | `openspec validate assets-repo-split --strict` → valid; `openspec archive assets-repo-split --yes` → archived as `2026-10-22-assets-repo-split`; this file |

### Terminal gate output (verbatim, pre-merge)

```text
$ make gates-ci   # exit 0
contracts-check                 39 passed, 1 skipped
runtime-architecture           132 passed
ansible-embedded-template-lint  PASS (75 files scanned under engine v0.1.0 ansible)
deploy-coverage                 PASS (+ the pin-set and COMPOSITION-ONLY lines)
ci-gates-parity                 PASS (6 gates == 6 jobs; 1 declared rename)
per-app-drift-symbol-suites     OK (no in-repo suites)
```

```text
$ make deploy-coverage   # exit 0
CHECK pinned installer engine v0.1.0 at …/.dev/dotfiles-provision-v0.1.0
deploy-coverage: pin set — installer dotfiles-provision v0.1.0 (from
  dotfiles/provisioning/installer.pin; bootstrap.sh reads it, no literal),
  assets dotfiles-assets v0.5.0, CLIs csg v0.2.0, itr v0.2.0, weg v0.2.0,
  runtime pins cli-invocation-contract v0.2.0, cli-output v0.1.0 — every pin
  semver and gate-mirrored
deploy-coverage: COMPOSITION-ONLY — src/ holds runtime/ only, dotfiles/ holds
  ['config', 'provisioning'] (config/ = ['btop/active-theme']), and
  src/provisioning/, dotfiles/assets/, dotfiles/applications/, dotfiles/scripts/
  are absent
deploy-coverage: PASS -- six packages are consumed from their pinned repos
  (cli-output, config-assembler-engine, oci-runtime, itr, weg, csg); … the CLI
  manifest carries exactly ONE in-repo source (dotfiles-runtime -> src/runtime)
```

```text
$ make hermetic   # exit 0
hermetic: PASS -- no in-repo package sources; the six extracted
  packages (cli-output, config-assembler-engine, oci-runtime,
  itr, weg, csg) run their own 'make hermetic' in their pinned
  repos; this repo's src/runtime is covered by 'make gates-ci'
```

```text
$ test ! -e src/provisioning                                            # exit 0
$ git ls-files src | sed 's#^src/##; s#/.*##' | sort -u                 # runtime
$ rg -n 'path = "\.\.|editable = true' --glob 'pyproject.toml' .        # exit 1 (no match)
$ rg 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md
                                                                        # exit 1 (no match)
```

### Negative controls (the new gates bite)

| Mutation | Observed |
| --- | --- |
| `touch dotfiles/config/extra/x` | exit 1 — `dotfiles/config/ must hold exactly ['btop/active-theme'] … found ['btop/active-theme', 'extra/x']` |
| `mkdir -p src/provisioning` | exit 1 — `src/provisioning/ still exists — the engine is the pinned external dotfiles-provision repo …` |
| `printf 'main\n' > dotfiles/provisioning/installer.pin` | exit 1 — `must contain one semver tag (vX.Y.Z …); got 'main'` |
| append `# v0.1.0` to `bootstrap.sh` | exit 1 — `bootstrap.sh names the engine tag 'v0.1.0' literally …` |
| bump a CLI tag in `cli-tools.yaml` only | exit 1 — role mirror `does not mirror … cli-tools.yaml` |
| set `verify_csg_version: v9.9.9` in the cached engine | exit 1 — `verify_csg_version is 'v9.9.9' but the manifest pins 'v0.2.0'` |

All mutations were reverted (`git status --short` showed only the intended S7
edits before commit).

## 2. What the repository looks like now

- **Pins only, no package sources.** `src/` holds `runtime/` alone. `dotfiles/`
  holds the manifests (`provisioning/`) and the one mutable preference
  (`config/btop/active-theme`). The installer engine is
  `dotfiles/provisioning/installer.pin` → `dotfiles-provision v0.1.0`; the corpus
  is `assets.tag` → `dotfiles-assets v0.5.0`; the CLI manifest is
  `csg`/`weg`/`itr` at `v0.2.0`; the runtime's `[tool.uv.sources]` pins
  `cli-output v0.1.0` and `cli-invocation-contract v0.2.0` (full table:
  `ARCHITECTURE.md` §4.1).
- **Two consumption shapes only** (unchanged from `cli-tools-repos`): git-tag
  `[tool.uv.sources]` for libraries/contracts, `{name,repo,tag}` + tag-bearing
  checkout for CLIs; `dotfiles-runtime -> src/runtime` is the only local
  `source:`.
- **The installer is a separate pin, never a tool entry.**
  `assert_manifest_source_scope` rejects an engine entry in
  `cli-tools.yaml`; `bootstrap.sh` reads `installer.pin` and installs the
  checkout editable.
- **The composition gates read the engine checkout.** `deploy-coverage` and
  `ansible-embedded-template-lint` resolve `.dev/dotfiles-provision-<tag>/` and
  print the `CHECK` line; there is no in-repo fallback.

## 3. Known gaps / follow-ups

Each item is real and observed. The detailed entries with impact, planned
resolution and closure proof are in `RESIDUALS.md`; this section states what the
closeout did **not** close.

**R-15 — the engine wheel is not self-contained (OPEN, P2).** The closeout
exposed the packaging caveat rather than fixing it: `pyproject.toml` builds the
wheel from `src/provisioning` only, so `unzip -l
dotfiles_provision-0.1.0-py3-none-any.whl | grep -E ' ansible/' | wc -l` → **0**
while the sdist carries **87** `ansible/` entries, and
`src/provisioning/cli/main.py:106` resolves `_ANSIBLE_ROOT` beside the package.
`bootstrap.sh:329-368` therefore clones the tag and installs the checkout
`--editable`. Closure: ship `ansible/` as package data, then install
`git+…@tag`.

**R-16 — the composition gates need the cached engine checkout (OPEN, P2).** A
cold, network-less checkout cannot gate; the failure is loud and correct (no
silent fallback). Reproduced with an empty cache and an unreachable proxy:

```text
FAIL cannot fetch the pinned installer engine v0.1.0 into
  /tmp/opencode/engine-offline/dotfiles-provision-v0.1.0 (… Failed to connect to
  github.com:443 over proxy 127.0.0.1 …). The composition gates need the engine
  checkout; connect once, or pre-populate … at v0.1.0. Offline is a hard
  failure, never a silent pass.                                         # exit 1
```

Closure: cache the checkout in CI keyed by the pin + an explicit offline mode.

**R-17 — the engine tag is not asserted by `verify` (OPEN, P2).** The pin is
proven by `scripts/engine_checkout.py` (semver + checkout HEAD) on the gating
machine, not on the provisioned one: the engine `verify` role has no engine-tag
task (`rg` → two comments only, `tasks/main.yml:62,70`), and `bootstrap.sh`'s
`verify` call passes no expected tag. Closure: `expected_engine_tag` extra-var +
`dotfiles-provision version` assertion; runs on the VM gate still tracked by
R-10.

**Still open from the earlier ledger** (unchanged by S7): R-01 (AD-8.4 parity is
developer-only), R-02 (`TestVerifyRuntime` fixture), R-03 (CPython 3.15/pillow),
R-04 (display-manager host apply), R-05 (no `validate-configs`), R-06
(`hyprland.lua` token, accepted), R-07 (`btop/active-theme` stays by design),
R-08 (stale docs outside the S7 scan), R-09 (27 legacy OpenSpec failures), R-10
(VM end-to-end never run — `incus` absent), R-11 (S5 landed in `854bac08`; the
ledger entry predates that merge), R-12, R-13, R-14. `make hermetic` is still a
no-op PASS by design (`HERMETIC_PACKAGES` empty).

## 4. Verification log for this record

| Command | Observed |
| --- | --- |
| `git rev-parse HEAD` (base) | `fca6552c` |
| `openspec validate assets-repo-split --strict` | `Change 'assets-repo-split' is valid`, exit 0 |
| `openspec archive assets-repo-split --yes` | archived as `2026-10-22-assets-repo-split`; `Task status: ✓ Complete`; specs created: `assets-repo-boundaries`, `assets-repo-consumption`, `composition-closeout`, `installer-engine-extraction` (+13 requirements) |
| `openspec validate --all` | exit 1, `Totals: 108 passed, 27 failed (135 items)`; the 27 are the pre-existing legacy set (was `104/27/131`), all four new specs pass |
| `make gates-ci` | exit 0 — see §1 |
| `make deploy-coverage` | exit 0 — pin-set + `COMPOSITION-ONLY` lines |
| `make hermetic` | exit 0 — no-op PASS, quoted above |
| `test ! -e src/provisioning` | exit 0 |
| `git ls-files src \| sed 's#^src/##; s#/.*##' \| sort -u` | `runtime` |
| `rg -n 'path = "\.\.\|editable = true' --glob 'pyproject.toml' .` | exit 1 |
| `rg 'src/provisioning\|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md` | exit 1 |
| `uv build --wheel --out-dir /tmp/opencode/engine-dist` (engine `v0.1.0`) | wheel built; `grep -E ' ansible/'` → 0 entries; sdist → 87 |
| offline cold-cache gate (bad proxy) | exit 1, loud R-16 message |
| six negative controls (table in §1) | each exit 1 with a named failure |

## 5. Engine-packaging caveat (read this before "fixing" bootstrap)

Do **not** replace the `--editable` install with `uv tool install git+…@tag`
without fixing the wheel first: the console script would exist but every
playbook path (`_ANSIBLE_ROOT`) would point at a non-existent
`lib/pythonX/ansible`. The pinned **checkout** is the installable form of the
engine at `v0.1.0` (R-15). Likewise, do not vendor `ansible/` into this repo —
that re-creates the in-repo engine the split deleted (AD-17, guarded by
`assert_composition_only`).
