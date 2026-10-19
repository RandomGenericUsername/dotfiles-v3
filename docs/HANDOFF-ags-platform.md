# HANDOFF — AGS Platform Split (roadmap + manner + environment)

> Read `docs/101-ags-platform-architecture.md` first — it is the design of
> record. This file is the **plan**, the **working manner**, the **harness
> record**, and the **environment facts** the next session would otherwise have
> to rediscover. Written 2026-10-09.

---

## 0. Where we are

- **Design of record:** `docs/101-ags-platform-architecture.md`.
- **`master` is the single source of truth.** The bar descriptor prototype, the
  kit-gap fixes, `docs/100`/`101`, and both handoffs were merged from
  `bar-rearchitecture` (merge commit `a64c287e`) and **pushed to `origin/master`**.
- `master` is checked out at `/home/inumaki/Development/dotfiles-v3` (in sync
  with `origin/master`).
- **The AGS apps migration is complete (2026-10-19).** All seven apps live in
  `ags-apps` and `dotfiles-v3` consumes it as one pinned unit (`v0.3.8`); see
  §2.1 and §5.1. Remaining work is *not* migration: the per-app repo split
  (deferred, §2), the `ags-apps` ticket roll-up (§5.1), and the "Still to
  define" items in §7.
- **The three split repos EXIST** (private, scaffolded, pushed — see §7).
- `bar-rearchitecture` is **fully merged** (safe to delete).

---

## 1. Environment / auth (so the next session does not rediscover this)

- **`gh`** installed at `~/.local/bin/gh` (v2.102.0), authenticated as
  `RandomGenericUsername`. Token scopes: `repo`, `admin:public_key`, `gist`,
  `read:org`. **Repo creation works via `gh repo create`.**
- **Git uses HTTPS + the `gh` credential helper** (`gh auth setup-git`;
  `gh config set -h github.com git_protocol https`). The helper is the absolute
  path `/home/inumaki/.local/bin/gh`, so it works in agent shells with no `PATH`.
  **No SSH agent / passphrase needed** — agents can push.
- `origin` = `https://github.com/RandomGenericUsername/dotfiles-v3.git`.
- The user's `~/.ssh/personal` key is passphrase-protected and was left unused;
  SSH is **not** the chosen path.
- **OpenSpec CLI** installed: `@fission-ai/openspec` **1.14.1** at
  `~/.local/bin/openspec` (user-level npm install, no sudo). `openspec list
  --json` confirms each repo root.
- Present on host: `uv` 0.9.22, Python 3.14, Node 26, `gh` 2.102.0.
- **`dotfiles-v3` uses git worktrees** (run `git worktree list`). `master` lives
  at `/home/inumaki/Development/dotfiles-v3`; other branches live in sibling
  worktrees.

---

## 2. The goal

> **Topology decided (2026-10-16).** Three repos: `contracts → ags-platform → ags-apps`
> (monorepo, bar-first). Per-app repos deferred until the exit gate in
> `docs/GUIDE-ags-app-repos-refinement.md` §7. Design of record:
> `docs/101-ags-platform-architecture.md` §3 + `ARCHITECTURE-SPINE.md` AD-1/17/20.
> The settled inputs still hold: `ags-platform` is a separate
> repo; apps → platform only, never app → app.
>
> **State (2026-10-19): the migration is DONE.** `ags-apps` holds **all seven
> apps** (`bar/`, `hypr-pano/`, `notifications/`, `capture-tool/`,
> `wallpaper-selector/`, `icme/`, `btop-theme-studio/`) and `dotfiles-v3`
> consumes the whole monorepo as **one pinned unit**. Current pins:
> `ags-platform` **v0.2.0**, `ags-apps` **v0.3.8**. **Per-app repos remain
> deferred** — the GUIDE §7 exit gate (AD-6 + AD-17 + AD-21 closed,
> `ags-bar-validate` green in provisioning, one pilot proving the
> harness/install cost) is **still unmet**; the pilot half is evidenced, the
> three ADs are not closed. Details + evidence below and in
> `docs/LESSONS-ags-apps-migration.md`.

