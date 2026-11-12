# SKIN-PLANE-V3 — generations v3 (epic)

> **id:** `SKIN-PLANE-V3`
> **kind:** epic (container; the RFC ticket `SKIN-PLANE-V3` / slug
> `generations-v3-rfc` carries the design)
> **status:** **delivered** (2026-11-08) — cut over live; see
> [Delivery evidence](#delivery-evidence)
> **design:** [`docs/107-generations-v3.md`](../107-generations-v3.md)
> **predecessor:** [`docs/105-appearance-plane-v2.md`](../105-appearance-plane-v2.md)
> **ticket:** worktree `.worktrees/SKIN-PLANE-V3/`, branch
> `ticket/SKIN-PLANE-V3-generations-v3-rfc`
> **delivered pins:** contracts `v0.12.0` · ags-platform `v1.1.0` ·
> dotfiles-runtime `v1.3.1` · dotfiles-assets `v0.17.0` ·
> dotfiles-provision `v0.1.60` · composition `v0.1.65` · apps bar `v0.6.1`,
> notifications `v0.5.1`, capture `v0.7.1`, clipboard `v0.6.1`,
> wallpaper-selector `v0.5.1`, icme `v0.5.1`, btop-theme-studio `v0.5.1`.
> **follow-on:** [`SKIN-CONSUMERS`](./SKIN-CONSUMERS.md) — non-AGS consumers
> (wlogout first) and Hyprland-sourced skin defaults; criteria in
> [`docs/108`](../108-non-ags-skin-consumers.md) and
> [`docs/109`](../109-hyprland-host-defaults.md).

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

Visual reference: [`docs/design/skins.html`](../design/skins.html) — a static
gallery of the four skins over one identical app structure.

## Child workstreams (delivered)

| Repo | Child | Scope | Acceptance criteria | Status |
| --- | --- | --- | --- | --- |
| `contracts` | Generation + refresh v3 contract | `schemaVersion: 3` manifest and `genHash` identity; generation-bound request/ack; `refresh`/`supervision` vocabulary; retire `{"ok":true}` as applied | Schemas validate a manifest and reject a v3 generation without `genHash`; a refresh ack without the requested `genHash` is invalid; exactly one `refresh` value is enforceable; conformance fixtures cover live/restart and unit/launcher | delivered |
| `dotfiles-runtime` | Generation store + one convergence | Content-addressed layers -> `generations/<genHash>`; one commit rename; `converge(intent)`; daemon converge job queue; fallback lock; mode as input; GC; event-driven readiness | Concurrency and crash-injection tests from RFC A-1/A-2/A-7; one mutation path; mode change works without `wallpaper set`; no `.seed.lock`/appearance lock split; no runtime write outside state | delivered |
| `ags-platform` | Generation-bound consumer | Apply/ack keyed by `genHash`; read `state/current/appearance/<configDir>.css`; watch `current`; D-Bus `NameOwnerChanged` registration | Stale/missing generation answers deferred and never applies; one provider, USER priority, last; no config/tag read path; registration success comes from the bus event | delivered |
| `dotfiles-provision` | State and stable links | State directories; provisioning-owned stable links for non-runtime consumers; mirror `refresh`/`supervision`; verify immutability | No runtime artifact inside any app tag; every stable link resolves through `current`; verify fails when a runtime file is planted in a tag; app-list lane fields validated | delivered |
| `ags-bar` | Restart lane | Keep no appearance refresh handler; restart through systemd when unit-managed; declare `refresh: restart`, `supervision: unit` | Appearance change restarts once, one instance, no duplicate; no live fallback; no post-appearance provider | delivered |
| `ags-notifications` | Live lane | Generation-bound handler; preserve open cards/daemon/bus; declare `refresh: live`, `supervision: unit` | `{"applied":"<genHash>"}` only after the requested generation is installed; pid unchanged; open cards preserved; unit supervision unaffected | delivered |
| `ags-capture-tool` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; no restart; launch policy unchanged | delivered |
| `ags-clipboard` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; token ink preserved; no luminance math; no restart | delivered |
| `ags-wallpaper-selector` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Requested generation applied; layout default preserved; no restart | delivered |
| `ags-icme` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Unsaved-state rule preserved; requested generation applied or deferred, never discarded; no restart | delivered |
| `ags-btop-theme-studio` | Live lane | Generation-bound handler; declare `refresh: live`, `supervision: launcher` | Unsaved-state rule preserved; requested generation applied or deferred, never discarded; no restart | delivered |
| `dotfiles-v3` | Composition cutover | Consume the wave tags in a separate cutover; docs 106 live; gates | `make ci-gates-parity` + `make deploy-coverage` green; the RFC A-1…A-10 suite run against the tuple; no pin before the cutover ticket | delivered |

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

## Acceptance (epic-level, delivered)

- [x] All ten RFC acceptance tests (A-1…A-10) pass against the cutover tuple.
- [x] A consumer never sees palette N with appearance N+1 (or any other
      cross-generation pair).
- [x] One converge mutates one generation; a stopped daemon uses the same
      function under the same lock; concurrent daemon + CLI has exactly one
      commit.
- [x] A stale or forged ack is never recorded as `applied`.
- [x] No runtime file exists inside any `<install>/apps/<installDir>/<tag>/`.
- [x] A mode change with all apps open converges without `wallpaper set` and
      without a restart of live apps.
- [x] Lane policy is one declared value per app; unit-managed changes only the
      restart mechanism.
- [x] No sleep/name poll is a success condition; registration/restart success
      comes from the bus/systemd event.
- [x] GC keeps active, newest, pinned and ledger-referenced generations and
      removes only unreferenced entries older than grace.
- [x] No composition pin, app tag or runtime pin changes before wave 5.

## Delivery evidence

Live cutover completed 2026-11-08:

- `state/current -> generations/43d62e17e2da58da2ea43da41bde41fb30e9d0077611a8c34fe30e8d50ef7fc8`,
  manifest `schemaVersion: 3`, `terminal` skin, `smart` intent → `dark`.
- `dotfiles-provision apply` → `failed=0`; `verify` → `ok=327 failed=0`,
  `failed=0`; `make deploy-coverage` PASS.
- `dotfiles-runtime doctor` → clean, 27 items, supervision `ok`; both
  always-on apps fresh (`stale_appearance=False`).
- App tags are immutable: recursive tag-file checksums unchanged across
  skin/mode changes; no runtime artifact remains in any tag; every stable
  consumer link resolves through `current/palette/`.
- Live lane proof with apps open: `terminal → flat`/`light` applied; bar
  restarted through systemd, notifications applied in-place with the same PID.
  Pure watcher-driven mode changes (`desired.json` only, no `wallpaper set`)
  converged end-to-end in ~18s (`light`) and ~47s (`smart`/dark) on the final
  v1.0.5 run, including generation commit, bar restart and ledger apply (the
  inotify debounce itself is 0.25s); ledger, history tail and manifest agreed;
  `doctor` clean and the current palette/wallpaper cache survived both GC
  cycles.
- Concurrency/crash invariants: two simultaneous `wallpaper set` runs both
  exited 0, left one `current`, zero `.staging-*` generations, one history
  tail, and a clean `doctor`.
- Child releases: contracts `v0.8.0`, ags-platform `v1.1.0`, runtime `v1.0.5`,
  assets `v0.13.0`, engine `v0.1.60`, composition `v0.1.65`; apps at the tags
  listed above.

## Non-goals

- No structure tokens or layout trees; appearance remains palette + skin +
  mode, and structure stays app-owned.
- No new app list, no per-file GUI list, no in-repo runtime/app/engine source.
- The cutover itself was an ordinary composition pin bump +
  bootstrap/provision on the live host (2026-11-08); it is not a second
  deployment mechanism.
- No v2 hotfix branch: v3 is the replacement, not a patch of the multi-pointer
  family.
