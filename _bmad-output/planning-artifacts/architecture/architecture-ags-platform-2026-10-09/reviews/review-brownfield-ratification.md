# Brownfield Ratification Review — AGS Platform Spine

- **Lens:** brownfield ratification. Does the spine's account of the CURRENT code hold, and does it honestly separate target from current?
- **Subject:** `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/ARCHITECTURE-SPINE.md` (278 lines, status: draft)
- **Codebase:** `/home/inumaki/Development/dotfiles-v3` (working tree at review time)
- **Method:** every factual current-code claim was checked against the named files; counts were enumerated; target language was checked for being flagged as target.
- **Spine was not modified.**

---

## Verdict

**Ratification largely holds.** Of the ~30 distinct current-code claims checked, 26 are TRUE as written. The load-bearing claims — the seams, the AD-4 correction list, all three duplication counts, both deployment findings, the AGS pinning, and the absence of the `node_modules` shortcut — are all **accurate and honestly framed**. Two defects are worth fixing: one FALSE characterization (theme copies called "divergent") and one internal target contradiction (where the bar-specific ports live). The rest are low-severity completeness nuances.

---

## Findings

### F1 — `theme.ts` copies are called "divergent" but are byte-identical

- **Severity:** medium (false current-code claim; mischaracterizes the evidence)
- **Exact claim:** AD-13, line 136: *"Prevents: the three divergent `theme.ts` copies and direct `app.apply_css` calls."*
- **Evidence:**
  - `src/gui-tools/icon-color-mapping-editor/lib/theme.ts`
  - `src/gui-tools/notifications/lib/theme.ts`
  - `src/gui-tools/wallpaper-selector/lib/theme.ts`
  - `md5sum` of all three = `bc086bf2e60f324900a47cdcb945e708` (identical). Each is 25 lines. All three were introduced by the same commit `512cd5f9` (2026-09-23) and are unchanged as of the spine date (2026-10-09).
  - The "three copies" part is TRUE; the "divergent" part is FALSE. They are three *identical* copies — duplication without divergence.
- **Fix:** change "the three divergent `theme.ts` copies" → "the three byte-identical `theme.ts` copies" (or "three duplicated `theme.ts` copies"). The AD-13 conclusion (Theme should be a port) is unaffected; only the characterization is wrong.
- **Disposition:** **autofix** (one-word wording correction in the spine).

### F2 — Internal target contradiction: where the bar-specific ports live

- **Severity:** medium (coherence defect in a load-bearing packaging decision; not a current-code error)
- **Exact claim(s):**
  - Design Paradigm table, line 34 (row "ports", lives in `ags-platform/ports/`): lists `LayoutProvider`, `SurfaceSpec`/`SurfaceRegistry`/`PopupHost`.
  - AD-4, line 77: *"the platform defines exactly these ports; adapters implement them: `IconProvider`, `EventSource`/`EventHub`, `LayoutProvider`, `SurfaceSpec`/`SurfaceRegistry`/`PopupHost`, ..."*
  - Target source tree, lines 232–234: `ags-platform/ports/` includes `LayoutProvider`, `SurfaceSpec/SurfaceRegistry/PopupHost`.
  - **Versus** AD-1, line 47: *"Bar-specific ports (`LayoutProvider`, `SurfaceSpec`, `PopupHost`) stay with the bar, not the platform."*
  - And the bar-specific row, line 36 + target tree line 238–239, which place `LayoutProvider` default / `SurfaceSpec` bodies / `PopupHost` in `ags-apps/bar/`.
- **Evidence:** the four locations above are in the spine itself; no code involved. They cannot all be true. Either the interfaces live in `ags-platform/ports/` (table, AD-4, tree) or they live with the bar (AD-1).
- **Fix:** pick one home and make the table, AD-4, AD-1, and the target tree agree. The likely intent (AD-1) is that the *interfaces* are platform ports while the *default implementations / bodies* are bar-specific — if so, AD-1's wording ("ports ... stay with the bar") should say "defaults/bodies stay with the bar", and the table/tree should not be read as contradicting it.
- **Disposition:** **discuss** (owner decision on the intended layering).

### F3 — Gate framing is true but understated in a way that can mislead