Split AGS into **three repos**, with apps depending on the platform only:

```
contracts  →  ags-platform  →  ags-apps
```

- `contracts`: event contract (`JSON`/`XML`) + generated bindings; consumed by
  the **Python runtime** and `ags-platform`.
- `ags-platform`: ports + shared adapters (icons, events, preferences,
  notifier) + the event-contract client.
- `ags-apps`: the AGS apps (bar, notifications, capture-tool, hypr-pano,
  wallpaper-selector, icon-color-mapping-editor (`icme`), btop-theme-studio).
- **Rule:** apps → platform only; never app → app.

### 2.1 Pins and tag scheme (as consumed by `dotfiles-v3`)

| Unit | Pin | Where | Evidence |
|---|---|---|---|
| `ags-platform` | **v0.2.0** | `src/provisioning/ansible/roles/ags_platform/vars/main.yml:32` | `ags_platform_version: v0.2.0`; mirror `verify/vars/main.yml:473` |
| `ags-apps` | **v0.3.8** | `src/provisioning/ansible/roles/ags_apps/vars/main.yml:99` | `ags_apps_version: v0.3.8`; mirror `verify/vars/main.yml:509` |
| `contracts` | unchanged | consumed via `ags-platform` | not re-pinned in this migration |

- **Tag scheme:** the monorepo releases `vX.Y.Z` (`v0.2.0` → `v0.3.8`, 2026-10-17
  → 2026-10-19). `bar-v0.1.0` / `bar-v0.1.1` are **historical** pre-monorepo bar
  tags (2026-10-16) kept for the record — they pinned a repo that held the bar
  only. Do **not** mint new `bar-v*` tags: from `v0.2.0` on, a tag covers the
  whole unit (all seven apps), and the pin bump is the release act.
- Tag → commit map (dereferenced, `git rev-list -n1 <tag>`): `bar-v0.1.0`
  `8a7ea203`, `bar-v0.1.1` `182ed869`, `v0.2.0` `869068e1`, `v0.3.0`
  `88dce7d9`, `v0.3.1` `f01e7dc3`, `v0.3.2` `d661b3cb`, `v0.3.3` `0cfccf3f`,
  `v0.3.4` `7431e29d`, `v0.3.5` `e7bc54b2`, `v0.3.6` `e09e13d4`, `v0.3.7`
  `01866d5f`, `v0.3.8` `c6f09e5c`.
- **Pin ladder in `dotfiles-v3`** (`git show <merge>:…/ags_apps/vars/main.yml`):
  `16a9266e` bar-v0.1.0 → `c9701f8c` bar-v0.1.1 → `ffb6e142` v0.2.0 →
  `8269f876` v0.3.0 → `c406a28e` v0.3.1 → `7c879d22` v0.3.2 → `39e79f84`
  v0.3.3 → `b99a32a9` v0.3.4 → `66fb2adb` v0.3.5 → `d1b3b8af` v0.3.6 →
  `82adb150` v0.3.7 → `3a8bcb84` v0.3.8.
- **One unit, seven links:** `verify` asserts a live link per app, all against
  `verify_ags_apps_version` — `verify/tasks/main.yml:1023` (bar), `:1071`
  (hypr-pano), `:1115` (notifications), `:1160` (capture), `:1204`
  (wallpaper-selector), `:1250` (icme), `:1296` (btop-studio).

---

## 3. How we work here (the manner) — read before starting

- **Iterate this with the BMad architect; validate everything before building.**
  Drive the rework through the BMad **architecture** skill (`bmad-architecture`)
  — and route the work via `/triage` (lane 4 = bmad-advisory) — so the design of
  record and **each iteration are validated before implementation**. Do not
  free-hand the extraction: have the architect validate `docs/101` and the plan
  for every step, then implement. BMad advises; it never auto-executes.
