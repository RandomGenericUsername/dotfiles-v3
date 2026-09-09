# GTK Theming Consumer — Working Change (cycle state, durable)

> **This is the durable working document for the `feat/gtk-theming-consumer`
> branch.** Anyone (human or agent) can pick the cycle up from here; nothing
> important lives only in a conversation. Complements, does not replace:
> `_bmad-output/planning-artifacts/epics-gtk-theming.md` (contract),
> `_bmad-output/planning-artifacts/gtk-theming-investigation.md` (analysis),
> `_bmad-output/implementation-artifacts/sprint-status.yaml` (story states),
> per-story files in `_bmad-output/implementation-artifacts/gt-*.md`.
> Branch: `feat/gtk-theming-consumer`, worktree
> `../dotfiles-repo-v3-gtk-theming`. Updated: 2026-09-08 (post `d6f3e43`).

## Why

The desktop's GTK surfaces never follow the wallpaper: GTK4/libadwaita apps
(bar buttons, menus, power-options-gtk, icme) rendered stock light Adwaita,
GTK3 apps were frozen on static Arc-Dark, and new shells read a stale
pre-Epic-4 palette. Investigation + epics live in the artifacts above.

## Current state (what is DONE — commits on this branch)

| Commit | What |
|---|---|
| `516f113` | Plan: investigation + epics gt-1..gt-4 + sprint-status gt-* keys |
| `58d9646` + `799ce86` | **gt-1-1 done** — csg `adw.css` format (named colors) |
| `90d59c8` + `47d23cb` | **gt-2-1 done** — palette artifact set grows to 5 (`colors.adw.css`, `colors.sequences`), meta-completeness migration guard |
| `dedeeb7` + `68d70ca` + `07ea6fd` | **gt-2-2 done** — `IConsumerPathSpec` declarative consumer pointers (ags, gtk-3.0, gtk-4.0); inspect status covers them |
| `9b87109` + `f60259c` + `81719f3` | **gt-2-3 done** — `TerminalColorApplier` reads `current/colors.sequences` artifact (parser retired) |
| `0d30dd4` | gt-3-1 story |
| `5ecb7e0` + `9e70ab8` + `104e11f` | **gt-3-1 done** — GTK config-in-spine: `config/gtk-{3,4}.0/`, migrate-then-symlink backup guard, `@import` skeletons, verify criteria |
| `d42e70b` + `4240246` | **gt-3-2 done** — `.zshrc` cats `current/colors.sequences`; `COLOR_SCHEME_OUTPUT_DIR` retired |
| `983e4dc` | **gt-4-1 pass 1** — style.css per-line reconciliation (decision table in story), adw fg-color gap (`popover/dialog_fg_color`) |
| `d6f3e43` | **gt-4-1 pass 2** — `:root { --… }` custom-properties channel in `colors.adw.css` (THE load-bearing fix: libadwaita ≥1.4 / GTK ≥4.16 Default theme resolve CSS variables, not named colors) |
| `ddcbf2b`, `fcb5614`, `4dd4a07` | housekeeping: story_location fix; gt-fix-1 test-isolation (no real desktop spawns from tests — after a test leaked a live bar); epic flips |

## BLOCKED ON: human visual confirmation (the only thing gt-4-1 needs)

After `d6f3e43` the machine is reseeded with the two-channel artifact
(entry `7e8a556e…`). The user must relaunch and confirm:

1. `power-options-gtk` → window/popovers dark + readable (libadwaita channel)
2. AGS bar relaunch → workspace pills no longer white (plain-GTK4 Default theme via variables)
3. Battery right-click popover → dark bg, readable text
4. `wallpaper set <other-img>` → relaunch → colors follow (NFR-5: relaunch-pickup is the model; running instances keep old colors — documented limitation)

If still light → next candidates: `--sidebar-backdrop-color`/`--shade-color`
gaps, or `color-scheme` enforcement; investigate via
`GTK_DEBUG=interactive power-options-gtk` (inspector CSS tab).

## NEXT STEPS (in order)

1. **Human confirmation** of the checklist above → record results in
   `_bmad-output/implementation-artifacts/gt-4-1-…md` Dev Agent Record
   (Verification checklist results table: replace `AWAITING HUMAN`).
