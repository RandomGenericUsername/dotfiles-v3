# 105 — Appearance plane v2 (RFC)

> **Status:** RFC / architecture ticket, 2026-11-06. This page is the design
> record for the v2 appearance plane. It does **not** bump a composition pin and
> does **not** change a live host. The normative vocabulary will be
> `contracts` `v0.7.0`; the implementation lives in the pinned repos and lands
> in the waves below.
>
> v1 is [`docs/104-skin-plane-composition.md`](./104-skin-plane-composition.md).
> This RFC keeps the v1 boundary that a skin is appearance, never structure; it
> replaces the v1 artifact/refresh/supervision mechanics.

## 0. Decisions (frozen)

1. **One Appearance plane.** Palette and skin stop being two artifacts, two
   providers, two watches and two apply paths. The runtime publishes one
   composed **appearance generation**; a consumer gets one provider, one
   monitored pointer and one refresh handler.
2. **Token model v2.** Appearance is expressed as
   `surface.{panel,card,cell,control,pill}`, `state.{hover,selected,focus,disabled}`,
   a type scale, `ink`, `layout.<app>` and `mode.dark/light`. There is **no
   `structure` group**; structure remains app-owned.
3. **Always-on apps are systemd `--user` units.** The bar and notifications are
   supervised. On-demand apps keep their launchers.
4. **No v1.1 hotfix.** Live apps need a restart until v2 ships. The extra
   provider/watch is not patched into v1; the fix is the v2 cutover.

## 1. Findings and evidence

### 1.1 Hot skin reload is broken for every consumer

The v1 consumer chain is:

```text
config/<configDir>/skin.css  ->  current/skins/<configDir>.css  ->  cache/skins/<hash>/<configDir>.css
        (stable first hop)            (repointed second hop)
```

`ags-platform` watches the **stable first hop**:

- `adapters/skin.ts:9-11` — “Only the CSS pointer is app-scoped
  (`$XDG_CONFIG_HOME/<configDir>/skin.css`)”.
- `adapters/skin.ts:140-143` — the monitor is created on that path with
  `Gio.FileMonitorFlags.WATCH_MOVES`.
- `adapters/skin.ts:202-207` — `createAppSkin()` resolves
  `$XDG_CONFIG_HOME/<configDir>/skin.css`.

The runtime repoints the **second hop**, not the first:

- `dotfiles-runtime/src/runtime/adapters/seeder.py:759-775` — each skin artifact
  becomes a `current/skins/<artifact>` symlink, and `current/skin.json` is
  repointed as `skin.json`.
- `seeder.py:779-808` — consumer pointers are `config/<configDir>/skin.css ->
  current/skins/<configDir>.css`; the seeder does not repoint the first hop on a
  skin change.

A `Gio.FileMonitor` on a symlink reports events for the symlink entry itself;
it does not follow the link and report a repoint of the target link. So a
running app sees **no event** when `current/skins/<configDir>.css` is replaced.
The palette works only because `Theme` watches the repointed hop directly:

- `ags-platform/adapters/theme.ts:45-46` — `PALETTE_YAML` is
  `$XDG_STATE_HOME/dotfiles/current/colors.yaml`.
- `theme.ts:135-141` — the one `Theme` monitor is bound to that path.

Even if the skin event reached the app, the app-level refresh path does not
re-apply the skin. The existing `palette-refresh` work re-applies only the
palette (plus app-specific derived work):

- `ags-notifications/app.tsx:62-65` — handler calls `theme.apply()` and
  `refreshNotificationCardIcons()`.
- `ags-notifications/lib/palette-refresh.ts` — wraps
  `createPaletteRefreshHandler` around `lib/appearance.ts`; the injected
  `apply` is the palette/icon path, not `skin.apply()`.
- The same shape is in `ags-clipboard/lib/appearance.ts:46-49` and the other
  live apps: clear caches / rebuild icons / rebuild cards, but no appearance
  provider swap.

`theme.apply()` also owns a **second** provider. A skin change cannot be
correct while two providers exist (see §3.1).

### 1.2 Stale AGS instances are unsupervised