- **Never work on main.** Work on a **branch + worktree off `master`** (use
  `git worktree add`; `dotfiles-v3` already does this). Merge back only when the
  gates are green. The three new repos carry `scripts/worktree-guard.sh` and the
  same no-main rule.
- **Granular, independently shippable steps.** No big-bang: each iteration is
  small, gated, and committable on its own; each leaves the tree green.
- **Verified by execution, not by reading diffs.** Run the gates; where it
  matters (the bar), deploy to the host and eyeball.
- **Honest gap-reporting** over silent fixes. If evidence is missing, say so.
- **Separate planning from implementation** (the OpenSpec/BMad planning boundary):
  planning edits land in their own turn, code in another.

---

## 4. Key adjustments to the naive "3 parallel repos" plan

1. **The repos are a dependency chain, not independent.** Parallel *authoring*
   is fine **against a frozen interface** (doc 101). Integration must be
   **sequenced**: contracts → platform → apps. One integration owner.
2. **Extract `ags-platform` IN-PLACE in `dotfiles-v3` first**, prove it with the
   existing gates (`bar-typecheck`, `ags-typecheck`, `ags-test`, `gates-ci`),
   **then** publish to the repo. Creating a repo from untested code is the risky
   path; the in-place extraction is also the "without deleting code" bridge.
3. **Thin slice first:** `ags-apps` starts with **the bar only**; migrate the
   other five apps one at a time. Otherwise the final "delete redundant code"
   touches six apps at once.
4. **The contract move ripples.** `contracts/event-contract.*` is consumed by
   the Python runtime and pinned by tests across components — it is a
   cross-cutting change with a repointing step, not a standalone repo task.
5. **Branch base — RESOLVED.** `bar-rearchitecture` was merged to `master`
   (merge `a64c287e`). All further work branches off `master`; the "consume
   external repos" branch must also sit on `master`.

---

## 5. Iteration list

| # | Iteration | Notes | Status (2026-10-19) |
|---|---|---|---|
| 0 | **Validate doc 101** (fresh BMad architect review) + decide deferred items (§6) | Test: *are the port signatures/schemas complete enough to implement against without the conversation?* | done |
| 1 | **Extract `ags-platform` in-place** in `dotfiles-v3` | New worktree/branch off `master`; all gates green. The risky part — do it where the tests are. | done (pin v0.2.0) |
| 2 | **`contracts` repo** | Move contract + bindings; repoint runtime + consumers. | done — sibling checkout (`CONTRACTS_REPO`), pin asserted by `contracts-check`, part of `gates-ci` (`Makefile:13`) |
| 3 | **`ags-platform` repo** | Publish the proven extracted package + CI. | done (pin v0.2.0) |
| 4 | **`ags-apps` repo** | Bar only. | **done** — `8a7ea20`, tag `bar-v0.1.0`; guards re-homed `182ed86` (`bar-v0.1.1`) |
| 5 | **Consumption branch** in `dotfiles-v3` | Install framework as one unit + `node_modules` shortcut; provision; user+agent test. | **done** — `16a9266e` (pin `bar-v0.1.0`), bridge retired `03272b60`/`415de57b` |
| 6 | **Migrate remaining apps**, one at a time | notifications, capture-tool, hypr-pano, wallpaper-selector, icme. | **done** — hypr-pano `v0.2.0`, notifications `v0.3.4`, capture-tool `v0.3.5`, wallpaper-selector `v0.3.6`, icme `v0.3.7`, btop-theme-studio `v0.3.8` |
| 7 | **Delete redundant code** | Only after 5/6 are green. | **done, but not as a separate change** — each app's in-repo source was deleted in its own consumption slice (see §5.1) |

Steps 2–4 may be **authored in parallel** (frozen interface); step 5 is a single
gate. The BMad architect validates steps 0 and 1; OpenSpec changes fit 2–4
(create/move).

### 5.1 Where the seven slices landed (evidence)

The plan is `openspec/changes/ags-apps-bar-first/tasks.md` — it lives **only** on
branch `ticket/appsplan-bar-first-proposal` (worktree `.worktrees/appsplan`),
never merged to `master`; the completion record was written there in place.

