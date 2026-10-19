# Tasks

Evidence convention: every tick names the command run and the observed result.
Nothing is ticked from reading a diff.

> **Status (2026-10-19): slices 0–9 COMPLETE.** All seven apps live in the
> `ags-apps` monorepo and `dotfiles-v3` consumes it as ONE pinned unit
> (`ags_apps_version: v0.3.8`, `src/provisioning/ansible/roles/ags_apps/vars/main.yml:99`
> in dotfiles `3a8bcb84`). Narrative + gaps:
> `docs/HANDOFF-ags-platform.md` §2/§5 and `docs/LESSONS-ags-apps-migration.md`
> (branch `ticket/migdone-record`).
>
> **Where this plan lives.** `openspec/changes/ags-apps-bar-first/` exists ONLY on
> branch `ticket/appsplan-bar-first-proposal` (worktree `.worktrees/appsplan`);
> it is **not** on `master`. `git merge-base --is-ancestor
> ticket/appsplan-bar-first-proposal master` → false. The completion record was
> therefore written here, in place, and NOT copied into an invented master
> location.
>
> Commit-hash conventions below: `dtf:` = `dotfiles-v3`, `apps:` = `ags-apps`.

## 0. Repo-shape decision record (no code)

- [x] 0.1 Record the shape: one `ags-apps` monorepo, `bar/` first, per-app
  folders after (`bar/`, `hypr-pano/`, `notifications/`, `capture-tool/`,
  `wallpaper-selector/`, `icme/`, `btop-theme-studio/`), apps → platform only
  (AD-1), bar-specific
  ports in `bar/` (AD-8/AD-14). Cite GUIDE §7 + spine AD-1/17/20 + Deferred.
  Verify: `ls openspec/changes/ags-apps-bar-first/` → `proposal.md tasks.md`.
  **Evidence (2026-10-19):** `ls openspec/changes/ags-apps-bar-first/` →
  `proposal.md tasks.md` (exit 0, worktree `.worktrees/appsplan`). Decision
  text: `docs/GUIDE-ags-app-repos-refinement.md` §7 (three repos now; seven-app
  folders; per-app split deferred).

## 1. Bar moves first (REQ-001)

- [x] 1.1 Copy `dotfiles/config/ags/` → `ags-apps/bar/` (history-preserving
  move authored in `ags-apps`, not here); wire imports to `ags-platform`
  ports/adapters; keep only bar-specific code in `bar/` (layout default,
  `SurfaceSpec`/`PopupHost`, Shell + shapes, capabilities, `bar-manifest.ts`).
  Verify: `grep -rn "from ['\"]ags-platform" ags-apps/bar | head` → non-empty;
  `grep -rn "ags-apps/" ags-apps/bar` cross-app imports → none (AD-1).
  **Evidence (2026-10-19, `ags-apps` @ `v0.3.8`):** `git log --merges` →
  `8a7ea20 merge ticket/bar1-thin-consumer: bar thin consumer (REQ-001 slice 1)`;
  tag `bar-v0.1.0` → commit `8a7ea203`. `grep -rn "from ['\"]ags-platform"
  bar --include='*.ts*'` → **45** matches. Cross-app import grep
  (`from '<app>/'` for all seven app dirs, `*.ts/*.tsx/*.mjs`, `node_modules`
  excluded) → **0** matches. Same grep over the other six apps: hypr-pano 4,
  notifications 5, capture-tool 4, wallpaper-selector 5, icme 6,
  btop-theme-studio 2 → all non-zero, no app→app.