Always-on apps are raw `ags run` processes; the composition list marks them
`launch: always` but there is no unit:

- `dotfiles/provisioning/apps.yaml:32-59` — bar (`instance: ags`) and
  notifications (`instance: notifications`) are `launch: always`; the other
  five are `launch: on-demand`.
- The pinned provisioning role installs links, launchers, autostart and starts
  through `ags-run-locked`; it does not install `systemd --user` units
  (`dotfiles-provision ansible/roles/ags_apps_units/tasks/_one.yml`).
- Login starts are assets-owned autostart lines, not units
  (`ags_apps_units/tasks/_verify_surfaces.yml:68-104`).

The runtime’s restart lane is careful but is **not supervision**. It quits by
D-Bus name, waits for release, then relaunches and verifies the name:

- `dotfiles-runtime/src/runtime/adapters/ags_reloader.py:25-40` — documented
  quit → wait → launch → name-verify procedure.
- `ags_reloader.py:530-603` — `ags quit -i <instance>`, bounded release wait,
  then detached `ags run`.
- `ags_reloader.py:621-634` — release is name + known wrapper pid.

That protects a restart from racing a live name. It does nothing when nothing
is running, when the `ags run` parent is killed, or when a `gjs` child survives
without its wrapper. The investigation found exactly that: a killed `ags run`
parent left a `gjs` child owning `org.freedesktop.Notifications` until
`ags quit -i notifications`; a raw process tree has no supervisor to notice.

### 1.3 The v1 workaround ledger

These are in the v1 data/templates/apps and are the reason the token model
changes, not merely the artifact path:

| v1 workaround | Evidence | v2 answer |
| --- | --- | --- |
| Global `border-w` + `hairline-w` cannot express per-role borders | `dotfiles-assets/skins/README.md:127-170`; `templates/ags.gtk.css.j2:15-22` | `surface.<role>.border` per surface role |
| Hover/selected/disabled are template literals | `templates/ags.gtk.css.j2` hover rules; capture `.bar-pill.selected` | first-class `state.*` tokens |
| Small type/paddings are template literals | `skins/README.md:140-151` | type scale + per-surface padding/typography |
| Clipboard derives contrast from parsed hex/luminance | `ags-clipboard/ui/ItemCard.tsx:111-147` | explicit `ink` / `ink.on-*` tokens; no app math |
| Layout tokens are bar-only | `skins/README.md:16-19`; manifests under `[layout]` | `layout.<app>.<token>` |
| `paper` is palette-mode dependent | `skins/README.md:172-186` | `mode.dark` / `mode.light` overrides in the skin |

## 2. Artifact interface

### 2.1 Layout

The runtime publishes **one immutable generation directory** and repoints
**one stable pointer**:

```text
$XDG_STATE_HOME/dotfiles/
  cache/appearance/<appearance-hash>/
    appearance.json          # manifest: hash, mode, palette/skin identity, artifact digests
    colors.yaml              # typed palette (one source of palette truth)
    tokens.json              # resolved v2 token tree
    ags.css                  # expanded bar skin CSS
    ags-notifications.css    # expanded notifications skin CSS
    ...                      # one <configDir>.css per target
  current/appearance -> cache/appearance/<appearance-hash>/

<install>/config/<configDir>/appearance.css -> current/appearance/<configDir>.css
$XDG_CONFIG_HOME/<configDir> -> <install>/config/<configDir>    # existing spine/XDG link
```

`current/appearance` is the **only monitored pointer**. The convenience
`config/<configDir>/appearance.css` is a static link into the current
generation; it is a read path, not a watch path. The runtime owns both the
generation directory and the `current/appearance` repoint; provisioning only
guarantees the config dir and its existing XDG/spine links.

### 2.2 `appearance.json`

```json
{
  "schemaVersion": 2,
  "appearanceHash": "<sha256>",
  "mode": "dark",
  "palette": { "entryHash": "<sha256>", "name": "<producer>" },
  "skin": { "entryHash": "<sha256>", "name": "glass" },
  "artifacts": {
    "colors.yaml": "<sha256>",
    "tokens.json": "<sha256>",
    "ags.css": "<sha256>",
    "ags-notifications.css": "<sha256>"
  },
  "configDirs": ["ags", "ags-notifications", "ags-capture", "..."]
}
```

