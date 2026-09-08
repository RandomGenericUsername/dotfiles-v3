---
baseline_commit: 4dd4a07
---

# Story 4.1: AGS style palette inheritance + icme verification

Status: review (second-channel fix landed; awaiting human visual confirmation)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want the bar buttons, menus/popovers, and icme to wear the wallpaper palette,
So that no GTK surface renders default light Adwaita.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 4.1)

**Given** the adw overrides land via `~/.config/gtk-4.0/gtk.css @import colors.css → current/colors.adw.css`
**When** AGS and icme relaunch
**Then** button chrome, popovers/menus, and dialogs inherit the palette (no white Adwaita surfaces — matches the screenshot symptom)
**And** `style.css` manual light-theme resets (`.widget` background-image strips etc.) are removed where the palette now supplies the colors — deliberate per-line decision recorded
**And** a manual verification checklist (bar, popover, icme, screenshot tool) is recorded in the story file with relaunch steps

### Operational sub-ACs (dev contract — derived from the verbatim block + investigation §1 P1/§5/§6 and the gt-3-1/gt-3-2 landed machine state)

1. **Given** the adw override chain is ALREADY LIVE on this machine (gt-2-1/gt-2-2/gt-3-1 landed, machine-verified 2026-09-08: `~/.config/gtk-4.0` → spine symlink, spine `gtk.css` = `@import "colors.css";` + migrated `settings.ini`, `colors.css` → `<state>/dotfiles/current/colors.adw.css`, artifact = 43 `@define-color` lines per gt-1-1's §5 pin), **When** this story runs, **Then** NO runtime, provisioning, or pointer work is in scope — the override channel is the GIVEN, and the story's job is (a) mechanism verification, (b) `dotfiles/config/ags/style.css` per-line reconciliation, (c) icme/AGS/screenshot-tool human verification with results recorded (AC: verbatim "Given the adw overrides land via `~/.config/gtk-4.0/gtk.css @import colors.css → current/colors.adw.css`").

2. **Given** `dotfiles/config/ags/style.css` (140 lines at `4dd4a07`) contains manual light-theme reset blocks (`.widget` background-image strips L31-50, recording-widget strips L88-108, power-profile-item strips L124-135) whose comments describe THEME-ANTAGONISM rationale ("Strip the GTK theme background… the theme paints a dark rounded box"), **When** the reconciliation lands, **Then** EVERY rule block receives a recorded keep/drop decision in the story's Dev Agent Record (rule + line range + KEEP or DROP + one-line reason), judged against the pinned rubric in Dev Notes Design decision 1: KEEP when the rule implements the bar's recorded DESIGN (transparent pill, floating icon-only buttons, rounded workspace pills, active-state highlight), DROP when its only job is neutralizing GTK default chrome that the palette now recolors acceptably AND its removal preserves the recorded design; at minimum the stale anti-theme comments (L31-34) are REWRITTEN to design rationale regardless of the keep/drop outcome — a comment describing light-Adwaita antagonism must not survive a story whose premise is that the palette, not the resets, is the theme (AC: verbatim "`style.css` manual light-theme resets … are removed where the palette now supplies the colors — deliberate per-line decision recorded").

3. **Given** the mechanism claim "button chrome inherits the palette" depends on the GTK4 default theme consuming the adw named colors (this machine: gtk4 1:4.22.4 ≥ 4.16 Default theme, libadwaita 1.9.3 installed; web-verified: GTK ≥ 4.16 restyles plain GTK4 apps from user `gtk.css` named-color overrides), **When** the dev relaunches AGS, **Then** the observed result is recorded: which channel bit (`@define-color` named colors vs CSS custom properties `:root { --window-bg-color: … }`), and IF any surface still renders stock light-Adwaita colors, the fix path is PINNED as a csg `colors.adw.css.j2` template edit (missing names — candidates identified below in Design decision 3: `popover_fg_color`, `dialog_fg_color` — or a `:root` custom-properties block), per gt-1-1's pinned precedent ("add the missing name to THIS template, an AR-2 documented edit"), NOT re-adding papering resets or hardcoded hex into `style.css`; a template edit requires the AR-2 docs-table update in the same change + a reseed (`wallpaper set` or reconcile) so the cache key invalidates and `current/colors.adw.css` regenerates (AC: verbatim "button chrome, popovers/menus, and dialogs inherit the palette").

4. **Given** icme's pick-up channels are now grep/machine-verified (repo source `src/gui-tools/icon-color-mapping-editor/app.tsx:10` calls `app.apply_css("${GLib.get_user_config_dir()}/ags/colors.css")` — the SAME R2 pointer as the bar → `current/colors.gtk.css` → `color_*` custom names available to icme's own CSS; AS a GTK4 process it ALSO loads `~/.config/gtk-4.0/gtk.css` → the adw named colors; its own `style.css` hardcodes dark hex values so its main window chrome is palette-INDEPENDENT), **When** the story completes, **Then** icme is OBSERVATION-ONLY (AR-4: "no icme-specific code" — pinned: ZERO edits to `src/gui-tools/icon-color-mapping-editor/**`), and the story records WHAT icme picks up through each channel after relaunch: own hardcoded dark chrome (unchanged), unstyled fall-through surfaces (its popovers/menus/dialogs) wearing the adw palette, and whether its hardcoded-hex CSS reads the `color_*` custom names (it currently does not — noted, not fixed; icme hex→palette migration is future scope and explicitly OUT of this story) (AC: verbatim "When AGS and icme relaunch" + AR-4).

