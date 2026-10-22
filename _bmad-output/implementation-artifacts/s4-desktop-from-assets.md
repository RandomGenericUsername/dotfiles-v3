# S4 — `desktop` → assets `v0.5.0` (three validation layers)

Slice: `_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/SLICES.md`
§S4 + spine AD-10. Worktrees: `.worktrees/s4/` in both repos
(`ticket/s4-assets-desktop`, `ticket/s4-desktop-from-assets`).

## Acceptance

### Assets (`dotfiles-assets`, `v0.5.0`)

- [x] Six `.desktop` entries in `desktop/applications/`; `toggle-touchpad` in
      `desktop/scripts/` with mode `0755` (`stat -c %a` → `755`).
- [x] Every entry carries `TryExec=` naming the binary its `Exec` launches
      (`antigravity-ide`, `code`, `devin-desktop`, `kitty` ×2, `tidal-hifi`). Each
      entry differs from the consumer source by exactly one added line
      (`git diff --no-index --numstat` → `+1 -0`); the script is byte-identical
      (`cmp` rc 0, sha256 `d1a94536…a69e6c7` on both sides).
- [x] `desktop/desktop.yaml`: `schema_major: 1`, one record per entry, exactly
      `{file, requires, optional}`; 6 requires names, 2 optional (`codex`,
      `copilot`), each occurring in its own entry's `Exec` line.
- [x] `make validate-desktop` (AD-10 layer 1) is a `GATES` member with its own CI
      job: Desktop Entry parse (`[Desktop Entry]`, `Type`, `Name`, `Exec`, `Icon`,
      `TryExec`), `Exec` tokenized with the spec's quoting rules + field-code
      stripping, argv[0] basename ∈ `requires`, `TryExec` present + same binary,
      contract == `.desktop` set both ways, scripts executable with a shebang, and
      `shellcheck` in the same target. `make ci-gates-parity` → `GATES (7)`.
- [x] Vacuity proof: bogus `Exec` → rc 2 naming `code.desktop` and
      `definitely-not-installed`; a missing `TryExec`, a dropped contract record,
      a 0644 script, an invented `optional` name and an unsupported YAML flow
      collection each fail with their own message (restored → rc 0).
- [x] `catalog.yaml` declares `desktop` schema-bearing (`desktop/desktop.yaml`,
      `schema_major: 1`); `validate-catalog.py` reads a YAML contract through the
      same strict subset (sequence-of-mappings items added), so AD-12 covers it.
- [x] `desktop/README.md` documents the three layers and their owners, the
      `TryExec` rationale, the `requires`/`optional` semantics, the scope boundary
      (launcher wrappers stay in `cli_tools`) and the vacuity proof.
- [x] Annotated `v0.5.0` (tag object `1fdbc858…`, peeled `fc0ce5d6…`), release
      published with notes and zero assets; CI run `39813199995` on `fc0ce5d6` →
      success, 8/8 jobs (incl. `validate-desktop`); the ticket-record commit
      `d894f9bf` is green too (`39813334068`).
- [x] Fresh anonymous clone at `v0.5.0`: `make gates` rc 0, `make ci-gates-parity`
      rc 0.

### dotfiles (`dotfiles-v3`)

- [x] Pin bumped end-to-end: `assets.tag` + the three literal entry sources,
      `assets_pinned_tag`, and every per-role mirror (`btop_config`,
      `config_copies`, `compositor_configs`, `display_manager`, `kitty_config`,
      `wlogout_config`, `zsh_config`, `verify`) → `v0.5.0`; parity tests green.
- [x] `roles/compositor_configs` reads `<install>/assets/<tag>/desktop/…`
      (`compositor_configs_assets_desktop_dir` + `_desktop_contract_file`);
      `compositor_configs_repo_root` deleted (no `playbook_dir` path remains).
- [x] Layer 2 before the copy: pinned-class stat+assert, contract slurp+parse,
      contract ↔ role entry-set assert, `command -v` probe per declared binary, a
      per-item assert for `requires` (names entry + binary), a debug report for
      skipped `optional` entries, and the deploy loop over the filtered set.
- [x] Layer 3 in `verify`: deployed six-entry stat+assert; the deployed file's own
      `Exec` argv[0] resolved (absolute → executable, bare → `command -v`); the
      seven keybind-invoked launchers must exist **and** be executable; the
      pinned desktop pieces are asserted under `<install>/assets/<tag>/desktop`.
- [x] Destructive-last: `dotfiles/applications/` and `dotfiles/scripts/` deleted;
      `deploy-coverage` gained `assert_no_in_tree_desktop_corpus` (absence + deploy
      shape + resolution ordering), with negative tests for both retired trees, a
      repo-source copy, a non-tag pin mirror and a removed required-binary assert.
- [x] Role header, `ARCHITECTURE.md` (§4 pin table, §5 repo map, §6.5), `docs/02`,
      the docs pin table (`docs/Adding an Icon — …`), `packages.yaml` and
      `group_vars/arch.yml` name the corpus and the retired trees.

## Evidence (command → observed)

Assets (worktree, then fresh clone):