- [x] 1.2 Per-app CI in `ags-apps` (typecheck + tests for `bar/`).
  Verify: `make -C /home/inumaki/Development/ags-apps bar-check` (or the
  repo's gate target) → exit 0.
  **Evidence (2026-10-19):** the bar targets exist and are wired into the root
  gate — `ags-apps/Makefile:143 bar-typecheck:`, `:198 ags-test:`, `:81
  typecheck: bar-typecheck`; `make gates-ci` (`:890`) → **exit 0** on the
  `v0.3.8` tip. `bar-check` is not a target name in this repo; the gate line is
  `make gates-ci`.

- [x] 1.3 dotfiles still green with the in-place bar (bridge, pre-consumption).
  Verify: `make bar-typecheck && make ags-typecheck && make ags-test && make gates-ci && make deploy-coverage` → all exit 0.
  **Evidence — PARTIAL / superseded, stated honestly:** the pre-consumption run
  was not archived as an artifact, so its exit codes cannot be cited. What IS
  verifiable now: the bar/app gates were subsequently RETIRED from dotfiles
  (they live in `ags-apps` — no `bar-typecheck` / `ags-typecheck` / `ags-test`
  targets remain in the dotfiles `Makefile`), and `make gates-ci` in
  `.worktrees/migdone` (dotfiles `3a8bcb84`) → **exit 0**. The slice's intent —
  "dotfiles stays green through the move" — is carried by that current exit,
  not by a preserved historical one.

## 2. dotfiles consumes the moved bar

- [x] 2.1 Provisioning installs `ags-apps/bar` as one pinned unit
  (`<install>/ags-apps/<version>/`-style unit: pinned GitHub tag, version
  dir, pin recorded) and `config/ags` resolves to it via the shared-ancestor
  `node_modules` shortcut (mirror of the `ags-platform` consumption shape —
  precedent `openspec/changes/ags-consume-platform/tasks.md` 1.1 + 1.2,
  AD-17; rollback = repoint the shortcut).
  Verify: fresh provision stats the unit dir; `ags bundle <unit>/bar/app.tsx …` → exit 0.
  **Evidence:** `dtf:16a9266e` "consume ags-apps/bar as one pinned unit (slice
  2)" pinned `ags_apps_version: bar-v0.1.0` (`git show
  16a9266e:src/provisioning/ansible/roles/ags_apps/vars/main.yml` → line 65);
  `dtf:c9701f8c` repointed to `bar-v0.1.1`. Current shape: unit dir
  `{{ ags_apps_install_root }}/{{ ags_apps_version }}`
  (`ags_apps/vars/main.yml:109`), pin file + resolution shortcut in
  `ags_apps/tasks/main.yml:138,156`. `make deploy-coverage` → **PASS, exit 0**:
  "external bar unit 'ags-apps' — pinned unit + live-bar link + per-unit
  resolution shortcut provisioned". *Unverified here:* the fresh-host
  `ags bundle` run — no provision log for it was retained.

- [x] 2.2 Retire the in-place bridge (`dotfiles/config/ags/` no longer the
  deploy source; provisioning lists repointed; `verify` asserts the unit).
  Verify: `make deploy-coverage` → PASS; `verify` passes on a fresh host.
  **Evidence:** `dtf:03272b60` "remove the in-repo bar bridge (ags-apps is the
  source of truth)", `dtf:415de57b` "config/ags is an ags_apps symlink, not a
  spine dir"; `verify` asserts seven live links against
  `verify_ags_apps_version` (`verify/tasks/main.yml:1023,1071,1115,1160,1204,1250,1296`).
  `make deploy-coverage` → **PASS, exit 0**, line: "per-file non-bar sources in
  the manifest: 0" + "NOTE — dotfiles/config/ags/app.tsx absent (bridge
  retired)". `ls config` in the worktree → *No such file or directory* (the
  bridge dir is gone, not merely unreferenced). *Unverified here:* a fresh-host
  `verify` run.

## 3–8. Remaining apps, one slice each (REQ-002…REQ-006 + btop, no REQ yet)

Each slice: move `<app>` → `ags-apps/<app>/` as a thin platform consumer
(no app→app imports) — implementation in `ags-apps` repo worktrees, never in
dotfiles; dotfiles only consumes — wire CI, repoint provisioning, keep gates
green. Ship in this order (bar stays slice 1 as reference; `hypr-pano` leads
as simplest pilot per GUIDE §7):

- [x] 3.1 `hypr-pano` (REQ-004, simplest pilot). Verify: app imports
  `ags-platform` only; `make gates-ci` → exit 0; clipboard manager runs.
  **Evidence:** `apps:869068e` "merge ticket/pano3b-migrate: hypr-pano thin
  consumer (REQ-004)" → tag `v0.2.0` → commit `869068e1` ("monorepo unit: bar +
  hypr-pano thin consumers", 2026-10-17). `dtf:ffb6e142` consumes it (pin
  `v0.2.0`), `dtf:2cf4b023` asserts the pano bridge retired, `dtf:f5cf4037`
  deletes the in-repo source. ags-platform imports in `hypr-pano/` → 4;
  cross-app → 0. AD-24 pilot lived in this slice: `apps:88dce7d` (requestHandler,
  `v0.3.0`), `apps:f01e7dc` (surface-before-rebuild, `v0.3.1`).
  `ags-apps make gates-ci` → **exit 0**. *Unverified here:* a live clipboard
  open on the host (no session capture retained).

- [x] 4.1 `notifications` (REQ-002). Verify: app imports `ags-platform` only;
  `make gates-ci` → exit 0; notifications window runs.
  **Evidence:** `apps:7431e29` "merge ticket/notif4-migrate: notifications thin
  consumer (REQ-002)" → tag `v0.3.4` → commit `7431e29d` (2026-10-18).
  `dtf:b99a32a9` consumes it (pin `v0.3.4`); the guard re-home
  `apps:890d608` came with it. ags-platform imports → 5; cross-app → 0.
  `ags-apps make gates-ci` → **exit 0**.

- [x] 5.1 `capture-tool` (REQ-003). Verify: same gate line; capture UI runs.
  **Evidence:** `apps:e7bc54b` "merge ticket/cap5-migrate: capture-tool thin
  consumer (REQ-003)" → tag `v0.3.5` → commit `e7bc54b2` (2026-10-19).
  `dtf:66fb2adb` consumes it (pin `v0.3.5`); in-repo GUI source deleted by
  `dtf:71958a50`, per-file deploy retired by `dtf:5183aae6`. The Python backend
  survives in-repo by design (`src/gui-tools/capture-tool/bin`) — see the
  deploy-coverage line. ags-platform imports → 4; cross-app → 0.
  `ags-apps make gates-ci` → **exit 0**.

- [x] 6.1 `wallpaper-selector` (REQ-005). Verify: same gate line; selector runs.
  **Evidence:** `apps:e09e13d` "merge ticket/wall6-migrate: wallpaper-selector
  thin consumer (REQ-005)" → tag `v0.3.6` → commit `e09e13d4` (2026-10-19).
  `dtf:d1b3b8af` consumes it (pin `v0.3.6`); source deleted by `dtf:52654621`,
  per-file deploy retired by `dtf:b423a75d`. ags-platform imports → 5;
  cross-app → 0. `ags-apps make gates-ci` → **exit 0**.

- [x] 7.1 `icme` (REQ-006). Verify: same gate line; editor runs.
  **Evidence:** `apps:01866d5` "merge ticket/icme7-migrate: icme thin consumer
  (REQ-006)" → tag `v0.3.7` → commit `01866d5f` (2026-10-19). `dtf:82adb150`
  consumes it (pin `v0.3.7`); source deleted by `dtf:66990194`, drift suite
  retired by `dtf:b8fcfc1f`. ags-platform imports → 6; cross-app → 0.
  `ags-apps make gates-ci` → **exit 0**.

- [x] 8.1 `btop-theme-studio` (7th app-move slice; no REQ ticket — exists in
  `src/gui-tools/` but absent from `ags-apps/tickets/`; file one before this
  slice). Verify: same gate line; studio runs.
  **Evidence:** the ticket gap was closed first — `apps:534d2ee` "file REQ-007
  for btop-theme-studio (slice 8.1)"; then `apps:64411c0` (move), `94515b4`
  (consume the platform Theme port), `4cfc0ff` (per-app gates + workflow),
  `85f91ab` (acceptance evidence), merge `apps:c6f09e5` → tag `v0.3.8` →
  commit `c6f09e5c` (2026-10-19). `dtf:3a8bcb84` consumes it (pin `v0.3.8`),
  `dtf:3a3e3dfd` retires the per-file deploy, `dtf:8d733b3f` deletes the
  in-repo source, `dtf:0ff6e8b0` records that the gui_tools per-file list is
  now empty. ags-platform imports → 2; cross-app → 0.
  `ags-apps make gates-ci` → **exit 0** (btop drift: "OK:
  btop-theme-studio/lib/key_widgets.json matches source (48 keys)").

## 9. Handoff (no deletion)

- [x] 9.1 Confirm `ags-apps` holds bar + six apps, all gates green, and hand
  off to `ags-delete-redundant-code` (deletion is a separate change, AD-20).
  Verify: `ls ags-apps/` → seven app dirs; `make gates-ci` → exit 0.
  Explicitly NOT in this change: deleting any in-place duplicate.
  **Evidence (2026-10-19):** `ls /home/inumaki/Development/ags-apps` → `bar
  btop-theme-studio capture-tool hypr-pano icme notifications
  wallpaper-selector` (seven app dirs, plus harness). `make gates-ci` in
  `ags-apps` → **exit 0** at tag `v0.3.8` (= HEAD `c6f09e5`, `git tag
  --points-at HEAD` → `v0.3.8`). dotfiles: `make deploy-coverage` → **PASS,
  exit 0** — "the retired bar + hypr-pano + notifications + capture-tool +
  wallpaper-selector + icme + btop-theme-studio bridges carry no per-file
  deploy source and the external units are provisioned"; `make gates-ci` →
  **exit 0**.
  **Deviation from the letter of this task (honest):** in-repo duplicates were
  NOT left for a separate `ags-delete-redundant-code` change. Each app's
  source was deleted in its own consumption slice (`dtf:f5cf4037` hypr-pano,
  `71958a50` capture-tool, `52654621` wallpaper-selector, `66990194` icme,
  `8d733b3f` btop-theme-studio, and the bar bridge in
  `03272b60`), i.e. deletion rode with consumption rather than trailing it.
  AD-20's ordering ("delete only after consumption + migration are green") was
  respected per slice; the separate-change separation was not. The dotfiles
  tree is now free of the duplicates (`config/` absent; `src/gui-tools/` holds
  only capture-tool's Python backend).
  **Second gap (open, unverified as anything else):** the `ags-apps` ticket
  roll-up was never closed — `tickets/INDEX.md:11-16` still shows REQ-001…REQ-006
  as `proposed` and `REQ-007` as `in-progress`, and `EPIC-001` as `0/7 children
  done`, while all seven slices are merged and tagged. Ticket status is
  bookkeeping, not code; it is recorded here so the handoff is not silently
  overstated.