2. **CR gt-4-1** (fresh context) → `done` in story + sprint-status.
3. **gt-4-2** (CS→DS→CR): docs + contract reconciliation —
   `shared-data-contract.md` (5-artifact set + ConsumerPointer table),
   `consumer-wiring.md` (GTK3/GTK4/icme/sequences chains + the two-channel
   mechanism), `docs/99`, ARCHITECTURE-SPINE AD-11 note, `cache-model.md`,
   stale `terminal_color_applier.py:61` docstring.
4. Then flip `gt-epic-4: done` and the GTK change is complete; merge the branch.
5. **Separate follow-up stories (NOT in gt-*):** stale-monitor repair
   (stored `eDP-1` vs live `eDP-2` — reconcile should diff `IMonitorSource`
   against stored monitors; blocks Hyprpaper reload on renamed outputs),
   terminal live-broadcast beyond the launching tty (P5 territory).

## Machine procedures (how to converge — from THIS worktree only)

```bash
# deploy csg templates (incl. adw) to the spine
cd src/provisioning && env ANSIBLE_CONFIG=$PWD/ansible/ansible.cfg \
  .venv/bin/ansible-playbook -i ansible/inventory/localhost.yaml \
  ansible/playbooks/assets.yaml -e install_dir=$HOME/.local/share/dotfiles -e os_family=arch

# land style.css / AGS config into the spine
… ansible/playbooks/compositor-configs.yaml (same invocation)

# reseed (regenerates the 5-artifact palette; template edits auto-invalidate)
#   NOTE: requires the container image to contain the new csg code:
csg install   # rebuilds csg-base/-custom/-pywal images (network needed; wallust build may fail offline — harmless)
env $SESSION_ENV uv run --directory src/runtime dotfiles-runtime wallpaper set \
  ~/.local/share/dotfiles/wallpapers/<img>
#   SESSION_ENV = WAYLAND_DISPLAY, XDG_RUNTIME_DIR, HYPRLAND_INSTANCE_SIGNATURE,
#   DISPLAY, DBUS_SESSION_BUS_ADDRESS extracted from any live session process
#   (e.g. /proc/$(pgrep -f 'ags run -d ~/.config/ags-icme')/environ)

# relaunch the bar (kill-first: orphan gjs children hold io.Astal.ags D-Bus name)
pkill -f "/usr/bin/ags run"; pkill -f "gjs -m /run/user/$UID/ags.js"  # then:
systemd-run --user --unit=ags-bar --setenv=WAYLAND_DISPLAY=… \
  --setenv=XDG_RUNTIME_DIR=… --setenv=HYPRLAND_INSTANCE_SIGNATURE=… \
  --setenv=XDG_STATE_HOME=$HOME/.local/state ags run
```

## Known hazards (learned the hard way — do not rediscover)

1. **Main-worktree provisioning runs clobber branch machine state** (old zshrc
   template, old runtime 3-artifact set, stale csg). Converge ONLY from this
   worktree; if a main bootstrap ran, re-run: assets + compositor-configs +
   zsh-config applies, `csg install`, reinstall `dotfiles-runtime`
   (`uv tool install --force --reinstall-package dotfiles-runtime --editable
   src/runtime`), reseed.
2. **Killing `ags` leaves an orphaned `gjs -m /run/user/$UID/ags.js` holding the
   `io.Astal.ags` D-Bus name** — a new `ags run` then dies with "instance 'ags'
   has no request handler implemented". Always kill the gjs orphan before relaunch.
3. **Launch the bar via `systemd-run --user` with session env** (systemd user
   manager inherits a clean env; bare shells lack the session vars; test
   processes leak pytest env otherwise — see gt-fix-1).
4. **Reload failures from a non-session shell are environmental**: `/dev/tty`
   absent (TerminalColorApplier), Hyprland instance env missing. Run the
   runtime from a process inside the session env (see SESSION_ENV above).
5. **Stored `current.json` monitors can go stale** (output renamed eDP-1→eDP-2)
   → HyprpaperReloader "Invalid monitor" on every reload. Deferred runtime
   story (see `_bmad-output/implementation-artifacts/deferred-work.md`).
6. **Container-mode csg needs image rebuilds after csg code changes**
   (`csg install`); the spine templates come from the assets role, not the image.
7. **`uv tool install --editable` for csg/dotfiles-runtime points the installed
   binaries at the repo checkout they were installed from** — reinstall from
   THIS worktree or the installed binary runs main's code.

## 2026-09-08 findings — libadwaita palette injection is DEAD upstream (empirical)