- **Consumption shape (one gate, all seven):** `make deploy-coverage` →
  **PASS, exit 0** in `.worktrees/migdone` at `3a8bcb84`:
  "per-file non-bar sources in the manifest: 0" and, per app, "external '<app>'
  app — pinned unit subdir + live-<app> link provisioned; no per-file gui_tools
  source remains".
- **`ags-apps` gates:** `make gates-ci` at `v0.3.8` (= `HEAD`, `git tag
  --points-at HEAD` → `v0.3.8`) → **exit 0**; the root target (`Makefile:890`)
  aggregates bar + all six apps' guards. Per-app typecheck targets exist for all
  seven (`Makefile:143, 234, 302, 409, 502, 581, 665`).
- **AD-1 holds at the end state:** `grep -rn "from ['\"]ags-platform"` per app →
  bar 45, hypr-pano 4, notifications 5, capture-tool 4, wallpaper-selector 5,
  icme 6, btop-theme-studio 2; cross-app imports (`from '<sibling>/'`) → **0**.
- **In-repo duplicates removed per slice:** `dtf:03272b60` (bar bridge),
  `f5cf4037` (hypr-pano), `71958a50` (capture GUI), `52654621`
  (wallpaper-selector), `66990194` (icme), `8d733b3f` (btop-theme-studio).
  `config/` no longer exists; `src/gui-tools/` is gone entirely — capture-tool's
  Python backend now ships in the unit too (`capture-tool/bin/`), installed by
  `cli_tools`.
- **Open bookkeeping gap:** the `ags-apps` ticket roll-up was never applied —
  `tickets/INDEX.md:11-16` still shows REQ-001…REQ-006 as `proposed` and
  REQ-007 as `in-progress` while every slice is merged and tagged.
- **Per-app repos:** still deferred (GUIDE §7 exit gate unmet, §2 above).

---

## 6. Deferred items to decide before/within step 0

From doc 101 §14:

- `contracts` repo promotion timing (now in scope).
- Notification cards as `SurfaceSpec` vs a separate concept.
- `ForeignCollectionSpec` final naming.
- Per-app repo split (deferred).
- `ags run` has no `--alias` → deployed install relies on the `node_modules`
  shortcut (verified).

---

## 7. Per-repo structure — DONE (the repos exist)

Investigating `/home/inumaki/Development/arm-stm-env` gave the harness. The three
repos now exist (private, HTTPS remotes, `main` pushed):

| Repo | URL | Purpose |
|---|---|---|
| `contracts` | https://github.com/RandomGenericUsername/contracts | event contract + generated bindings |
| `ags-platform` | https://github.com/RandomGenericUsername/ags-platform | ports + shared adapters + event-contract client |
| `ags-apps` | https://github.com/RandomGenericUsername/ags-apps | the AGS apps (bar first) |

Local checkouts: `/home/inumaki/Development/{contracts,ags-platform,ags-apps}`
(each an independent git repo, identity `Juan Tangarife
<juan.david@ubidots.com>`, first commit `chore: scaffold …`).

Each carries the **reusable harness** cloned from arm-stm-env (148 files):

```
AGENTS.md            # evidence rule + per-repo routing (§2/§3 rewritten per repo)
CLAUDE.md -> AGENTS.md
tickets/             # _template (epic|requirement|spike|task|bug|ops-task),
                     #   INDEX.md, LIFECYCLE.md (per-kind gates), _fixtures/router-lanes.md
openspec/            # config.yaml (context + rules) + governance specs
                     #   (task-router, ticket-system, worktree-discipline) + changes/
.agents/skills/      # vendored BMAD skills (bmad, bmad-build, bmad-architecture,
                     #   bmad-product-brief, bmad-spec, bmod-*)
.opencode/           # commands (triage, opsx-*) + openspec skills
_bmad/               # config.toml (per-repo project_name) + core-tools/method/scripts
scripts/worktree-guard.sh   # check-clean | create <id> <slug>
skills-lock.json  Makefile  README.md  .gitignore
```