The directory name **is** the appearance hash. The manifest is the
self-check: consumers verify the digests they read (or the runtime verifies
before repointing) and fail closed on a mismatch. `configDirs` is the only
app-list input; the platform still has no app list.

### 2.3 Hash and publication

```text
appearanceHash = sha256(canonical-json {
  schemaVersion: 2,
  paletteHash: <palette entry hash>,
  skinHash: <skin entry hash>,
  mode: "dark" | "light"
})
```

The hash is intentionally `f(palette, skin, mode)`. Effects/icons are content
layers, not appearance layers; see O-3 in §8. The runtime must:

1. build the whole generation under a staging path;
2. hash every artifact and write `appearance.json` last;
3. atomically rename staging → `cache/appearance/<hash>/`;
4. atomically repoint `current/appearance` (temp symlink + `rename(2)`);
5. keep the previous generation until prune (bounded keep + grace).

No partial generation is ever visible. A failed build leaves the old pointer
in place and the old provider installed.

### 2.4 Why one pointer, and why inotify then works

The v1 failure is structural: the watched entry and the repointed entry are
different links. A symlink’s target change updates the **second** link’s inode;
a monitor on the first link sees nothing. v2 watches the entry the runtime
actually repoints:

- Consumers monitor `$XDG_STATE_HOME/dotfiles/current/appearance` (the symlink
  entry itself, or its parent directory for a `MOVED_TO` event).
- A repoint produces one `MOVED_TO` / `RENAMED` event on that entry; the
  50 ms debounce collapses the burst of one atomic repoint.
- On the event, the consumer re-reads `appearance.json`, `tokens.json`,
  `colors.yaml` and its convenience CSS path through the new pointer.
- Reading the **path** rather than the resolved inode is what prevents a stale
  read; the runtime never writes through the pointer.

This gives one event source for palette, skin and tokens. There is no chain of
per-artifact symlinks to watch and no second pointer that can move unseen.

## 3. Provider and refresh

### 3.1 One provider, one monitor, one apply

The platform exposes **one** Appearance adapter. It replaces the v1
`Theme` + `Skin` pair:

- exactly one `Gtk.CssProvider` per app;
- the sheet is the palette role block (rendered from `colors.yaml`, including
  the legacy `@color_*` aliases needed by existing GTK widgets) followed by the
  expanded `<configDir>.css`;
- priority is `GTK_STYLE_PROVIDER_PRIORITY_USER` (800);
- the provider is installed **last**, and every swap adds the new provider
  before removing the previous one (the existing replacing-sink rule;
  `ags-platform/ports/theme.ts` and `ports/skin.ts`);
- exactly one `Gio.FileMonitor` on `current/appearance` per app process, shared
  by all subscribers and retained against GC;
- exactly one apply path: `appearance.apply()` reads the current generation,
  composes, and swaps the provider. Apps no longer call `theme.apply()` and
  `skin.apply()` as two operations.

The bar is still a **restart-lane** app. It has no `palette-refresh` handler;
a bar appearance change is a supervised restart (see §4). The restart lane is
the only place where “restart the bar” remains correct.

> **Implementation constraint (found while writing this RFC):** the bar
> currently calls `app.apply_css($XDG_CONFIG_HOME/ags/audio/audio-panel.css)`
> **after** `skin.apply()` (`ags-bar/app.tsx:147-156`). That installs a second
> USER-priority provider after the appearance provider, violating “appearance
> installed last”. v2 must either compose that sheet into the appearance
> generation or apply it before `appearance.apply()`; it must not remain a
> post-appearance provider.

### 3.2 Refresh transport

Keep the existing transport. The runtime already invokes
`ags request palette-refresh <appearance-hash> -i <instance>`
(`dotfiles-runtime/src/runtime/adapters/ags_app_refresh.py:588-598`), and the
platform helper enforces hash idempotence.

What changes is the **handler contract**:

```ts
const appearanceRefresh = createAppearanceRefreshHandler(() => {
  appearance.apply()        // re-read current/appearance, compose, swap provider
  refreshDerivedSurfaces()  // only app-owned derived work (icons, raster caches)
})
```

- The platform handler re-applies the **whole appearance**; an app must not
  need to know whether the change was palette, skin or mode.
- App code keeps only genuinely derived work. `theme.apply()` disappears from
  handlers; `skin.apply()` disappears from startup/handlers.
- The handler is idempotent by appearance hash, as today. A failed apply does
  not advance the hash, so the runtime retries.
- The runtime's ledger and live/restart lanes stay; the bar remains in the
  restart lane.

### 3.3 Mode

`appearance.json.mode` records the mode that produced the generation. The
provider is mode-complete: `tokens.json` already contains the resolved
`mode.dark`/`mode.light` branch, so a mode change is an appearance-hash change,
not an application-side CSS media query. The exact selector (desired override
vs the palette producer’s projected mode) is open question O-2; whatever wins
must be recorded in the manifest so the hash is stable and debuggable.

## 4. Supervision

### 4.1 Units

| App | Unit | Instance | Config dir | Start | Stop |
| --- | --- | --- | --- | --- | --- |
| bar | `dotfiles-ags-bar.service` | `ags` | `ags` | shared launch lock | `ags quit -i ags` |
| notifications | `dotfiles-ags-notifications.service` | `notifications` | `ags-notifications` | shared launch lock | `ags quit -i notifications` |

Both are `systemd --user` units with:

```ini
[Unit]
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/ags-run-locked --exec --expect-instance <instance> -d <configDir>
ExecStop=%h/.local/bin/ags quit -i <instance>
Restart=on-failure
RestartSec=2
TimeoutStopSec=10
KillMode=mixed

[Install]
WantedBy=graphical-session.target
```

`ags-run-locked` gains an `--exec` mode for units: acquire the shared launch
lock, then `exec ags run …` in the foreground so systemd tracks the real
process; the existing background/register-and-exit behavior stays for
provisioning and on-demand launchers. The unit must never background
`ExecStart`.

`Restart=on-failure` is the frozen policy. A clean `systemctl --user stop`
does not restart; a crash, a non-zero exit, or a failed startup does.

### 4.2 The rule: never kill the `ags run` parent

AGS `ags run` is a wrapper around a `gjs` child that owns the D-Bus name
(including `org.freedesktop.Notifications`). Killing the wrapper can leave the
child owning the name with no supervisor. Therefore:

- stop/restart through `ags quit -i <instance>` (graceful D-Bus quit) or
  `systemctl --user stop/restart <unit>` (which runs `ExecStop`);
- never `kill`, `kill -9`, `pkill`, or a raw process-tree kill on the `ags run`
  parent from scripts, doctor repair or operators;
- if a wrapper is orphaned, quit its instance by name and let systemd reap the
  unit; if a `gjs` child is orphaned without a unit, `ags quit -i` still targets
  the name, then the owner is re-checked.

### 4.3 Doctor

`dotfiles-runtime doctor` grows an appearance/supervision leg (read-only, with
`--repair` limited to `systemctl --user restart` / `ags quit -i`):

- **unit state** — `systemctl --user is-active` and `show -p MainPID` for both
  always-on units;
- **unit PID sanity** — `MainPID` is alive and is the process the unit started;
- **bus owner** — `GetNameOwner("org.freedesktop.Notifications")` resolves to a
  pid inside the notifications unit’s cgroup; the bar’s `ags` instance is on the
  AGS bus;
- **orphans** — any `ags run`/`gjs` process not in an always-on unit cgroup and
  not an on-demand launcher child is reported; a name owned without a unit is a
  failure;
- **pointer sanity** — `current/appearance` resolves to the recorded
  generation; each `config/<configDir>/appearance.css` resolves inside it.

The doctor reports, never silently kills. Repair uses the same graceful stop
rule as §4.2.

## 5. Token model v2

### 5.1 Shape

