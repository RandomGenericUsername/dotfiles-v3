# preferences-notifier-theme

## Why

Spine **AD-12** makes settings a port: `Preferences.get(namespace, key,
fallback) → Accessor<T>`, where the **adapter owns the config file and the
`FileMonitor` lifecycle** and an absent file degrades to the fallback. Spine
**AD-11** makes notification a port: senders post `NotificationIntent`s and the
**provider routes** a transient intent to freedesktop `Notify` and a keyed/
progress intent to the event-card path; senders never construct a freedesktop
call. Spine **AD-13** makes theme a port: a `Theme` adapter applies the palette
(`colors.gtk.css`), and every app routes theming through it. Doc 101 §4.5/§4.6
define the `Notifier`/`Preferences` shapes; §4.7 carries them on `BarContext`;
§13 step 7 is this step ("Preferences + Notifier — extract the capture config
adapter; route senders through `Notifier`").

Today all three seams are absent, and the pre-port reality has the exact defects
the ports fix:

- `bar/widgets/recording.tsx` reads the capture-tool config **directly** and
  holds its `Gio.FileMonitor` at **module scope** — the GC trap AD-12 names.
- `services/bluetooth-service.ts` constructs a freedesktop `Notify` call
  **directly** (`org.freedesktop.Notifications`), so a sender knows the wire.
- `app.tsx` applies the palette with a **direct `app.apply_css`** call, which
  AD-13 forbids.
- The three byte-identical `theme.ts` copies live under `src/gui-tools/**`.

Evidence:
`grep -n "captureConfigMonitor\|bar_compact_controls\|monitor_file" dotfiles/config/ags/bar/widgets/recording.tsx`
→ `21:const CAPTURE_CONFIG = …/capture-tool/config.json`, `39:return raw.bar_compact_controls === true`,
`49:let captureConfigMonitor: Gio.FileMonitor | null = null`,
`75:captureConfigMonitor = Gio.File.new_for_path(CAPTURE_CONFIG).monitor_file(`;
`grep -n '"Notify"' dotfiles/config/ags/services/bluetooth-service.ts` → `733: "Notify",`;
`grep -n "apply_css" dotfiles/config/ags/app.tsx` → `138:` (colors.css) and `149:` (audio-panel.css);
`ls src/gui-tools/*/lib/theme.ts` → 3 files.

Verify:
`grep -n "captureConfigMonitor\|bar_compact_controls\|monitor_file" dotfiles/config/ags/bar/widgets/recording.tsx`;
`grep -n '"Notify"' dotfiles/config/ags/services/bluetooth-service.ts`;
`grep -n "apply_css" dotfiles/config/ags/app.tsx`;
`ls src/gui-tools/*/lib/theme.ts`.

## What Changes

### The three platform ports (AD-11, AD-12, AD-13)

- New `platform/preferences.ts`: the `Preferences` port
  (`get<T>(namespace, key, fallback): ReadAccessor<T>`), the injected
  `PreferencesSource` I/O seam, and the pure `createPreferences` core that owns
  the per-namespace watch lifecycle and degrades to the fallback. No `gi://`, no
  `ags`.
- New `platform/notifier.ts`: `NotificationIntent`, the `Notifier` port
  (`post`/`dismiss`), the injected `NotifierSinks` seam, and the pure
  `createNotifier` router: **transient** intent → `notify` sink (freedesktop),
  **keyed/progress** intent → `card` sink (the event-card path). No `gi://`, no
  `ags`.
- New `platform/theme.ts`: the `Theme` port (`apply()`), the injected `CssSink`
  seam, and the pure `createTheme` core. No `gi://`, no `ags`.

### The three adapters (the file + monitor lifecycle, the wire, the CSS)

- New `lib/preferences.ts`: the Gio `PreferencesSource` (`GLib.file_get_contents`
  + a per-namespace `Gio.FileMonitor` held in a map, **never** module scope) and
  the bound `preferences` instance built on the injected `agsRuntime`.
- New `lib/notifier.ts`: the freedesktop `Notify` transient sink (the call moved
  out of `bluetooth-service.ts` verbatim) plus the card sink seam, and the bound
  `notifier` instance.
- New `lib/theme.ts`: the `app.apply_css` `CssSink` (applies the stable
  `colors.css`, the pointer to the runtime's `colors.gtk.css` generation — F9
  says never cache the generation path) and the bound `theme` instance.

### The bar consumes the ports (no behaviour change)

- `bar/widgets/recording.tsx`: the `bar_compact_controls` read becomes
  `preferences.get("capture-tool", "bar_compact_controls", false)`; the
  module-scope monitor and `loadCompactControls` are deleted (the adapter owns
  them); a `createEffect` closes the popup when compact mode turns off.
- `services/bluetooth-service.ts`: `postBluetoothNotification` posts a transient
  `NotificationIntent`; the freedesktop call is gone from the sender.
- `app.tsx`: the palette `app.apply_css(colors.css)` becomes `theme.apply()`.
  The component stylesheet (`audio/audio-panel.css`) is not the palette and stays
  a direct apply.

### Tests prove the pure cores (fake file/monitor; fake notifier)

- New `tests/ts/preferences.test.ts`: a fake `PreferencesSource` (fake file +
  fake monitor) drives the real core — fallback when the file is absent, a
  reactive update when the monitor fires, one watch per namespace, and a
  namespace switch that does not re-watch.
- New `tests/ts/notifier.test.ts`: fake sinks capture intents — a transient
  intent reaches the `notify` sink and not the `card` sink; a keyed intent and a
  progress intent reach the `card` sink and not the `notify` sink; `dismiss`
  reaches the dismiss seam.

### One registered source (deploy manifest)

- `platform/preferences.ts`, `platform/notifier.ts`, `platform/theme.ts`,
  `lib/preferences.ts`, `lib/notifier.ts`, and `lib/theme.ts` are registered in
  `compositor_configs_skeleton_files` and mirrored in the verify role, so a fresh
  provision deploys them and `make deploy-coverage` stays green.

## Out of scope

- **The 3 app-local `theme.ts` copies.** `src/gui-tools/{notifications,
  wallpaper-selector,icon-color-mapping-editor}/lib/theme.ts` are the `ags-apps`
  epic's to migrate (AD-20 step 8); this change does not touch them.
- **The notifications app.** It stays a consumer/host; nothing under
  `src/gui-tools/notifications/` changes.
- **The generic keyed/progress card topic.** The contract has no generic
  notification-card topic (`known_topic_only`), and AD-22 forbids an app
  emitting domain state, so the bar's card sink is an injected seam; the
  transient route (the only sender the bar has) is wired for real.
- **`BarContext`.** Doc 101 §4.7 carries the ports on `BarContext`, but
  `BarContext` is not built yet; this change binds the ports to module clients
  exactly as `lib/event-bus.ts` binds the one event client.
- **Platform package extraction (AD-17/AD-20).** The ports land in-place under
  `dotfiles/config/ags/platform/`; the versioned unit is a later step.
- **Theme re-apply on `wallpaper.state`.** The bar applies the palette once at
  startup today; adding the AD-29 re-apply is future work (behaviour change).

## Impact

- New: `dotfiles/config/ags/platform/{preferences,notifier,theme}.ts`,
  `dotfiles/config/ags/lib/{preferences,notifier,theme}.ts`,
  `dotfiles/config/ags/tests/ts/{preferences,notifier}.test.ts`.
- Edited: `dotfiles/config/ags/bar/widgets/recording.tsx`,
  `dotfiles/config/ags/services/bluetooth-service.ts`,
  `dotfiles/config/ags/app.tsx`,
  `dotfiles/config/ags/tests/tsconfig.tests.json`,
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml`,
  `src/provisioning/tests/unit/test_compositor_configs_role.py`,
  `src/provisioning/tests/unit/test_verify_role.py`.
- No behaviour change on a provisioned host: the freedesktop call, the config
  read/watch, and the palette application are the same operations, moved behind
  ports.