```text
make validate-desktop
  entries=6 with_TryExec=6 contract_records=6 requires=6 optional=2 scripts=1
  shellcheck -> 1 script(s) clean
  PASS (rc 0)
make gates      -> rc 0   (7 gates + hermetic)
make gates-ci   -> rc 0
make ci-gates-parity -> GATES (7) / workflow jobs (8) / PASS
openspec validate --specs -> 1 passed (assets repo), 2 long-requirement WARNINGs
git ls-remote --tags origin 'refs/tags/v0.5.0*' -> tag object 1fdbc858… + peeled fc0ce5d6…
gh run view 39813199995 -> 8/8 jobs success (validate, validate-icons, validate-content,
  validate-templates, validate-desktop, lint, hermetic, ci-gates-parity)
fresh clone @v0.5.0: make gates -> rc 0
```

Dotfiles (worktree):

```text
make deploy-coverage -> rc 0, prints the desktop-corpus PASS line
make gates-ci        -> rc 0 (6 gates; ci-gates-parity 6 == 6)
make hermetic        -> rc 0 (explicit PASS: no in-repo package sources)
uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py \
  tests/unit/test_verify_role.py tests/unit/test_assets_role.py \
  tests/unit/adapters/test_yaml_manifest_reader.py tests/unit/test_template_vars_parity.py \
  -q -k "not TestVerifyRuntime" -> 286 passed, 11 deselected
# with DOTFILES_ASSETS_DESKTOP_DIR / DOTFILES_ASSETS_CONFIGS_DIR pointed at the assets
# checkout, test_compositor_configs_role.py alone: 87 passed, 1 skipped (0 with both)
test_verify_role.py -k "TestVerifyRuntime" -> 5 passed, 6 failed — PRE-EXISTING: the
  synthetic machine predates the cli-tools pin split and aborts at "Read the itr pin
  record" (`install/cli-tools/itr/pinned` missing). Reproduced on master:
  `pytest ... -k test_verify_passes_on_a_provisioned_machine` → same failure (1 failed).
  The two new layer-3 negative locks pass (they start at the desktop block).
openspec validate --specs -> 41 passed, 8 failed (cli-runtime-engine-scope,
  container-image-engine-tagging, csg-image-naming, oci-*) — identical on master;
  S4 touches no spec.
```

Deletion diffstat (commit `2318d1c3`): 7 files, 145 deletions —
`dotfiles/applications/{antigravity-ide,code,codex,copilot,devin-desktop,tidal-hifi}.desktop`
(110 lines) + `dotfiles/scripts/toggle-touchpad` (35 lines).

`ls -A dotfiles` → `config  provisioning` (the mutable `btop/active-theme` and the
five manifests; nothing else).

## Deviations

1. **`validate-desktop` joins `GATES`, not the `validate` target.** SLICES says "wire
   into `validate`/`gates`"; making `validate` depend on it would run the class
   validator twice in one `make gates` (once via `validate`, once via the new
   member) and change what the envelope target means. It is a `GATES` member with
   its own CI job and a `hermetic` step, so `gates`, `gates-ci`, CI and parity all
   run it.
2. **`shellcheck` runs in BOTH `validate-desktop` and `lint`.** Layer 1 owns its
   class's scripts; `lint` is the class-independent sweep. Two invocations, each
   target complete on its own.
3. **`Exec`/`TryExec` rule is stronger than "absolute or in requires".** The
   validator requires `basename(Exec argv[0]) ∈ requires` AND `TryExec` present and
   equal to that binary (the AD-10 table wording). An absolute override therefore
   still declares the name layer 2 resolves (`code`, not `/usr/bin/code`).
4. **`optional` carries a real instance.** The plan names only the required list;
   `codex`/`copilot` are declared `optional` (the payload a kitty wrapper runs), so
   the "missing optional is skipped" path has a live case and is tested.
5. **`validate-catalog.py` reads YAML contracts.** Declaring `desktop/desktop.yaml`
   as the class schema made the JSON-only schema reader wrong; it now parses JSON
   or YAML through one strict subset (sequence-of-mappings items added).
6. **Layer-3 negative locks run `verify` from the desktop block
   (`--start-at-task`).** The synthetic-machine fixture's earlier cli-tools tail is
   broken on master (see above); starting at the layer-3 block executes the real
   tasks, and the clean run is asserted first in the same test.
7. **`docs/Adding an Icon — …` pin table was stale at `v0.2.0`.** Updated to
   `v0.5.0` and extended with the desktop rows (the slice's "docs pin table").
8. **`VM PLANNED — not run`** (per the slice instruction): `dev/vm-fresh.sh &&
   dev/vm-verify` needs incus and was not executed.

## MISSING / not done

- `dev/vm-verify` (PLANNED) — no disposable target was provisioned, so the
  end-to-end claim (entries in `$XDG_DATA_HOME/applications`, 0755 helper on PATH,
  keybind assertions on a fresh host) is **not** proven by execution in this slice.
- `TestVerifyRuntime` cannot run end-to-end here (pre-existing fixture gap, not
  introduced or fixed by S4).
- S5 (schema support window), S6 (engine extraction) and S7 (closeout) remain.