```jsonc
{
  "schemaVersion": 2,
  "surface": {
    "panel":   { "bg": "...", "border": {"width": 1.5, "color": "@primary"},
                 "radius": 12, "padding": "11px", "shadow": "none", "blur": "none" },
    "card":    { "bg": "...", "border": {"width": 1, "color": "..."}, "radius": 9,
                 "padding": "10px 11px", "shadow": "none", "blur": "none" },
    "cell":    { "bg": "transparent", "border": "none", "radius": 7,
                 "padding": "8px 9px" },
    "control": { "bg": "...", "border": {"width": 1, "color": "..."}, "radius": 7,
                 "padding": "4px 8px" },
    "pill":    { "bg": "...", "border": {"width": 1, "color": "..."}, "radius": 20,
                 "padding": "2px 6px" }
  },
  "state": {
    "hover":    { "bg": "...", "border": "...", "ink": "..." },
    "selected": { "bg": "...", "border": "...", "ink": "..." },
    "focus":    { "outline": "2px @primary", "outline-offset": 1 },
    "disabled": { "opacity": 0.45, "ink": "..." }
  },
  "type": {
    "title":   { "size": 12.5, "weight": 600 },
    "body":    { "size": 13, "weight": 400 },
    "label":   { "size": 11, "weight": 600 },
    "caption": { "size": 10.5, "weight": 400 }
  },
  "ink": {
    "primary": "@on_surface",
    "dim": "alpha(@on_surface, 0.62)",
    "accent": "@primary",
    "over": "auto",
    "disabled": "alpha(@on_surface, 0.38)",
    "on-image": "@on_primary",
    "on-busy": "@on_primary_container"
  },
  "layout": {
    "ags": { "panel-width": 312, "list-spacing": 4, "row-height": 0, "chip-min": 0 },
    "ags-capture": { "bar-height": 52 },
    "ags-notifications": { "card-width": 360 }
  },
  "mode": {
    "dark":  { /* token overrides for dark, including paper's dark branch */ },
    "light": { /* token overrides for light, including paper's light branch */ }
  }
}
```

Rules:

- **No `structure` group.** `layout.<app>` is a metric namespace, not a layout
  tree. Tokens never describe presence, ordering or variants.
- **Per-role borders.** Every surface owns its border width/color/style. There
  is no global `border-w`/`hairline-w`; a role that has no border says
  `border: "none"` (the cell does, deliberately, because a transparent border
  changes allocated height — the v1 finding stays true).
- **State is first-class.** Hover/selected/focus/disabled are token sets, not
  hand-written CSS rules. A surface consumes `surface.<role>` plus
  `state.<state>`; the template renders the combination.
- **The type scale is first-class.** Small component type (`label`, `caption`)
  and per-surface typography/padding are tokens, not templates. This removes
  the v1 literal table.
- **`ink.on-*` is explicit.** The clipboard no longer parses hex and computes
  luminance; the skin supplies the ink for image/busy/colored headers. App
  contrast math is deleted, not ported.
- **`layout.<app>` replaces the bar-only four.** Each app reads its own
  namespace through `createAppearanceValue("layout.<app>.<token>", fallback)`;
  the bar keeps its accessor shape.
- **`mode.*` is mode-aware.** A skin may define different values per mode;
  `paper` can be a real light paper in light mode and a deliberate dark paper
  in dark mode. It no longer depends on “whatever mode the palette happened to
  be”.
- **No literal hex.** Palette roles and role expressions remain the only color
  atoms; the vocabularies and fail-closed validation rules of v1 carry over.

### 5.2 Compatibility mapping (for the migration, not the final model)

| v1 | v2 |
| --- | --- |
| `shape.border-w` | `surface.panel.border.width` (and per-role borders) |
| `shape.hairline-w` | `surface.card.border.width`, `surface.control.border.width`, `surface.pill.border.width` |
| `shape.radius-*` | `surface.<role>.radius` |
| `surface.bg-panel` / `bg-card` | `surface.panel.bg` / `surface.card.bg` |
| `surface.border` | each `surface.<role>.border.color` |
| `surface.shadow` / `blur` | each `surface.<role>.shadow` / `.blur` |
| `ink.ink` / `ink-dim` / `accent` | `ink.primary` / `ink.dim` / `ink.accent` |
| `ink.ink-over` | `ink.over` |
| `type.title-size` / `text-size` | `type.title` / `type.body` |
| `rhythm.cell-pad` | `surface.cell.padding` |
| `layout.panel-width` … | `layout.ags.panel-width` … |