- **The harness base is identical** across the three (the lean arm set). Only
  `AGENTS.md` §2, `openspec/config.yaml` `context`, and `README.md` differ per repo.
- **Harness matrix** (encoded as routing guidance in each `AGENTS.md` §3):
  `contracts` = core/spec only (schema repo); `ags-platform` = core + bmm;
  `ags-apps` = core + bmm (+ `tea` useful). To add a module later, run the `bmad`
  skill's setup in the repo.
- The repos are **empty scaffolds** — the code move (iterations 1–4) still follows.

### Harness source & mechanics

- **Template source:** `/home/inumaki/Development/arm-stm-env` — a lean, vendored
  BMad + OpenSpec + tickets install. The scaffold copied its generic layers
  (`.agents/`, `.opencode/`, `_bmad/`, `scripts/`, `skills-lock.json`,
  `tickets/{_template,_fixtures,LIFECYCLE.md}`, `openspec/specs/*`) and rewrote
  only the three per-repo files.
- **BMad is modular** (`core`, `bmm`, `bmb`, `cis`, `tea`, `bmad-loop`). arm
  installs a curated subset (`core` + the `bmm`-ish skills `bmad`, `bmad-build`,
  `bmad-architecture`, `bmad-product-brief`, `bmad-spec`); `dotfiles-v3` carries
  the full installer output. To add a module to a repo later, run the `bmad`
  skill's setup in that repo.
- **Skills fan out to IDE harness dirs** (`.opencode/`, `.agents/`, `.agent/`,
  `.codex/`, `.gemini/`, `.github/`, `.windsurf/`). The scaffold uses
  `.opencode` + `.agents` (like arm). `skills-lock.json` pins the vendored skills.
- **OpenSpec CLI** = npm `@fission-ai/openspec` (bin `openspec`).
- **The ticket system is bespoke** (`tickets/`), not an external tool: 6 kinds
  (`epic|requirement|spike|task|bug|ops-task`), `INDEX.md` rollup + counting rule,
  `LIFECYCLE.md` per-kind gates, `_fixtures/router-lanes.md`, and `/triage`
  routing (4 lanes).
- **The rules added to each repo** are exactly: `AGENTS.md` (evidence rule +
  routing), `openspec/config.yaml` (project context + per-artifact rules),
  `tickets/` (the whole system), `scripts/worktree-guard.sh` (no-main / dirty-main
  discipline), `.opencode/` + `.agents/` (skills), `_bmad/` (config + scripts),
  `skills-lock.json`, `Makefile`, `README.md`, `.gitignore`, and the `CLAUDE.md`
  symlink.

### Still to define

- **CI** per repo: `ags-apps` now has per-app workflows —
  `.github/workflows/{bar,hypr-pano,notifications,capture-tool,wallpaper-selector,icme,btop-theme-studio}.yml`
  (pure suites on `ubuntu-latest`, desktop-stack typechecks on
  `[self-hosted, linux]`). `contracts` / `ags-platform` CI status is
  **unverified here** (not inspected in this pass).
- Whether to **vendor BMAD skills per repo** (arm does) or rely on the host install.
- A **repo-creation script / template** so future repos reuse this exactly.

---

## 8. Pointers

- Design of record: `docs/101-ags-platform-architecture.md`.
- Migration lessons (colors.css seed, nested-worktree npm, re-homed test path
  math, AD-24): `docs/LESSONS-ags-apps-migration.md`.
- Migration plan/completion record: `openspec/changes/ags-apps-bar-first/tasks.md`
  (branch `ticket/appsplan-bar-first-proposal` only — not on `master`).
- Bar prototype + findings: `docs/100-ags-bar-rearchitecture.md`,
  `docs/HANDOFF-bar-rearchitecture.md`.
- Reference project for repo structure: `/home/inumaki/Development/arm-stm-env`.
- Verification commands: `make bar-typecheck`, `make ags-typecheck`,
  `make ags-test`, `make gates-ci`;
  `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py -q`.