- **Severity:** low
- **Exact claim:** AD-19, line 172: *"today `bar-typecheck`/`ags-typecheck` are excluded from `gates-ci`, and `ags-typecheck` only fails under `audio/`."*
- **Evidence (claim is TRUE):**
  - `Makefile:58`: `gates-ci: $(filter-out capture-typecheck bar-typecheck ags-typecheck,$(GATES))` — both are excluded.
  - `scripts/ags-typecheck.py:91`: `WATCHED_PREFIX = "dotfiles/config/ags/audio/"`; only errors containing that prefix go into `ours` and fail (lines 220, 232–239); everything else is reported as `note` (lines 249–255). So "only fails under `audio/`" is exactly right.
- **Nuance the spine omits:** `ags-typecheck` *does* run in CI on a `[self-hosted, linux]` runner (`.github/workflows/gates.yml:339–348`); only `capture-typecheck` and `bar-typecheck` have no CI job (gates.yml:33). The workflow header explicitly distinguishes "cannot run on a stock runner" from "does not run in CI" (gates.yml:22–35). A reader of the spine could wrongly conclude `ags-typecheck` never runs in CI. Also, `capture-typecheck` — which guards an in-scope `ags-apps` tool — is excluded too but unmentioned.
- **Fix:** add a clause: "excluded from the stock `gates-ci` set; `ags-typecheck` still runs on the self-hosted CI runner, and `capture-typecheck` is also excluded." No rule changes.
- **Disposition:** **discuss / autofix** (one-sentence clarification).

### F4 — Stale Makefile comment (source of the gate claim), not a spine error

- **Severity:** low (context; the spine itself is correct)
- **Exact claim in the repo:** `Makefile:40–41`: *"TWO gates are excluded — `capture-typecheck` and `bar-typecheck`"*.
- **Evidence:** the very next line, `Makefile:58`, filters out **three** (`capture-typecheck`, `bar-typecheck`, `ags-typecheck`). `.github/workflows/gates.yml:22–24` says three. The Makefile comment is stale by one gate.
- **Why it matters here:** the spine's gate claim is correct *despite* its nearest source being stale. If a future editor trusts the comment, the spine's claim could be "corrected" in the wrong direction.
- **Fix:** update the Makefile comment to three (or to reference the filter). This is a repo fix, not a spine fix.
- **Disposition:** **autofix** (repo comment).

### F5 — `wallpaper.state` is ahead of the contract by more than `stage`

- **Severity:** low (incomplete evidence, not false)
- **Exact claim:** AD-6, line 94: *"already observed: `wallpaper.state.stage` ahead of the contract, the dead `speedtest.finished` in hypr-pano"*.
- **Evidence:**
  - The claim is TRUE: `contracts/event-contract.json` `topics["wallpaper.state"].payload` = `{state, wallpaper_hash, trigger}` only, while `src/runtime/src/runtime/cli/main.py:486,587,617,716,724` emits `stage`.
  - But the same runtime also emits `reload_failures` (`main.py:474,496–497`), which the contract also lacks, and `src/runtime/src/runtime/adapters/emit_validation.py:181–201` validates **both** `stage` and `reload_failures` for `wallpaper.state`. So the contract gap is two fields, not one.
- **Fix:** say "`wallpaper.state.stage` / `reload_failures` ahead of the contract", so the codegen scope captures both.
- **Disposition:** **autofix** (one-phrase amendment) or **defer** (AD-6 folds this into codegen anyway).

---

## Verification ledger (claims confirmed TRUE)