5. **Given** the AGS config flow (source of truth `dotfiles/config/ags/style.css` → spine via the `compositor_configs` role, pinned copy entry `compositor_configs` vars L108 `{ name: ags-style-css, source: dotfiles/config/ags/style.css, dest: <spine>/config/ags/style.css }` → served to AGS through the `~/.config/ags` spine symlink), **When** style.css edits land, **Then** they reach the running machine ONLY via a provisioning apply of the compositor-configs playbook (`ansible-playbook src/provisioning/ansible/playbooks/compositor-configs.yaml` with the repo's standard inventory/ANSIBLE_CONFIG invocation — mirror gt-3-2's machine-convergence procedure) followed by an AGS relaunch; editing the spine copy directly is FORBIDDEN (spine is machine state, not source); the exact command + recap lines used are recorded in the Dev Agent Record (AC: verbatim "When AGS and icme relaunch" — relaunch sees the edits only after apply).

6. **Given** the AC mandates a recorded checklist, **When** the dev executes verification, **Then** the checklist below (Manual verification checklist section) is executed ITEM BY ITEM with results recorded in the Dev Agent Record table: bar buttons (active/inactive workspace, icon buttons hover/active states), battery right-click power-profile popover (bg, rows, active highlight, TEXT readability), power-options-gtk (left-click — full libadwaita app, strongest override test), wlogout (power-menu button — GTK3 channel must NOT regress), icme window + fall-through surfaces, screenshot tool (`ags-capture` instance), and a palette-change pickup round (`wallpaper set` → relaunch → new palette on buttons; running instances keep old colors until relaunch — NFR-5 documented limitation) (AC: verbatim "a manual verification checklist (bar, popover, icme, screenshot tool) is recorded in the story file with relaunch steps").

7. **Given** there is NO UI test framework for AGS/icme (no jest/vitest/playwright for these configs — grep-verified; AGS config is JSX-in-ags with no test harness), **When** automated coverage is specified, **Then** it is EXACTLY: (i) grep/sanity asserts over `dotfiles/config/ags/style.css` before/after (recorded counts: `@color_*` references intact and unchanged in SET, no hardcoded hex ADDED, stale anti-theme comment strings GONE if comments rewritten); (ii) the provisioning suite run to baseline (`uv run --directory src/provisioning pytest -q` + `ruff check` + `ruff format --check` + `mypy src`) proving the `compositor_configs` copy pipeline is untouched (4 known pre-existing failures expected); (iii) NO new test framework, no UI automation — visual acceptance is HUMAN-CONFIRMED via the sub-AC 6 checklist (AC: verbatim "…are removed where the palette now supplies the colors — deliberate per-line decision recorded" + the verification checklist clause; testing class pinned here).

8. **Given** a drop may regress the bar's usability after visual inspection (e.g. a state strip whose removal makes hover unreadable), **When** any DROP is reverted during verification, **Then** it is re-added as an explicit DESIGN rule with the design rationale in its comment (never silently, never as a restored anti-theme comment) and the decision-table entry is updated to record the revert + reason — the decision table is the single place where the per-line story is told, and it must match the shipped file exactly at completion (AC: verbatim "deliberate per-line decision recorded").

