# SKIN-PLANE-V3 — generations v3 (epic)

> **id:** `SKIN-PLANE-V3`
> **kind:** epic (container; the RFC ticket `SKIN-PLANE-V3` / slug
> `generations-v3-rfc` carries the design)
> **status:** **planned** (design only, 2026-11-06)
> **design:** [`docs/107-generations-v3.md`](../107-generations-v3.md)
> **predecessor:** [`docs/105-appearance-plane-v2.md`](../105-appearance-plane-v2.md)
> **ticket:** worktree `.worktrees/SKIN-PLANE-V3/`, branch
> `ticket/SKIN-PLANE-V3-generations-v3-rfc`
> **pins:** none — this epic plans the work and changes no composition pin,
> app tag or runtime pin.

This epic replaces the v2 *multi-pointer* and *two-pipeline* mechanics with a
single committed generation and one convergence function. It keeps the v2
artifact boundary: appearance is palette + skin + mode, one composed sheet, one
provider per app, one monitored state hop. It removes the remaining ways a
consumer can see two generations or an ack can lie about what was applied.

The live findings that force this epic are in the RFC:

- `current/` is a set of independently repointed palette/icons/effects/skins/
  appearance links, so a reader can mix generation N and N+1.
- the daemon and the CLI both mutate state through different compositions;
  `reconcile --regenerate-stale` can return rc=0 without applying a mode change.
- the refresh ack is `{"ok":true}` with no generation; an app can answer success
  for a hash it never applied.
- the runtime writes `appearance.css` through `config/<app>` into an immutable
  app tag (AD-37).
- lock/name readiness is sometimes a sleep loop rather than an event.
- lane policy is split between `launch`, app-manifest `mode`, and unit
  supervision.

## Frozen decisions (summary)

1. Generation is the unit; one `state/current -> generations/<genHash>` commit
   pointer, one atomic rename.
2. One `converge(intent) -> generation` used by daemon, CLI and all intent
   changes; daemon job queue with the same function + same lock as fallback.
3. Generation-bound refresh request/ack; `{"applied":"<genHash>"}` only.
4. Runtime writes only under state; never under `<install>/apps/<tag>`.
5. Event-driven readiness only; no polling as correctness.
6. Each app declares `live` or `restart`; exactly one is enforced.
7. Mode is a generation input; a mode change is an ordinary generation change.
8. No workarounds: no second pointer, no second pipeline, no boolean ack.

The full rationale, layout, manifest, transaction, crash matrix and tests are
in [`docs/107`](../107-generations-v3.md).

## Child workstreams (planned)

