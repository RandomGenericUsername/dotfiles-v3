# Guide — AGS app repo topology (DECIDED 2026-10-16)

> **DECIDED 2026-10-16 (lane-4 advisory).** Topology is **three repos**:
> `contracts → ags-platform → ags-apps` (monorepo, bar-first). Per-app repos are
> **deferred** until the exit gate below. Design of record stays
> `docs/101-ags-platform-architecture.md` §3 + `ARCHITECTURE-SPINE.md` (AD-1/17/20);
> this guide and `docs/HANDOFF-ags-platform.md` §2 are pointers, not competing sources.
>
> **Update 2026-10-28 — the split is complete.** The `ags-apps` EPIC-002 /
> REQ-008 architecture (AD-25/31/32) moved all seven apps to standalone repos;
> engine `v0.1.22` retires the monorepo role and installs them from
> `dotfiles/provisioning/apps.yaml`. The composition side (single app list, one
> program tuple, one-owner gate) is recorded in
> [`102-ags-app-consumption.md`](./102-ags-app-consumption.md). Only external
> publish/archive and host apply remain; §7 below is the historical decision
> that the pilot gate superseded.
>
> Original discussion framing is preserved below for provenance. Only §1 + §7 are normative.

## 0. Why this guide exists

The AGS platform work reached a fork. `ags-platform` (the reusable ports/adapters utils) is
extracted, published (`v0.1.0`, public), and consumed by the bar. The **next** question — how the
GUI apps split into repos — was answered *provisionally* as "one `ags-apps` repo that holds them
all" (`docs/HANDOFF-ags-platform.md` §2/§4). The maintainer's actual intent is **one repo per app**
— each app a standalone unit (e.g. the clipboard manager on its own), consuming `ags-platform`,
consumed by `dotfiles`. This guide exists so that intent is refined properly instead of being
decided inline.

## 1. Fixed inputs (settled — not under discussion)

- **`ags-platform` is a separate repo**: the reusable utils (ports + shared adapters + the event
  client), versioned, consumable by any AGS project.
- **Dependency direction:** apps → platform only; **never app → app.**
- **`contracts` is a repo** (two consumers: the Python runtime + the platform).
- **The manner:** BMad-validate before building; worktree-per-change (`.worktrees/<id>/`); gates
  green; honest gap-reporting.

## 2. The proposal on the table

**One repo per app.** Each app becomes a standalone AGS app that:

- **consumes `ags-platform`** — its seams (icons, events, preferences, notifier, theme) are the
  platform's, not local copies;
- **is consumed by `dotfiles`** — installed as one unit (clone at a pinned tag, like `ags-platform`);
- **never imports another app.**

Candidate repos: `bar`, `notifications`, `capture-tool`, `hypr-pano` (the clipboard manager),
`wallpaper-selector`, `icme` (icon-color-mapping-editor), `btop-theme-studio`.

## 3. Tensions to weigh (options, not conclusions)

- **Repo count vs the multi-repo / version-skew tax.** `docs/101` §3.1 warns that per-app repos
  *"pay the multi-repo/version-skew tax before it is earned."* Counter-argument to test: now that
  `ags-platform` freezes the interface, the tax may be lower — and each app may genuinely have an
  independent lifecycle.
- **Shared harness per repo.** Each repo would carry the arm-stm-env harness (AGENTS.md, tickets,
  openspec, guard). Cost of maintenance vs consistency.
- **Per-repo CI + releases/tags.**
- **Consumption in `dotfiles`:** install *N* units + shortcuts vs one.
- **The bar:** first mover / reference app? does it stay in `dotfiles` longer?
- **Ordering**, and the endgame ("delete redundant code").

## 4. Open questions (discussion prompts)

- Does each app have an **independent lifecycle** (released/pinned separately), or are they
  released together? If together, one repo may be simpler.
- Is the **skew tax** acceptable now that the platform interface is frozen?
- **Minimal viable split:** one repo first (the bar) and per-app later, or one-per-app immediately?
- **Who consumes each app** — only `dotfiles`, or others too?
- How does `dotfiles` **install N app repos** — a manifest, a script, a meta-package?
- Does the **bar** move first (reference), or the **clipboard manager** (simplest)?
- What **stays in `dotfiles`** (the Python runtime, provisioning, CLI tools csg/weg/itr) vs moves out?

## 5. References

- `docs/101-ags-platform-architecture.md` §3 — topology + the dependency-direction rationale.
- `docs/HANDOFF-ags-platform.md` §2/§4 — the decided three-repo plan; the in-place-first and
  skew-tax cautions.
- `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/ARCHITECTURE-SPINE.md`
  — AD-1 (dependency direction), AD-17 (distribution), AD-20 (sequencing); the Deferred list.
- The per-repo ticket backlogs (`ags-apps/tickets/`, and each new repo's `tickets/`).

## 6. How the refinement ran (done 2026-10-16)

1. ~~Fresh session~~ — done; read this guide + refs in `ticket/apptopo-3repo-bar-first`.
2. ~~Run `bmad-architecture` lane-4 pressure-test~~ — done (advisory, no auto-execute).
   Outcome: 101 §3.1 skew-tax warning holds; freeze does not erase it yet.
3. ~~Refine → decide~~ — done; see §7 below.
4. Next: plan it (OpenSpec changes + tickets) and execute — worktree-per-change, gates green.

## 7. Decision (2026-10-16 — normative)

- **Stay at 3 repos now.** `ags-apps` holds all apps as folders (`bar/`,
  `notifications/`, `capture-tool/`, `hypr-pano/`, `wallpaper-selector/`, `icme/`,
  `btop-theme-studio/`). Rule AD-1 holds: apps → platform only.
- **Bar first.** `ags-apps` starts with the bar as reference; migrate remaining apps one
  at a time; delete redundant code last (`HANDOFF` §4.3).
- **Why not 7 now:** 7× harness/CI/release cost with no CI template or repo-creation
  script yet; platform surface not frozen (AD-6 codegen, AD-21 single manifest, AD-17
  package boundary open); `dotfiles` N-unit install/rollback unsolved.
- **Exit gate for a future per-app split:** AD-6 + AD-17 + AD-21 closed, `ags-bar-validate`
  green in provisioning, and one pilot (candidate: `hypr-pano`, simplest) proves the
  harness/install cost. Until then, independent lifecycles alone do not earn the tax.