| # | Claim | Evidence |
| --- | --- | --- |
| 1 | Real seams are `IconRegistry`, `BarWidgetSpec`, `overlays`, `DomainEventBusCore`/`EventBusTransport` | `lib/icon-registry.ts:32` (`class IconRegistry`, exported singleton `registry` line 61); `kit/widget.tsx:19` (`interface BarWidgetSpec<S>`); `kit/overlay.ts:34` (`export const overlays = {...}` — module-scope singleton); `lib/event-bus-core.ts:96` (`class DomainEventBusCore`) and `:47` (`interface EventBusTransport`). |
| 2 | `IconRef` has no `fallback` today | `kit/icon.ts:13–17` — only `group` + `variant`; no `fallback` anywhere in `kit/` or `lib/icon-registry.ts`. |
| 3 | `subscribe(...)` returns `void` today | `lib/event-bus-core.ts:112` — `subscribe(topic, handler): void`. |
| 4 | `resolve` returns a bare path string today | `lib/icon-registry.ts:37–48` — `resolve(group, variant): string \| null`, a filesystem path or null. |
| 5 | `BarMapping` uses snake_case `icon_size` | `lib/icon-registry.ts:12` (`icon_size: number`); `icons.json` entries `"icon_size": 24` (lines 59, 182, 422, 561, 615). |
| 6 | `OverlayCoordinator` is a value, not a type | No `interface OverlayCoordinator` in the tree; `overlays` (`kit/overlay.ts:34`) is a value exposing exactly `register/isOpen/open/toggle/close/closeAll`. |
| 7 | `EventHub.select` unimplemented | No `EventHub` / `EventSource` / `.select<T>` machinery in the tree (only unrelated `select()` in capture-tool button groups). |
| 8 | 5 icon-registry copies | `dotfiles/config/ags/lib/icon-registry.ts`, `src/gui-tools/{capture-tool,hypr-pano,notifications,wallpaper-selector}/lib/icon-registry.ts`. All 5 differ (drift), 39–78 lines. |
| 9 | 4 `DomainEventBusCore` copies | `class DomainEventBusCore` at `dotfiles/config/ags/lib/event-bus-core.ts:96`, `src/gui-tools/hypr-pano/lib/event-bus-core.ts:100`, `src/gui-tools/icon-color-mapping-editor/lib/event-bus-core.ts:103`, `src/gui-tools/wallpaper-selector/lib/event-bus-core.ts:101`. |
| 10 | 2 bespoke notification readers | `src/gui-tools/notifications/lib/wallpaper-events.ts` and `.../speedtest-events.ts` — both hand-rolled D-Bus `DomainEvent` + `GetTopicState` + `(epoch,seq)` clients; `speedtest-events.ts:68–73` even documents the deliberate sibling duplication. (`services/bluetooth-service.ts:701` mentions `org.dotfiles.Events` only in a comment; it is not a reader.) |
| 11 | Popup chrome in 5 popups | `audio/AudioPopup.tsx`, `components/wifi/WifiPopup.tsx`, `components/battery/BatteryPopup.tsx`, `components/bluetooth/BluetoothPopup.tsx`, `settings-panel/SettingsPanel.tsx` — all present, each with its own window/anchor/keymode chrome. |
| 12 | `bar-typecheck`/`ags-typecheck` excluded from `gates-ci` | `Makefile:58`. (See F3 for the self-hosted nuance.) |
| 13 | `ags-typecheck` only fails under `dotfiles/config/ags/audio/` | `scripts/ags-typecheck.py:91` (`WATCHED_PREFIX`), `:220` (ours → fail), `:249–255` (everything else → note). |
| 14 | notifications per-file list omits `lib/speedtest-events.ts` | `src/provisioning/ansible/roles/gui_tools/vars/main.yml:270–277` lists `theme.ts`, `icon-registry.ts`, `wallpaper-events.ts` — but **not** `speedtest-events.ts`, which exists and is imported by `notifications/ui/NotificationsWindow.tsx:8,1033`. This is a real deployment break, so the claim is well-founded. |
| 15 | Per-file enumeration in `gui_tools` and `compositor_configs` | `gui_tools/vars/main.yml` enumerates each app file/source individually (e.g. `:224,241,259,271–277`); `compositor_configs/vars/main.yml:153–184` enumerates every bar file individually (`ags-app-tsx`, `ags-kit-*`, `ags-event-bus-core`, widgets, …). |
| 16 | AGS 3.1.0, unpinned `aylurs-gtk-shell-git` | `src/provisioning/ansible/group_vars/arch.yml:22` and `debian-family.yml:21` = `aylurs-gtk-shell-git`; `roles/packages/vars/arch.yml:13` AUR list; installed-version evidence in `docs/Animated_Icon_Loader_Findings.md:18`. |
| 17 | The shared-ancestor `node_modules` shortcut does not exist yet | No `ags-platform` symlink/dir anywhere; `dotfiles/config/ags/node_modules/` contains only the dev-time built-in aliases `ags -> /usr/share/ags/js` and `gnim -> /usr/share/ags/js/node_modules/gnim`, which the spine explicitly says are distinct (AD-17). The spine frames the shortcut as target and flags the resolution assumption as an Open Question (line 278). |
| 18 | `wallpaper.state.stage` ahead of the contract | `contracts/event-contract.json` `wallpaper.state` payload = `{state, wallpaper_hash, trigger}`; `main.py` emits `stage`. (See F5 for the second field.) |
| 19 | Dead `speedtest.finished` in hypr-pano | `src/gui-tools/hypr-pano/lib/event-bus-core.ts:25` defines `SPEEDTEST_FINISHED_TOPIC`, re-exported at `event-bus.ts:138`, with no subscriber anywhere. |
| 20 | Audio volume/mic + battery power-mode icon leaks | `audio/AudioPopup.tsx:37` `const icon = (group, variant) => registry.resolve(group, variant) ?? ""` (and `:352,:516`); `components/battery/BatteryContent.tsx:73` `registry.resolve("power-mode", mode.glyph)` — both bypass the uniform `IconRef` contract. |
| 21 | `bar.json` does not exist today | `find` for `bar.json` returns nothing; `contracts/` has only `event-contract.{xml,json,md}` + `schemas/`. Deferred note (line 270) is honest. |
| 22 | Stack: TS 5.9 pinned, node `--test`, no vitest/jest, Python 3.14, `colors.gtk.css` produced by runtime | `node_modules/typescript` = `5.9.3`; `Makefile` `ags-test` runs `node --test`; no vitest/jest configs; `src/provisioning/.venv` is python3.14; `colors.gtk.css` produced in `src/runtime/.../csg_adapter.py`, `seeder.py`, `cache.py`. |
| 23 | AD-6 reverses AD-44 (prior no-codegen) | `architecture-dotfiles-repo-v3-2026-09-11-phase5/.memlog.md:67` records AD-44 as "no codegen pipeline"; the spine's reversal is real. |
| 24 | Doc 101 §11 names theme as a shared seam but §4 defines no Theme port | `docs/101-ags-platform-architecture.md` §4 headers (`:141–333`) list IconProvider/EventSource/LayoutProvider/SurfaceSpec/Notifier/Preferences/BarContext — no Theme; §11 (`:557–575`) mentions "shared ports (icons, events, theme)". |
| 25 | `audio/` already uses ports-and-adapters | `dotfiles/config/ags/audio/application/ports.ts` and `dotfiles/config/ags/audio/composition.ts` both exist. |
| 26 | No cross-app imports today | No imports between `ags-*` config dirs; the only `ags-capture` hit is a path string in `capture-tool/lib/icon-registry.ts` (comment/constant), not an import. |