| Repo | Child | Scope | Acceptance criteria | Status |
| --- | --- | --- | --- | --- |
| `contracts` | Generation + refresh v3 contract | `schemaVersion: 3` manifest and `genHash` identity; generation-bound request/ack; `refresh`/`supervision` vocabulary; retire `{"ok":true}` as applied | Schemas validate a manifest and reject a v3 generation without `genHash`; a refresh ack without the requested `genHash` is invalid; exactly one `refresh` value is enforceable; conformance fixtures cover live/restart and unit/launcher | planned |
| `dotfiles-runtime` | Generation store + one convergence | Content-addressed layers -> `generations/<genHash>`; one commit rename; `converge(intent)`; daemon converge job queue; fallback lock; mode as input; GC; event-driven readiness | Concurrency and crash-injection tests from RFC A-1/A-2/A-7; one mutation path; mode change works without `wallpaper set`; no `.seed.lock`/appearance lock split; no runtime write outside state | planned |
| `ags-platform` | Generation-bound consumer | Apply/ack keyed by `genHash`; read `state/current/appearance/<configDir>.css`; watch `current`; D-Bus `NameOwnerChanged` registration | Stale/missing generation answers deferred and never applies; one provider, USER priority, last; no config/tag read path; registration success comes from the bus event | planned |
| `dotfiles-provision` | State and stable links | State directories; provisioning-owned stable links for non-runtime consumers; mirror `refresh`/`supervision`; verify immutability | No runtime artifact inside any app tag; every stable link resolves through `current`; verify fails when a runtime file is planted in a tag; app-list lane fields validated | planned |
| `ags-bar` | Restart lane | Keep no appearance refresh handler; restart through systemd when unit-managed; declare `refresh: restart`, `supervision: unit` | Appearance change restarts once, one instance, no duplicate; no live fallback; no post-appearance provider | planned |
| `ags-notifications` | Live lane | Generation-bound handler; preserve open cards/daemon/bus; declare `refresh: live`, `supervision: unit` | `{"applied":"<genHash>"}` only after the requested generation is installed; pid unchanged; open cards preserved; unit supervision unaffected | planned |
| `ags-capture-tool` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; no restart; launch policy unchanged | planned |
| `ags-clipboard` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; token ink preserved; no luminance math; no restart | planned |
| `ags-wallpaper-selector` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; layout default preserved; no restart | planned |
| `ags-icme` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Unsaved-state rule preserved; requested generation applied or deferred, never discarded; no restart | planned |
| `ags-btop-theme-studio` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Unsaved-state rule preserved; requested generation applied or deferred, never discarded; no restart | planned |
| `dotfiles-v3` | Composition cutover | Consume the wave tags in a separate cutover; docs 106 live; gates | `make ci-gates-parity` + `make deploy-coverage` green; the RFC A-1…A-10 suite run against the tuple; no pin before the cutover ticket | planned |

`launch` (`always|on-demand`) remains a composition app-list field. It is not
the refresh lane. `supervision` says how a restart is performed; `refresh` says
whether a restart is the lane.

## Migration waves

| Wave | Repo | Depends on | Done when |
| --- | --- | --- | --- |
| 0 | `contracts` | — | Generation/refresh v3 schemas and conformance fixtures released |
| 1 | `dotfiles-runtime` | 0 | One `converge`, one commit pointer, job queue + fallback, GC, mode input; v2 read compatibility only |
| 2 | `ags-platform` | 0 | Generation-bound apply/ack and state-only read/watch path |
| 3 | seven apps | 0, 2 | Each app's lane declared and conformance green |
| 4 | `dotfiles-provision` | 0, 3 | Immutability + stable-link verify green |
| 5 | `dotfiles-v3` | 1–4 | Cutover tuple/app pins + docs 106 live + gates |
| 6 | all | 5 | Legacy v2 pointer family, old locks and convenience links removed |

Waves may overlap only in their own repos; the composition consumes released
tags in wave 5, never a floating branch.

## Acceptance (epic-level, planned)

- [ ] All ten RFC acceptance tests (A-1…A-10) pass against the cutover tuple.
- [ ] A consumer never sees palette N with appearance N+1 (or any other
      cross-generation pair).
- [ ] One converge mutates one generation; a stopped daemon uses the same
      function under the same lock; concurrent daemon + CLI has exactly one
      commit.
- [ ] A stale or forged ack is never recorded as `applied`.
- [ ] No runtime file exists inside any `<install>/apps/<installDir>/<tag>/`.
- [ ] A mode change with all apps open converges without `wallpaper set` and
      without a restart of live apps.
- [ ] Lane policy is one declared value per app; unit-managed changes only the
      restart mechanism.
- [ ] No sleep/name poll is a success condition; registration/restart success
      comes from the bus/systemd event.
- [ ] GC keeps active, newest, pinned and ledger-referenced generations and
      removes only unreferenced entries older than grace.
- [ ] No composition pin, app tag or runtime pin changes before wave 5.

## Non-goals

- No structure tokens or layout trees; appearance remains palette + skin +
  mode, and structure stays app-owned.
- No new app list, no per-file GUI list, no in-repo runtime/app/engine source.
- No live host deploy in this epic; the cutover remains a composition pin bump
  and the operator's normal bootstrap/provision.
- No v2 hotfix branch: v3 is the replacement, not a patch of the multi-pointer
  family.