Controlled experiments (power-options-gtk, pixel-measured via grim+ImageMagick,
isolated `XDG_CONFIG_HOME` copies — all reproducible):

1. Our named-color chain (45 `@define-color`) loads + parses cleanly → window still `srgb(223,222,222)`.
2. Plano2 adw-colors reference theme (546 lines, both channels) → still white.
3. Pure-red override (`@define-color window_bg_color #ff0000` + `:root { --window-bg-color: #ff0000 }`) → still white.
4. Parser-error probe (`gtk.css:547 No property named "invalid"`) → **the file IS loaded and parsed**; its color declarations just lose the cascade.
5. `color-scheme: dark;` inside `:root` is INVALID GTK4 CSS ("No property named color-scheme") — removed from the template; GTK4 reads light/dark from the **`org.gnome.desktop.interface color-scheme` GSetting** only.
6. `gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'` → power-options-gtk renders **Adwaita dark** (`srgb(53,53,53)`).

**Conclusion:** libadwaita 1.9.3 resolves surface colors from its own compiled
stylesheet; user `gtk.css` overrides of named colors / `:root` variables are
loaded but never win the cascade on GTK 4.22.4. The wallpaper-palette
injection for libadwaita apps has **no supported CSS channel** on this stack
(adw-colors' mechanism is dead here; `ADW_COLOR_SCHEME`/gsettings control only
light-vs-dark Adwaita, not arbitrary colors).

**Decision point (user):** accept **dark-scheme for libadwaita surfaces**
(`prefer-dark`, wallpaper-derived accent still possible via the settings
portal accent-color channel — unverified) as the GTK4 consumer contract, with
the wallpaper palette fully reaching AGS (own CSS), GTK3 apps (gtk-3.0 named
colors — verify), terminal, icons; OR accept light/white status quo.
Runtime feature that follows from decision A: `ISystemColorSchemeSetter` —
reconcile computes palette background luminance and flips
`color-scheme prefer-dark/light` so GTK follows the wallpaper's tone.

## 2026-09-08 CORRECTION — the channel was never dead; `GTK_THEME=Adwaita:dark` was

Pass-2's "upstream killed user-CSS palette injection" conclusion was WRONG.
Continued investigation (user-directed internet research surfaced the GNOME
PSA that a stray `GTK_THEME` — even empty — breaks libadwaita styling):

- The session exported **`GTK_THEME=Adwaita:dark`** from the project's own
  `dotfiles/config/hypr/env-variables.lua:6` (Phase-1-era line). GTK_THEME
  forces the plain-GTK theme provider in place of libadwaita's stylesheet at
  a priority that beats ALL user-CSS declarations — every override
  (named colors AND `:root` variables) lost the cascade while it was set.
- Machine-verified: with `GTK_THEME` unset, a pure-red user-CSS override
  renders `srgb(255,0,0)` in power-options-gtk; with the runtime palette
  artifact live the same window renders the palette (`srgb(28,17,17)`
  titlebar ≈ `#140808` family). The two-channel `colors.adw.css` mechanism
  is FULLY ALIVE.
- Test-hygiene note: `cp -r ~/.config` preserves the `gtk-4.0` symlink, so
  writing the "isolated copy" wrote through into the spine — probe results
  in that window were from the real file. Spine restored via
  config-links re-apply (`@import "colors.css";` skeleton re-created).

Fix applied: the `GTK_THEME` line is REMOVED from `env-variables.lua`
(comment records the why). `gsettings color-scheme prefer-dark` stays as the
dark base; the wallpaper palette drives colors via `colors.adw.css`.
Follow-up runtime story (future): `ISystemColorSchemeSetter` — luminance-based
dark/light switch per wallpaper set.

## Correction protocol note

The durable doc previously stated "libadwaita user-css channel dead upstream".
Superseded by this section. Lesson: before concluding "unsupported upstream",
probe for env-var overrides (`GTK_THEME`) — the parser-error probe proved the
file was read; the missing red result was the env var, not the cascade.

## 2026-09-08 human verdict + AC closure

User visual verdict: "power options being colored two ways and it looks kinda
good" — tinted chrome CONFIRMED. Apps launched before re-login still inherit
`GTK_THEME=Adwaita:dark` (session env) → plain Adwaita-dark; the clean env
applies to all new sessions. User defers the re-login and approves proceeding.
Thunderbird (GTK3, own theme engine) recorded out of FR-7 scope.
gt-4-1 → done (caveats recorded in the story file).
