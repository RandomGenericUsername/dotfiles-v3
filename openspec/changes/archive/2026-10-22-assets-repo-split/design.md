# Design — assets-repo-split

## Context

See `proposal.md` — Why. The design is the migration mechanics for the spine at
`_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/ARCHITECTURE-SPINE.md`
(AD-1…AD-17), with the executable step list in `SLICES.md` and the evidence
pointers in `EVIDENCE-INDEX.md`.

Three facts shaped every choice:

1. **The corpus is data.** No consumer imports it; roles copy/render from
   `<install>/assets/<tag>/` and the runtime reads only the spine. So the split
   changes provenance and addressing, not file formats or destinations (AD-7).
2. **The engine is a program with an Ansible tree beside its package.** Its
   wheel packages `src/provisioning` only, so a `git+…@tag` tool install would
   have no `ansible/` at run time. The pinned **checkout** is the installable
   form today (R-15).
3. **The composition repo's remaining job is pins + runtime + gates.** Every
   smuggled copy is a second source of truth, so the end state needs absence
   gates, not conventions (AD-16/AD-17).

## Goals / Non-Goals

**Goals**

- One corpus, one tag, five classes; fetch once, deploy per class.
- Every destination path and every rendered value identical to the pre-split
  deploy — the split moves the source only.
- The installer engine consumed as one semver pin, with the composition seam
  explicit and no repo-relative derivation.
- A composition repo whose pin set is validated as a set and whose tree is
  allowlisted, so a returning corpus/engine copy fails a gate.

**Non-Goals**

- No new runtime features; no CLI/library re-extraction (done in
  `cli-tools-repos`).
- No PyPI/registry; no image publication.
- No VM end-to-end run here (R-10); no rewrite of history (AD-15).

## Decisions

### D1 — Five entities, one-way graph, no cycles (AD-1)

`dotfiles-v3` (composition) → `dotfiles-assets` (data) and
`dotfiles-provision` (engine); the engine → the pinned CLIs/assets; the runtime
→ the spine only. No repo imports another repo's Python; the only cross-repo
runtime edge is `subprocess` + artifacts (unchanged).

### D2 — The assets repo is data-only (AD-2, AD-11)

No `pyproject.toml` package, no console script, no engine, no generated
artifacts. A generated file (`icons/mappings/icons.json`) fails `validate`. This
is what makes "the tag is the corpus" true: there is nothing to execute.

### D3 — One tag is the deployment pin; schemas version separately (AD-3, AD-4, AD-12)

The repo tag (`vX.Y.Z`) names a corpus snapshot. Each schema-bearing class
carries its own `schema_major`; consumers declare a support window
(`assets_schema_support`), assert it at fetch and at verify, and refuse a corpus
outside it. A schema change does not force a repo-tag MAJOR, and a docs-only
change forces a PATCH tag (never a moved tag).

### D4 — Fetch once, deploy per class (AD-5, AD-6)

`assets` clones `repo@tag` once into `<install>/assets/<tag>/`, drops `.git`,
writes `<install>/assets/pinned`. Every other role reads a class from that
checkout. The manifest is authoritative for repo/tag/class map; role + verify +
per-consumer mirrors are parity-locked.

### D5 — The split moves the source, never the destination (AD-7)

Every `dest`, `mode`, `become` and supplied var is unchanged. S2/S3 prove the
static files byte-identical before the in-tree copy is deleted; S4 proves the
desktop deploy through the contract layer. The runtime's teardown/rebuild
behaviour is untouched.

### D6 — Templates ship with their schema, never their values (AD-8, AD-9)

The corpus ships the Jinja source + `*.vars.schema.json`; the role supplies the
values. A required var that the render task does not supply fails the parity
test. Display-manager templates are corpus; DM type/packages/enablement stay in
the engine.

### D7 — Desktop validation is three layers (AD-10)

Corpus `validate-desktop` (entry shape, `TryExec`, script shellcheck) → role
resolves `desktop.yaml`'s `requires`/`optional` **before** the copy (a missing
required binary fails naming entry+binary) → `verify` re-asserts the deployed
set and resolves every `Exec` on PATH. A dead menu entry is a gate failure, not
a surprise.

### D8 — The runtime consumes only the spine (AD-13)

`src/runtime` may resolve inputs from the install spine, env overrides or its own
package defaults — never a repo checkout. This is why the runtime needed no
behavioural change; only its corpus inputs' provenance moved.

### D9 — Destructive-last, one class at a time (AD-16)

Per class: import byte-identically → pin + mirrors → prove (`gates-ci`,
`deploy-coverage`, runtime tests) → delete the in-tree copy **and** the guard in
the same slice → merge. Rollback = pin bump + revert of the deletion commit; a
published tag is never moved.

### D10 — The engine is a pinned repo with an explicit seam (AD-17)

`installer.pin` is the one source; `bootstrap.sh` reads it (never repeats the
tag) and installs the pinned checkout editable because the wheel lacks
`ansible/`. The engine exposes `--manifests-dir`, `--composition-root` and
`--inventory`; no YAML value or Jinja template derives from `playbook_dir`.
Composition gates read `.dev/dotfiles-provision-<tag>/` and fail loudly when it
is absent (R-16).

### D11 — The closeout validates the pin SET, not each pin in isolation (S7)

`deploy-coverage`'s `assert_pin_set` reads the declared file and then every
mirror, so a half-bump fails naming the mirror. `assert_composition_only`
allowlists `src/` (`runtime/`) and `dotfiles/` (`config/` + `provisioning/`),
and asserts the retired roots absent. This is the executable form of AD-17.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| A half-bumped pin deploys a mismatched corpus | Manifest ↔ role/verify/per-consumer mirrors are parity-locked; `assert_pin_set` covers installer/CLI/lib pins |
| The wheel cannot be installed standalone | Documented (R-15); bootstrap installs the pinned checkout editable; closure = ship `ansible/` in the wheel |
| Composition gates need network on a cold checkout | Loud offline failure naming pin+cache (R-16); pre-populate `.dev/dotfiles-provision-<tag>/` |
| `verify` cannot prove which engine ran | R-17: planned extra-var + `dotfiles-provision version` assertion |
| An empty leftover tree becomes a new home | Absence guards read the filesystem, not `git ls-files` (the cli-tools merge lesson); `assert_composition_only` sweeps parents |
| VM end-to-end never run | R-10 OPEN-BLOCKED (`incus` absent); every slice states the planned gate |

## Migration Order

`S0` birth (assets `v0.1.0`) → `S1` icons+content (`v0.2.0`) → `S2` configs
(`v0.3.0`) → `S3` templates (`v0.4.0`) → `S4` desktop (`v0.5.0`) → `S5` schema
window → `S6` engine extraction (`dotfiles-provision v0.1.0`) → `S7` closeout.
No slice starts before its predecessor merged.

## Rollback

Per slice: revert the deletion commit and move the pin back (or remove it). The
corpus tags are additive and immutable; `master` remains provisionable at every
merge point. The S7 metadata/gates are additive and revert cleanly.