v1 manifests are not silently reinterpreted. The runtime either expands a v2
manifest or keeps a v1 generation; it never mixes a v1 token map with a v2
artifact directory.

## 6. Migration waves

Each wave is a separate repo ticket and release; the composition consumes the
tag only after the wave is green. **This RFC bumps no pin.**

| Wave | Repo | Deliverable | Exit gate |
| --- | --- | --- | --- |
| 0 | `contracts` | `v0.7.0`: appearance artifact interface, token model v2 (`surface`/`state`/`type`/`ink`/`layout.<app>`/`mode`), appearance-hash definition, fail-closed rules | contracts schema/tests; consumers vendor the canonical schemas |
| 1 | `dotfiles-runtime` | appearance generation: `cache/appearance/<hash>/`, `appearance.json`, `current/appearance`, one hop, prune/grace, hash `f(palette,skin,mode)` | runtime tests, hermetic, doctor pointer checks |
| 2 | `ags-platform` | one Appearance port/adapter: one provider 800, one monitor on `current/appearance`, one apply, refresh handler re-applies whole appearance; deprecate the split Theme/Skin path | platform tests, conformance fixtures |
| 3 | `dotfiles-assets` | v2 manifests/templates: `glass`, `flat`, `paper` converted, mode-aware, per-role borders/states/type; no literal workaround table | skins validation through every mode/template |
| 4 | seven `ags-*` apps | migrate to `appearance.apply()` and the v2 tokens; delete clipboard contrast math and template literals; bar keeps restart lane but stops the post-appearance `audio-panel.css` provider | each app's typecheck/domain tests; visual parity record |
| 5 | `dotfiles-provision` | install the two `systemd --user` units, extend `ags-run-locked` with `--exec`, wire unit enable/start/stop, doctor unit/bus/orphan checks | provisioning unit tests, verify role, no duplicate instances |
| 6 | `dotfiles-v3` | tuple bump: `contracts v0.7.0`, platform/runtime/assets/apps/provision tags, docs 105 flips to live | `make ci-gates-parity`, `make deploy-coverage`, app/tuple gates |

Dependency order is strict for 0 → 1 → 2 → 3 → 4 → 6; wave 5 can start after
wave 2 because units only need the existing `ags quit`/launch semantics, but
it must land before the tuple bump. Until wave 6, v1 remains live and running
apps keep their v1 behavior; the accepted user-facing state is “restart to see
a skin change”.

## 7. Acceptance

Run on a live host with **all seven apps open** (`ags list` shows
`ags`, `notifications`, `capture`, `clipboard`, `wallpaper-selector`,
`icon-color-mapping-editor`, `btop-theme-studio`):

1. **Hot skin change, no restart.** Record the pid of each live app; change
   `desired.json` `skin` (for example `glass` → `flat`) and reconcile. Every
   live app repaints (screenshot/pixel diff changes in the panel/card/control
   surfaces) while each pid is unchanged. The runtime output shows one
   `palette-refresh` per live app with a new appearance hash.
2. **Palette change, no restart.** Change the wallpaper/palette and repeat;
   the same apps repaint, including the clipboard headers whose contrast is now
   a token (no luminance math).
3. **Bar restart lane.** The bar changes only through the serialized restart:
   its pid changes, the new `ags` instance registers, and no duplicate bar
   appears. The runtime records `applied` for the restart lane.
4. **No orphan instances.** `systemctl --user status dotfiles-ags-bar
   dotfiles-ags-notifications`, `ags list`, and the bus owner agree; killing a
   `gjs` child (not the `ags run` parent) makes `Restart=on-failure` restore
   the unit and the bus owner; `doctor` reports zero orphans.