---

## Target-vs-current honesty

The spine is disciplined about the distinction, and that is its strongest brownfield property:

- The seam paragraph (line 39) explicitly says *"the current reality is pre-port ... this spine freezes the **target** interface those become."*
- Every AD-4 correction is written as "gains / is kept / today returns void" — the parenthetical current-state clauses are all accurate.
- AD-17's `node_modules` shortcut is stated as a rule but flagged in Open Questions (line 278) with the exact verification owed ("verify before relying on it").
- The Structural Seed is labelled target, and its `ags-*` directory names match the names provisioning already uses (`ags-capture`, `ags-notifications`, `ags-hypr-pano`, `ags-wallpaper-selector`, `ags-icme`).
- No current-code claim was found stated as target or vice versa, other than the F2 layering contradiction (which is target-internal, not current-vs-target).

---

## Disposition summary

| Finding | Severity | Disposition |
| --- | --- | --- |
| F1 — "divergent" theme.ts (identical) | medium | autofix (spine wording) |
| F2 — bar-specific ports: table/AD-4/tree vs AD-1 | medium | discuss (owner decision) |
| F3 — gate framing omits self-hosted CI + capture-typecheck | low | discuss / autofix (spine sentence) |
| F4 — stale Makefile "TWO gates" comment | low | autofix (repo comment) |
| F5 — contract gap is `stage` + `reload_failures` | low | autofix / defer (codegen scope) |

**Bottom line:** the spine ratifies reality accurately. Fix F1 and resolve F2 before the spine leaves draft; F3–F5 are cheap clarifications.