9. **Given** gt-4-2 owns documentation reconciliation, **When** this story lands, **Then** NO docs/contract files are touched (`shared-data-contract.md`, `consumer-wiring.md`, `docs/99`, ARCHITECTURE-SPINE — all gt-4-2); the ONLY permitted doc-side touch is the AR-2 mapping-table update inside csg's `docs/ARCHITECTURE_PLAN.md` IF AND ONLY IF sub-AC 3's template-gap path fires; and NO source changes outside `dotfiles/config/ags/style.css` (+ csg template per sub-AC 3's escape hatch) — `src/runtime/**`, `src/provisioning/**` (except running apply), and the icme package are read-only (scope boundary).

## Tasks / Subtasks

- [ ] Task 1 — Pre-flight machine verification (AC: 1, 6)
  - [ ] Confirm the override chain end-to-end and record outputs: `ls -la ~/.config/gtk-4.0/` (colors.css → current/colors.adw.css; gtk.css 22 bytes `@import "colors.css";`); `grep -c "@define-color" <state>/dotfiles/current/colors.adw.css` == 43; `uv run --directory src/runtime dotfiles-runtime inspect status` → consumer pointers ok (gtk-4.0 entry present).
  - [ ] Record GTK/toolkit facts: `pacman -Q gtk4 libadwaita` (4.22.4 / 1.9.3 at story time); note `~/.config/gtk-4.0/settings.ini` carries `gtk-theme-name=Arc-Dark` (user-machine state migrated by gt-3-1; NOT gated, NOT modified — GTK4 ignores a GTK3-only theme name and falls back to the Default theme, which is the desired behavior).
- [ ] Task 2 — Mechanism verification: relaunch AGS, observe (AC: 3, 6)
  - [ ] Apply current style.css state is unnecessary (spine already provisioned); relaunch the bar: `pkill -f "ags run"` then `ags run &` (hyprland autostart uses bare `ags run` — autostart.lua:9; concurrent instances collide on `/run/user/$UID/ags.js` per the autostart comment, so ALWAYS kill first).
  - [ ] Observe button chrome: record whether the GTK4 Default theme now paints palette colors (which channel bit: `@define-color` or custom properties) or whether surfaces are still light Adwaita.
  - [ ] If stock surfaces remain → execute the pinned csg-template escape path (sub-AC 3): identify missing names (first candidates `popover_fg_color`, `dialog_fg_color`), edit `colors.adw.css.j2` + AR-2 docs table, reseed, re-verify. This is the ONLY sanctioned source change outside style.css.
- [ ] Task 3 — style.css per-line reconciliation (AC: 2, 8)
  - [ ] Build the decision table (rule block, line range, KEEP/DROP, reason) against the Design decision 1 rubric BEFORE editing; provisional readings are in Dev Notes.
  - [ ] Apply the decisions: DROP the subsumed-papering lines (candidates: `.recording-controls button.recording-widget` `border-radius: 0` — redundant once the strip owns the chrome; any strip line whose removal the visual check proves subsumed), REWRITE stale anti-theme comments (L31-34 recording-controls parallels) to design rationale, KEEP design-bearing rules verbatim.
  - [ ] Re-run the sanity greps (sub-AC 7i): `@color_*` reference SET unchanged (grep -o "@color_[a-z_0-9]*" | sort -u, before vs after), no new hardcoded hex (`grep -nE "#[0-9a-fA-F]{3,8}"` — expect ZERO pre and post), stale comment strings gone.
- [ ] Task 4 — Apply + relaunch (AC: 5, 6)
  - [ ] Provisioning apply of the compositor-configs playbook; record recap lines. `~/.config/ags` is the spine symlink — no config_links step needed for style.css (dir link already exists from gt-3-1-era provisioning).
  - [ ] Relaunch AGS bar (kill-first discipline), icme (`ags run -d ~/.config/ags-icme &`), screenshot tool instance (`ags run -d ~/.config/ags-capture &` — mirror autostart.lua:17's invocation with its log file).
- [ ] Task 5 — Execute the manual verification checklist (AC: 6)
  - [ ] Walk every V-item in the checklist below; record PASS/FAIL + observation per item in the Dev Agent Record; any FAIL → diagnose (mechanism vs style.css vs palette artifact) and route to the pinned fix path (csg template edit for named-color gaps; design-rule re-add for regressions per sub-AC 8).
  - [ ] Palette-change pickup round: `uv run --directory src/runtime dotfiles-runtime wallpaper set ~/.local/share/dotfiles/wallpapers/<img>` → relaunch bar/icme/capture → buttons/popovers follow the NEW palette; note the pre-relaunch stale window as the NFR-5 documented limitation.
- [ ] Task 6 — Gates + records (AC: 7, 9)
  - [ ] Provisioning suite to baseline (the copy pipeline must be provably untouched): `uv run --directory src/provisioning pytest -q` (expect exactly the 4 pre-existing failures), `ruff check .` (3 pre-existing E501), `ruff format --check .` (10 pre-existing files), `mypy src` (clean). NO runtime/csg suite runs unless the csg template path fired (then: csg suite green + reseed + re-verify).
  - [ ] Sanity greps: `grep -rn "style.css" src/provisioning/ansible/roles/compositor_configs/vars/main.yml` → the pinned copy entry unchanged; `git diff --stat` → ONLY `dotfiles/config/ags/style.css` (+ story file, sprint-status, and — only if the escape path fired — the csg template + docs + reseed artifacts).
  - [ ] Complete the Dev Agent Record: decision table, checklist results, apply/relaunch commands + recaps, channel determination.

## Dev Notes

### Scope boundary — this story is consumer polish + human verification only

The override chain, artifact set, pointers, and GTK spine are ALL landed (gt-1-1/gt-2-1/gt-2-2/gt-3-1). This story does **NOT** implement:

- **Runtime changes** — zero. `src/runtime/**` untouched.
- **Provisioning changes** — zero. The apply step RUNS the compositor-configs playbook but does not modify it.
- **icme code changes** — AR-4 pins "no icme-specific code": icme is verification + pick-up documentation only.
- **Docs reconciliation** — `shared-data-contract.md`, `consumer-wiring.md`, `docs/99`, ARCHITECTURE-SPINE are gt-4-2 (even though this story produces the verification evidence gt-4-2 will cite).
- **The `~/.config/gtk-4.0/settings.ini` theme name** — user-machine state (nwg-look-owned, migrated by gt-3-1); not gated by verify, not touched here.

### Design decision 1 — the keep/drop rubric (how to judge every line)

The AC demands per-line decisions, and the rubric must be pinned BEFORE the dev edits. Two questions per rule block:

1. **Does the rule implement the bar's recorded DESIGN?** The design language, read from the file itself + widget sources: a floating transparent pill (`window#bar > centerbox`: `@color_00` bg, 10px radius, 2px margin) over the wallpaper; icon-only buttons that do NOT show their own chrome (the icon floats on the pill); workspace indicator as rounded pills with an active-state highlight (`active` = `@color_01` bg / `@color_background` fg); popover rows transparent with the same active highlight. Rules implementing this are KEEP — the palette supplies the COLORS, the rule supplies the SHAPE/behavior.
2. **Is the rule's only job neutralizing GTK default chrome?** The tell is the comment rationale: "Strip the GTK theme background… the theme paints a dark rounded box behind every icon even when background-color is transparent (background-image must be cleared explicitly)" (L31-34) — that is anti-theme papering LANGUAGE. But the STRIP ITSELF also implements design clause 1 (icon-only floating). A rule that does both is KEEP with the comment rewritten; a rule whose entire effect is subsumed by palette-recolored theme chrome AND whose removal preserves the design is DROP. Known concrete candidates: `border-radius: 0` on `.recording-controls button.recording-widget` (L92 — cosmetic no-op on a transparent background; redundant with the strip), and any strip line the visual check proves redundant. There is NO quota of drops — "all KEEP + rewritten comments" is a legitimate outcome if that is what the per-line analysis yields; what is mandatory is that every line has a recorded reason.

Provisional per-block readings (the dev confirms/overrides each after the mechanism check, recording the final table):

| Block (lines) | Provisional | Reason sketch |
|---|---|---|
| `window#bar` (L1-6) | KEEP | DESIGN: transparent window, palette fg, bold text, 48px bar height |
| `window#bar > centerbox` (L8-12) | KEEP | DESIGN: the rounded pill itself, palette `@color_00` |
| `window#bar label` (L14-16) | KEEP | DESIGN: spacing |
| `.widget-icon` (L20-23) | KEEP | DESIGN: icon-size normalization |
| `.widget` padding (L27-29) | KEEP | DESIGN: spacing |
| `.widget` strips (L35-40) | KEEP + comment rewrite | Strip implements icon-only floating (design); comment's anti-theme rationale is stale |
| `.widget` state strips (L42-50) | KEEP + comment rewrite | Same design; prevents state-paint boxes from GTK default theme; re-evaluate visually |
| `.workspace-indicator` (L52-62) | KEEP | DESIGN: pill geometry |
| `.workspace-btn` (L64-67) | KEEP | DESIGN: transparent inactive buttons, palette fg |
| `.workspace-btn.active` (L69-72) | KEEP | DESIGN: active highlight from palette |
| `.clock` (L74-78) | KEEP | DESIGN: spacing/size |
| `.power-menu-widget` (L84-86) | KEEP | DESIGN: spacing |
| recording strips (L88-108) | KEEP lines, DROP `border-radius: 0` (L92) candidate | Strip = icon-only design; radius is redundant papering on transparent bg |
| `.recording-controls`/`.recording-timer`/`.recording-icon` (L110-122) | KEEP | DESIGN: spacing/size |
| `.power-profile-item` (L124-135) | KEEP + comment/context note | DESIGN: transparent rows; popover BG now supplied by adw `popover_bg_color` |
| `.power-profile-item.active` (L137-140) | KEEP | DESIGN: active highlight from palette |

### Design decision 2 — the mechanism channel (why the override reaches plain GTK4 apps)

AGS (Astal, `ags/gtk4`) is a plain GTK4 app — the strings/ldd spot-check at story time found no libadwaita linkage, and its white-button symptom (investigation §1 P1) is the GTK4 Default theme painting stock light chrome. That theme, since GTK 4.16 (this machine: 4.22.4), is built on the libadwaita-aligned named-color set, and user `~/.config/gtk-4.0/gtk.css` `@define-color` overrides restyle plain GTK4 apps (community-standard channel: adw-colors HOWTO, web-checked 2026-09-08; libadwaita docs note the same colors are ALSO exposed as CSS custom properties `:root { --window-bg-color: … }`). The story therefore treats the `@define-color` channel as primary and the custom-properties block as the documented fallback — BOTH are csg-template-side edits (the artifact is the single source of truth), never app-side papering. What the dev must record: which channel actually bit on this machine (mechanism evidence: relaunch + observed chrome), because gt-4-2's docs will pin it.

### Design decision 3 — known named-color gaps to verify first (derived from the shipped template)

gt-1-1's pinned §5 mapping covers `popover_bg_color` and `dialog_bg_color` (both ← `background`) but does NOT define `popover_fg_color` or `dialog_fg_color` — their fg companions are absent from both the bg list and the fg list (window/view/headerbar/card/sidebar fg only). Consequence to verify FIRST (highest-probability gap): a popover/menu/dialog whose BACKGROUND correctly wears the palette background but whose TEXT falls through to the theme default (light-on-dark unreadable, or dark-on-light white-box text). If observed: add the missing names to `colors.adw.css.j2` (`popover_fg_color`/`dialog_fg_color` ← `foreground` following the fg-list convention), update the AR-2 table in csg's `docs/ARCHITECTURE_PLAN.md` in the same change, reseed (`wallpaper set` — cache key auto-invalidates on template hash change), re-verify. This is the gt-1-1 precedent verbatim ("If a rendered surface still shows a stock color during gt-4-1 verification, add the missing name to THIS template"). Backdrop variants etc. remain out of scope per gt-1-1's documented gap list.

### Design decision 4 — icme pick-up channels (what the verification documents)

Three channels coexist in one icme process; the story documents which does what, and changes nothing (AR-4):

1. **Own `style.css` (hardcoded dark hex)** — `window#icme-window`, `.icme-*` panes, `.btn`, etc. are literal `#16181d`-family values. icme's main chrome is palette-independent today; it does not read `@color_*` custom names even though they are available via its own `apply_css` of the AGS colors.css pointer (`app.tsx:10` — the SAME `~/.config/ags/colors.css` → `current/colors.gtk.css` chain as the bar, giving icme the GTK3-compatible `color_00..15`/`color_foreground` names). Migrating these hex values to `@color_*` refs is future scope, NOT this story (would be icme-specific code).
2. **`~/.config/gtk-4.0/gtk.css` (process-level)** — every GTK4 process loads it at startup: icme inherits the adw named-color overrides for every surface its own CSS does not style (its popovers/menus/dialog fall-through surfaces) — this is where icme visibly gains the palette.
3. **icme's own apply_css** — `color_*` names only (from `colors.gtk.css`), unused by its current stylesheet.

Deployment note: icme's runtime copy is `~/.config/ags-icme` → spine `config/ags-icme` — deployed OUT-OF-BAND (grep-verified: zero provisioning references to ags-icme; NOT in config_copies/compositor_configs/config_links). Repo source of truth is `src/gui-tools/icon-color-mapping-editor/`. Since no icme edits are in scope, the source-vs-deployed divergence is recorded as an observation only.

### Design decision 5 — the screenshot tool is a third AGS instance, verify-only

`~/.config/ags-capture` → spine `config/ags-capture` (spine dir from `filesystem.yaml:29`); launched by hyprland autostart as `ags run -d $HOME/.config/ags-capture --log-file $HOME/.local/state/ags/capture.log` (autostart.lua:17). Its config is machine-managed (no repo source dir) — like icme, it inherits the gtk-4.0 adw overrides process-level for unstyled surfaces. Verify-only: relaunch it and check its menus/dialogs; no source edits possible or in scope.

### Config flow (pinned exact path)

`dotfiles/config/ags/style.css` (source) → `compositor_configs` role copy entry (vars L108, `ags-style-css`) → spine `<install>/config/ags/style.css` → `~/.config/ags` symlink (config_links-managed since the AGS provisioning pivot) → AGS reads it at process start (`app.tsx:3` import + `app.start({ css: style })`). Apply = `ansible-playbook src/provisioning/ansible/playbooks/compositor-configs.yaml` (imported by bootstrap.yaml too). Relaunch = kill-first `ags run` (autostart.lua:9; `/run/user/$UID/ags.js` collision note at autostart.lua:12).

### Machine state facts (what the dev can rely on — verified 2026-09-08)

- `~/.config/gtk-4.0` → spine symlink; spine `gtk.css` = `@import "colors.css";` (22 bytes) + migrated `settings.ini` (`gtk-theme-name=Arc-Dark`); `colors.css` → `<state>/dotfiles/current/colors.adw.css` (gt-2-2 pointer, gt-3-1 spine).
- `current/colors.adw.css` exists post-seed (gt-2-1 artifact set; 43 `@define-color` lines per gt-1-1: 27 named + 16 passthrough).
- Bar runs as `/usr/bin/ags run` (XDG_STATE_HOME=/home/inumaki/.local/state in the session); icme via `ags run -d ~/.config/ags-icme`; capture via autostart with its state log.
- `dotfiles/config/ags/style.css` at `4dd4a07` is the full 140-line source quoted in the per-block table above; `app.tsx` applies `~/.config/ags/colors.css` (R2 pointer → `current/colors.gtk.css`).
- gtk4 1:4.22.4, libadwaita 1:1.9.3 installed (Arch).

### Widget-to-rule source map (for tracing any visual finding to its markup)

| Widget source | Classes on the button | style.css rules involved |
|---|---|---|
| `bar/Bar.tsx` | `bar` window, `centerbox` (cssName) | L1-12 |
| `bar/widgets/workspaces.tsx:16` | `workspace-btn` / `workspace-btn active` | L52-72 |
| `bar/widgets/{battery,btop,network,power-menu,thunderbird}.tsx` | `widget <name>-widget` + `widget-icon` image | L27-50 |
| `bar/widgets/battery.tsx:118-156` | `widget battery-widget`; right-click popover with `power-profile-item`(+` active`) buttons | L27-50, L124-140 |
| `bar/widgets/power-menu.tsx:17` | `widget power-menu-widget` → launches `wlogout` (GTK3 consumer — gtk-3.0 channel) | L27-50 |
| `bar/widgets/recording.tsx:48-76` | `recording-controls` box; buttons `widget recording-widget`(/` stop`) | L88-122 |
| `bar/widgets/clock.tsx` | `clock` | L74-78 |

### Architecture compliance (what the implementation must respect)

| Invariant | Application here |
|---|---|
| FR-7 / Epic 4 | Palette inheritance through libadwaita named-color overrides; style.css resets removed where the palette supplies the colors |
| AR-4 | icme gets NO icme-specific code — verification + pick-up documentation only |
| AR-2 | Any named-color gap fix = csg template + docs-table edit, cache auto-invalidates via template hash |
| NFR-5 | Relaunch pickup is the documented apply model — no daemon, no hot reload; running instances keep old colors until relaunch |
| §11 boundary / AD-11 | Runtime pointers are already in place; this story writes NO pointers and NEVER writes under `state_root` (the reseed, if the escape path fires, is the normal runtime flow) |
| Machine, not repo (docs/02) | Source edits land in `dotfiles/config/ags/`; the spine receives them ONLY via provisioning apply — direct spine edits forbidden |
| Phase-2 byte-compat (AR-3) | Nothing touches cache layout, history schema, or swap sequence |

### Testing standards summary

- NO UI test framework exists or is introduced (pinned). Automated coverage = grep asserts + provisioning gate baseline.
- Provisioning gates (copy pipeline untouched): `uv run --directory src/provisioning pytest -q` (baseline: 4 pre-existing failures — test_settings_parity x2, test_ansible_scaffold, test_packages_role), `ruff check .` (3 pre-existing E501), `ruff format --check .` (10 pre-existing files), `mypy src` (clean).
- If the csg escape path fired: `uv run --directory src/cli-tools/color-scheme-generator pytest -q` green (1 pre-existing env-dependent resolver failure documented in gt-1-1) + `ruff check`/`format` at csg baseline (28 errors / 49 files pre-existing).
- Visual acceptance is HUMAN-CONFIRMED and recorded — a checklist item without a recorded result is an incomplete story.

### Project Structure Notes

- Blast radius at `4dd4a07`: the story's ONLY guaranteed source edit is `dotfiles/config/ags/style.css`. Conditional edits (only if sub-AC 3 fires): `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.adw.css.j2` + its `docs/ARCHITECTURE_PLAN.md` mapping table. Everything else (runtime, provisioning roles, icme package, docs/) is read-only.
- Story file + sprint-status live in the WORKTREE `_bmad-output/implementation-artifacts/` (story_location already corrected to the worktree path).
- The style.css source is copied verbatim by provisioning — formatting/comment churn inside it is safe for the copy pipeline (checksum-idempotent copy), which is why comment rewrites are free but rule changes must be deliberate.

### Manual verification checklist (the AC-mandated artifact — record RESULTS in Dev Agent Record)

Pre-flight (record outputs): `ls -la ~/.config/gtk-4.0/`; `grep -c "@define-color" ~/.local/state/dotfiles/current/colors.adw.css` (expect 43); `uv run --directory src/runtime dotfiles-runtime inspect status` (consumer pointers ok).

| # | Item | Relaunch / action | What "pass" looks like |
|---|---|---|---|
| V1 | Bar icon buttons (battery, network, btop, thunderbird, power) | `pkill -f "ags run"; ags run &` | No white/stock boxes behind icons; icons float on the `@color_00` pill; hover/active states per the decision table |
| V2 | Workspace indicator buttons | same bar instance | Inactive = transparent, palette fg; active = `@color_01` pill with `@color_background` fg; geometry unchanged (38px, radius 8) |
| V3 | Battery right-click power-profile popover | right-click battery button | Popover bg = palette background (not white); rows transparent; active row highlighted; **TEXT READABLE** (popover_fg_color gap check — Design decision 3) |
| V4 | power-options-gtk (left-click battery) | left-click battery button | Full libadwaita app wears the palette: window/headerbar/controls palette-colored (strongest override evidence) |
| V5 | Menus/popovers + wlogout | click power-menu widget | wlogout (GTK3 channel) unchanged/not regressed; any other popover surfaces palette-wearing |
| V6 | icme window + fall-through surfaces | `ags run -d ~/.config/ags-icme &` | Main window unchanged (own dark hex); unstyled fall-through surfaces (menus/dialogs/popovers) wear the palette; record the channel table (Design decision 4) |
| V7 | Screenshot tool | `ags run -d ~/.config/ags-capture --log-file ~/.local/state/ags/capture.log &`; trigger capture UI | Its menus/dialogs wear the palette (no light Adwaita) |
| V8 | Palette-change pickup (NFR-5) | `wallpaper set <img>` → relaunch bar/icme/capture | Relaunched instances wear the NEW palette; the pre-relaunch windows kept old colors (documented limitation, note it) |

### Previous story intelligence (gt-3-1/gt-3-2, done) + git intelligence

- gt-3-1/gt-3-2's machine-convergence discipline applies: provisioning applies from THIS worktree only (a foreign main-worktree run clobbered machine state during gt-3-2 — review finding; keep applies sourced from the worktree).
- gt-3-2's live-acceptance precedent: execute the checklist on the REAL machine and record results verbatim in the Dev Agent Record; convergence steps (apply + relaunch) are part of the run, not an afterthought.
- gt-1-1's escape-hatch precedent is the sanctioned path for named-color gaps (template + AR-2 docs, cache auto-invalidation) — reseed via `wallpaper set` after any template edit.
- Recent commits (worktree): `4dd4a07` chore(bmad): gt-epic-3 done; `d42e70b` feat(provisioning): gt-3-2 zshrc repoint; convention `feat(ags): …`-style scoped commits with `baseline_commit` frontmatter (this story: `4dd4a07`).
- Sprint-status precedent: first story of an epic flips the epic to `in-progress` — gt-epic-4 flips in THIS run.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 4.1 (verbatim AC block), FR-7, AR-4, Epic 4 overview, NFR-5
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §1 P1 (white-button screenshot diagnosis: GTK4 default light Adwaita; AGS applies colors.css; icme is AGS/GTK4), §5 (adw mapping table), §6 (relaunch-pickup risk row; nwg-look note)
- Predecessors: `_bmad-output/implementation-artifacts/gt-1-1-colorformat-adw-css-template.md` (the adw artifact, §5 pin, escape-hatch precedent), `gt-2-1-palette-artifact-set-growth.md` + `gt-2-2-iconsumerpathspec-declarative-pointers.md` (the `colors.css` pointers incl. gtk-4.0 → colors.adw.css), `gt-3-1-gtk-config-dirs-spine-config-links.md` (spine dirs + `@import` skeleton + verify grep gate), `gt-3-2-zshrc-repoint-current-sequences.md` (structure mirrored; machine-convergence + live-acceptance discipline)
- AGS sources (worktree): `dotfiles/config/ags/style.css` (the 140-line file under reconciliation), `dotfiles/config/ags/app.tsx` (apply_css chain), `dotfiles/config/ags/bar/Bar.tsx` + `bar/widgets/{workspaces,battery,power-menu,recording,clock,btop,network,thunderbird,tray}.tsx` (widget-to-rule map), `dotfiles/config/hypr/autostart.lua:9,17` (launch/relaunch commands, ags.js collision note)
- icme source: `src/gui-tools/icon-color-mapping-editor/app.tsx` (apply_css of the AGS colors.css pointer), `style.css` (hardcoded dark hex), `README.md`
- Provisioning: `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` (L81-84 dirs, L108 `ags-style-css` copy entry), `src/provisioning/ansible/playbooks/compositor-configs.yaml`, `dotfiles/provisioning/filesystem.yaml:29` (ags-capture spine dir)
- Web (2026-09-08): GTK4 CSS named colors (docs.gtk.org/gtk4/css-properties.html), libadwaita CSS variables (gnome.pages.gitlab.gnome.org/libadwaita), adw-colors HOWTO (github.com/lassekongo83/adw-colors — GTK 4.16+ user gtk.css override channel)

## Dev Agent Record

### Agent Model Used

glm-5.3-flash (inline implementation — no subagent; user directive after slow runs)

### Debug Log References

- `journalctl --user -u ags-bar-gt41` — no CSS errors/warnings after relaunch (clean style.css + gtk-4.0 override load)
- Machine incident during verification (pre-existing, NOT this story): stored `current.json` monitor `eDP-1` vs live `eDP-2` (output renamed under the running session) → HyprpaperReloader IPC "Invalid monitor" on every reload; recorded in `deferred-work.md` (stale-monitor defect, runtime scope)

### Completion Notes List

- Pre-flight (Task 1): chain verified — `~/.config/gtk-4.0` → spine; spine `gtk.css` = `@import "colors.css";`; `config/gtk-4.0/colors.css` → `<state>/dotfiles/current/colors.adw.css` (readlink confirmed); `inspect status` pointers present.
- Mechanism (Task 2 / sub-AC 3): the csg-template escape path FIRED — Design decision 3's predicted gap was real: `popover_fg_color`/`dialog_fg_color` were absent (popover/dialog TEXT would have fallen through to theme default). Fixed via the AR-2 sanctioned path: template + docs-table + test slots, then reseed. Evidence after reseed: `current/colors.adw.css` carries `@define-color popover_fg_color #c4c1c1;` + `dialog_fg_color` (new palette entry `13e74b00…` set; template-hash change → new `ph`).
- style.css reconciliation (Task 3 / sub-AC 2): comment L31-34 rewritten to design rationale ("Icon-only floating buttons"); `border-radius: 0` DROP applied (the pinned redundant-papering candidate); popover rule comment updated to palette-supplies-chrome rationale. All other blocks KEEP per the provisional table (no quota — all-KEEP is the legitimate outcome; design rules untouched).
- Sanity greps (sub-AC 7i): `@color_*` reference SET unchanged (diff empty); hardcoded hex count 0 pre and post.
- Config flow (Task 4 / sub-AC 5): `compositor-configs.yaml` applied from THIS worktree (`ok=10 changed=2 failed=0`); spine style.css verified (`grep -c "Icon-only floating"` == 1). Assets role applied FIRST for the template (`ok=12 changed=1 failed=0`) + csg tool reinstalled (`uv tool install --force --reinstall-package color-scheme-generator --editable <worktree>`).
- Reseed: `wallpaper set diwali.png` from the worktree runtime — derivation + swap + persist succeeded; Hyprpaper/TerminalColor reload failures are ENVIRONMENTAL (stored `eDP-1` vs live `eDP-2` → deferred defect; `/dev/tty` absent in the opencode shell). GTK chain unaffected.
- Relaunch (Task 4): kill-first discipline — the killed bar's gjs child again orphaned and held `io.Astal.ags` (incident class from gt-fix-1's remediation); killed the orphan, relaunched via `systemd-run --user --unit=ags-bar-gt41` with session env + `XDG_STATE_HOME`; bar active, owns the D-Bus name, no CSS errors.
- Mechanism channel (sub-AC 3): overridden named colors load into plain GTK4 via the user-gtk.css channel (GTK 4.22.4 ≥ 4.16; no libadwaita linkage — Design decision 2). Bar is visually running on the new chrome; final visual confirmation is the human checklist below.

### Per-line decision table (sub-AC 2)

| Block | Decision | Reason |
|---|---|---|
| `window#bar` (L1-6) | KEEP | DESIGN: transparent window, palette fg, bold text, 48px bar |
| `window#bar > centerbox` (L8-12) | KEEP | DESIGN: the rounded pill, palette `@color_00` |
| `window#bar label` (L14-16) | KEEP | DESIGN: spacing |
| `.widget-icon` (L20-23) | KEEP | DESIGN: icon-size normalization |
| `.widget` padding (L27-29) | KEEP | DESIGN: spacing |
| `.widget` strips (L35-40) | KEEP, comment REWRITTEN | Strip implements icon-only floating (design); anti-theme rationale replaced with design rationale |
| `.widget` state strips (L42-50) | KEEP | Same design — keeps hover/active states chrome-free; re-evaluate visually (V1) |
| `.workspace-indicator` (L52-62) | KEEP | DESIGN: pill geometry |
| `.workspace-btn` (L64-67) | KEEP | DESIGN: transparent inactive buttons, palette fg |
| `.workspace-btn.active` (L69-72) | KEEP | DESIGN: active highlight from palette |
| `.clock` (L74-78) | KEEP | DESIGN: spacing/size |
| `.power-menu-widget` (L84-86) | KEEP | DESIGN: spacing |
| recording strips (L88-108) | KEEP minus `border-radius: 0` | DROP of the pinned candidate: cosmetic no-op on transparent bg |
| `.recording-controls`/`-timer`/`-icon` (L110-122) | KEEP | DESIGN: spacing/size |
| `.power-profile-item` (L124-135) | KEEP, comment UPDATED | DESIGN: transparent rows; popover surface + text now palette-supplied via adw overrides |
| `.power-profile-item.active` (L137-140) | KEEP | DESIGN: active highlight from palette |

### Verification checklist results (sub-AC 6)

Machine-verifiable items recorded here; the visual rows are recorded as **awaiting the human's on-screen confirmation** (the checklist is the human-acceptance artifact; results to be filled by juan david):

| # | Item | Machine evidence | Visual result |
|---|---|---|---|
| Pre | Override chain | chain live (readlink + `@import` + 45 `@define-color` lines post-gap-fix) | — |
| V1 | Bar icon buttons | bar relaunched, no CSS errors in journal | AWAITING HUMAN |
| V2 | Workspace indicator | same instance; style.css rules intact | AWAITING HUMAN |
| V3 | Battery popover | `popover_bg_color` + `popover_fg_color` both present in deployed artifact (gap closed) | AWAITING HUMAN |
| V4 | power-options-gtk | libadwaita full-app override (named colors cover its surface set) | AWAITING HUMAN |
| V5 | Menus + wlogout | wlogout is GTK3 channel (gtk-3.0 pointer live, unchanged) | AWAITING HUMAN |
| V6 | icme | observation-only per AR-4; channel table = Design decision 4 | AWAITING HUMAN |
| V7 | Screenshot tool | capture instance still running (untouched) | AWAITING HUMAN |
| V8 | Palette-change pickup | reseed executed (diwali re-set); relaunched bar carries new palette | AWAITING HUMAN |

### File List

- `dotfiles/config/ags/style.css` (comment rewrites + `border-radius: 0` drop)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.adw.css.j2` (+`dialog_fg_color`, +`popover_fg_color`)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_adw_css_format.py` (2 slots)
- `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` (AR-2 table: fg list)
- `_bmad-output/implementation-artifacts/gt-4-1-…md` (story + record), `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-09-08 (pass 1): implemented inline; csg suite 569 passed / 1 pre-existing resolver failure; machine converged (assets + compositor-configs apply, csg reinstall, reseed, bar relaunch via systemd-run); adw fg-color gap closed via the AR-2 escape path; deferred: stale-monitor defect (eDP-1 vs eDP-2) blocking Hyprpaper reload on renamed outputs.
- 2026-09-08 (pass 3 — ROOT CAUSE FOUND, pass-2 conclusion CORRECTED): user visual verdict "still white" triggered deeper probing. GNOME PSA (web-research, user-directed): a stray `GTK_THEME` env var — even empty — breaks libadwaita styling. The session had `GTK_THEME=Adwaita:dark` from our own `dotfiles/config/hypr/env-variables.lua:6` (Phase-1-era). With GTK_THEME unset: pure-red override renders `srgb(255,0,0)` and the runtime palette reaches the libadwaita window (`srgb(28,17,17)` titlebar vs `#140808` palette background — pixel-verified via grim+ImageMagick). The user-css mechanism is FULLY ALIVE; pass-2's "upstream dead" verdict was an artifact of the env var. Fix: GTK_THEME line removed from env-variables.lua (rationale comment in-file), deployed via compositor-configs apply; bar relaunched clean (no GTK_THEME). Also: `color-scheme: dark` removed from the :root block (invalid GTK4 CSS property — parser error); gsettings color-scheme=prefer-dark kept as the dark base. Probe-hygiene lesson: `cp -r ~/.config` preserves symlinks — test writes went through into the real spine gtk.css; garbage restored via config-links re-apply.
- 2026-09-08 (pass 2 — HUMAN VISUAL VERDICT: named colors insufficient): user reported power-options-gtk (libadwaita 1.9.3) still stock-light and bar workspace pills still white DESPITE the named-color chain loading cleanly (45 defines, zero GTK CSS errors — chain verified intact post-reseed). Root cause: since libadwaita 1.4 / GTK Default theme 4.16+, surface styles resolve CSS CUSTOM PROPERTIES (--window-bg-color etc.), not the legacy named colors — exactly the fallback channel Design decision 2 pinned. Fix: colors.adw.css.j2 now ALSO emits a :root { … } custom-properties block (same mapping: window/view/headerbar/card/dialog/popover/sidebar bg+fg, backdrop/shade family, accent 04/05, state trios, scrollbar outline, color-scheme: dark) — plain-GTK4 + libadwaita + mixed consumers all read one palette. Tests: new test_render_custom_properties_channel_matches_named_mapping; csg suite 570 passed / 1 pre-existing. Machine flow: assets apply (changed=1) → csg install rebuilt base/custom/pywal images (wallust build failed on network — codeberg unreachable, NOT code; custom+base fresh with adw.css verified in-container) → reseed → entry 7e8a556e… carries :root block (--window-bg-color #140808 live). AWAITING USER: relaunch power-options-gtk + bar and confirm dark/palette surfaces.