5. **Fail closed.** A malformed `tokens.json` or CSS artifact leaves the old
   `current/appearance` pointer and the old provider in place; the app reports
   the error and keeps its previous appearance.
6. **Supervision rule.** `systemctl --user stop dotfiles-ags-notifications`
   runs `ExecStop=ags quit -i notifications`; the bus name is released
   gracefully. No script or doctor repair kills the `ags run` parent.

## 8. Risks and open questions

| Id | Risk / question | Why it matters | Proposed handling |
| --- | --- | --- | --- |
| R-1 | **Appearance cache invalidation on wallpaper change.** A wallpaper may change the palette, effects and icons at different times; if the pointer is repointed before all inputs settle, apps can flash an intermediate appearance. | The acceptance is a single visible repoint, not a sequence of half-generated states. | Build the generation only after palette/skin/mode are final; one pointer repoint at the end; keep the previous generation until the next successful one. |
| R-2 | **Mode selection source.** `desired.json` may choose a mode while the palette producer projects another; a mode flip can change every token. | The hash includes mode, so an unstable selector causes refresh loops. | Record the winning mode in `appearance.json`; define precedence in contracts v0.7.0; add a doctor check for manifest mode vs palette metadata. |
| R-3 | **v1 compatibility window.** Apps, assets and runtime release on different dates; both `current/skins` and `current/appearance` may exist. | A consumer must never install two providers or read a v1 token map as v2. | Version the artifact (`schemaVersion: 2`) and make consumers select by manifest; keep v1 frozen during the window; remove v1 pointers only after the tuple bump. |
| R-4 | **Provider ordering in the bar.** `audio-panel.css` is applied after the skin today. | The “appearance installed last” invariant is already false in one app; a v2 swap would lose to the audio sheet. | Fold it into the appearance CSS or apply it before `appearance.apply()`; add an app conformance check. |
| R-5 | **Dropping effects/icons from the appearance hash.** The frozen hash is `f(palette,skin,mode)`, but icons/effects can still change. | Icon-only changes would no longer trigger a refresh. | Keep a separate content/icon refresh signal; do not silently fold it back into the appearance hash. |
| R-6 | **Systemd user-session availability.** Provisioning can run without a live `systemctl --user`/graphical session. | A hard unit enable would make provisioning brittle; a silent skip would hide a dead bar. | Follow the existing runtime-unit discipline (`failed_when: false` on session commands) and make `verify`/doctor the loud check. |
| R-7 | **Restart gap for notifications.** A restart releases `org.freedesktop.Notifications` for a short window. | Notifications sent in the gap are dropped. | Use `ExecStop=ags quit -i`, `Restart=on-failure`, and bounded `TimeoutStopSec`; doctor verifies the owner; the app already probes for a foreign owner. |
| R-8 | **Generation retention vs readers.** Pruning an old generation while a slow app is still reading it. | A consumer could read a dangling path. | Keep N generations plus a grace period; only prune older than the newest success; pointer reads are always re-resolved. |
| R-9 | **One monitor per app process, not per artifact.** | More monitors reintroduce the class of bug. | Platform conformance: one adapter instance, one monitor on `current/appearance`, one provider; tests assert no per-artifact watch. |
| R-10 | **`layout.<app>` namespace ownership.** An app could read another app's layout. | Layout becomes a shared back door. | The adapter only exposes the app's own namespace (configDir) plus explicit shared metrics; contracts reject unnamespaced layout. |
| R-11 | **Visual parity after conversion.** v2 templates remove the literal workarounds; glass must still match today. | The first v2 release should not be a redesign. | Keep the v1 parity fixture as the acceptance oracle for `glass`; generalised tokens must expand to the same measured values. |
| R-12 | **`paper` semantics change.** Making paper mode-aware is a behavior change from v1. | A user who selected paper in dark mode gets a different look. | Document the change; ship the v1-equivalent dark branch as the default, with the light branch only when the host selects light mode. |

## 9. What this ticket does not do

- No pin bump, no install, no deploy, no live-host mutation.
- No v1.1 provider/monitor hotfix. Running apps restart until v2.
- No structure tokens. The v1 boundary (“appearance, never structure”) is
  unchanged.
