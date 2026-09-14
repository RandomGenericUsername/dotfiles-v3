# AGS StatusNotifier (System Tray) — Investigation and Implementation

This document covers how the system tray actually works on this Wayland/Hyprland
(uwsm) desktop, what was implemented in the AGS bar, the crash modes found in
`libastal-tray`, and the deferred plan to replace the native menus with
AGS-generated UI.

It is the tray-focused companion to `ags_global_menu_investigation.md` (which
covers the separate, unrelated application global-menu problem).

---

## 1. Summary

- **Wayland has no native system tray.** The "tray" is the XDG
  **StatusNotifierItem (SNI)** D-Bus specification. Applications publish a
  `StatusNotifierItem`; a **watcher** owns `org.kde.StatusNotifierWatcher`; a
  **host** discovers items and renders them.
- Hyprland and uwsm are not involved beyond providing a healthy D-Bus session
  bus. The tray is a pure D-Bus concern.
- Originally this desktop had **no host at all**: the AGS `Tray` widget was a
  stub (it only rendered the recording indicator), `astal-tray` was not
  installed, and no watcher ran. Apps that "collapsed to tray" therefore had
  nowhere to render — the app appeared to just close.
- The bar now hosts the tray via `libastal-tray`, renders items, and can
  override per-app icons with runtime-generated palette SVGs.
- **Known limitation:** `libastal-tray`'s menu action group does not relay
  activations to the owning application, so SNI menus render and navigate but
  their actions are no-ops. Replacing the menus with AGS-generated UI is
  documented as deferred work (see §6).

---

## 2. How the tray works (background)

```text
Application (tidal, nm-applet, …)
    │  registers StatusNotifierItem on the session bus
    ▼
org.kde.StatusNotifierWatcher            ← owned by the AGS bar (libastal-tray)
    │  notifies hosts of registered items
    ▼
AGS bar Tray widget                       ← renders each item
    ├── left click  → item.Activate(x, y)
    └── right click → item's menu (best effort; see §5)
```

Key facts:

- The generic/legacy name `org.x.StatusNotifierWatcher` is merely
  **activatable** on this system via `xapp-sn-watcher` (from the `xapp`
  package). It renders nothing by itself. The real host is the AGS bar.
- A tray app that was already running when the watcher appears usually
  re-registers on its own (libappindicator/Electron watch the watcher name).
  If not, restart the app once.
- `libastal-tray` (`gi://AstalTray`) provides both the watcher and the host, so
  importing it in the bar makes the bar the tray host.

Useful diagnostics:

```sh
# who owns the tray watcher (expect the bar's gjs process)
busctl --user status org.kde.StatusNotifierWatcher

# registered SNI items
busctl --user get-property org.kde.StatusNotifierWatcher \
  /StatusNotifierWatcher org.kde.StatusNotifierWatcher \
  RegisteredStatusNotifierItems

# list candidate items/apps on the bus
busctl --user list | grep -iE 'StatusNotifierItem|tidal|nm-applet'
```

Observed values on this machine:

- `tidal-hifi` → `:1.x/org/chromium/StatusNotifierItem/1`, SNI `Id` =
  `tidal-hifi_status_icon_1`
- `nm-applet` → `:1.x/org/ayatana/NotificationItem/nm_applet`, SNI `Id` =
  `nm-applet`, `Title` = `Network`

---

## 3. Implementation

### 3.1 Files

| File | Role |
|---|---|
| `dotfiles/config/ags/lib/status-notifier.ts` | Tray singleton + crash-safe menu helper + item filters |
| `dotfiles/config/ags/bar/widgets/tray.tsx` | Renders SNI items, icon overrides, hide-network filter |
| `dotfiles/config/ags/bar/widgets/network.tsx` | Network widget; left = `wifitui`, right = nm-applet menu |
| `dotfiles/config/ags/bar/Bar.tsx` | Mounts `<Tray />` in the bar's end box |
| `dotfiles/config/ags/style.css` | `.bar-tray` / `.tray-item` styling |
| `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` | `tray` icon group (e.g. `tidal`) |
| `dotfiles/assets/icon-templates/status-bar/tray/tidal/default/icon.svg` | Tidal tray icon template |
| `src/provisioning/ansible/roles/packages/vars/arch.yml` | Adds `astal-tray` to `aur_packages` |
| `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` | Deploys `status-notifier.ts` + `tray.tsx` to the spine |

### 3.2 Behaviour

- **Item rendering is reactive**: `tray.get_items()` seeds a state that is
  refreshed on `item-added` / `item-removed`.
- **Left click** calls `item.activate(x, y)` (restores/activates the app).
- **Right click** attempts the item menu via the crash-safe helper (§4).
- **Icon override**: `TRAY_ICON_OVERRIDES` maps a StatusNotifier identity to an
  `icons.yaml` group/variant; if a runtime SVG resolves it is used, otherwise
  the item's native `gicon` / `icon-name` is used.
- **nm-applet is collapsed into the network widget**: `tray.tsx` filters it out
  (`isNetworkItem`) so the duplicate icon disappears; `network.tsx` attaches the
  right-click menu to the wifi icon. Left click keeps launching `wifitui`.

### 3.3 Tidal icon (runtime-generated)

The Tidal tray icon is produced by the normal icon pipeline:

1. Template: `dotfiles/assets/icon-templates/status-bar/tray/tidal/default/icon.svg`
   (palette placeholder `{{COLOR_FOREGROUND}}`, not a literal color).
2. Manifest group in `icons.yaml`:

   ```yaml
   tray:
     color_mappings:
       COLOR_FOREGROUND: color15
     variants:
       - name: tidal
         template: status-bar/tray/tidal/default/icon.svg
         output: tray-tidal.svg
   ```

3. Runtime renders it to `~/.local/state/dotfiles/current/icons/tray-tidal.svg`.
4. `registry.resolve("tray", "tidal")` returns it to the widget.

See `Adding an Icon — ITR and Provisioning Pipeline.md` §7.1 for the general
tray-override procedure.

---

## 4. Crash analysis and the menu helper

Two independent `libastal-tray` lifetime bugs were reproduced and worked around.

### 4.1 SEGV while rendering a menu

Binding a `Gtk.PopoverMenu` to the item's borrowed `menu-model` and keeping it
alive caused GTK to segfault later:

```text
#0 g_menu_item_get_attribute (libgio-2.0.so.0)
#1 libgtk-4.so.1
```

The item's model can be freed/replaced out from under GTK's popover.

### 4.2 GLib refcount underflow while activating a menu item

Inserting the item's own `action_group` into the popover and activating an item
produced a flood of:

```text
GLib-CRITICAL: g_atomic_ref_count_dec: assertion 'old_value > 0' failed
```

This corruption is what took the whole AGS process down when clicking a menu
entry ("the bar disappears").

### 4.3 The workaround (`lib/status-notifier.ts`)

`popupItemMenu(item, parent)` builds a **fresh popover per open** from data it
owns, and keeps nothing from `libastal-tray` after returning:

- **Private menu copy** — attributes (`label`, `action`, `target`, `icon`) and
  submenu/section links are copied manually into a new `Gio.Menu`. (`Gio.MenuItem.new_from_model`
  was avoided because it contributed to the refcount issues.)
- **Forwarding `SimpleActionGroup`** — each action from the item's group is
  mirrored into our own `Gio.SimpleAction` whose `activate` relays to
  `source.activate_action(name, parameter)`.
- **Lazy-menu wait** — calls `item.about_to_show()`, then waits for
  `notify::menu-model` (with a short timeout) because DBusMenu builds its
  layout lazily.

This stops the crashes. It does **not** make the actions work (§5).

---

## 5. Known limitation: SNI menu actions are no-ops

On this stack, selecting an SNI menu item does nothing:

- `TrayItem.action_group` is a local `Gio.SimpleActionGroup`; its activations do
  **not** reach the owning application. So nm-applet's "Connect"/"Disconnect"
  and the available-network entries are inert (submenus still navigate).
- Tidal's exported menu is Electron's **webview** menu (`Edit → Select All`,
  `Copy`, …), i.e. not a meaningful tray menu even if the relay worked.

Conclusion: the native SNI menu is a dead end for the apps that matter here.

---

## 6. Deferred: AGS-generated custom menus

**Decision (owner, 2026-09-13):** stop depending on the SNI menu for the apps we
care about and build the menus in AGS with real callbacks.

Planned shape:

- **Network widget right-click** — custom AGS popover:
  - Wi-Fi on/off (`nmcli radio wifi` / AstalNetwork),
  - live available-network list from
    `nmcli -t -f SSID,SIGNAL,SECURITY device wifi list`, click to connect
    (in-bar password entry for secured APs),
  - Disconnect,
  - launch `wifitui` / `nm-connection-editor`.
- **Tidal right-click** — custom AGS popover driven by MPRIS on
  `org.mpris.MediaPlayer2.tidal-hifi`: Play/Pause, Previous, Next, Show.
- **Unmapped tray apps** — keep the current SNI-menu attempt as a fallback.
- Open questions: password-prompt UX; whether to add a generic per-app custom
  menu registry in `status-notifier.ts`.

This is tracked in `_bmad-output/implementation-artifacts/deferred-work.md`
under "StatusNotifier tray custom menus (2026-09-13)".

For the general per-app procedure when a tray item's menu, activate, or icon is
broken/off-theme, see `docs/tray-app-integration-playbook.md`.

---

## 7. Deployment and validation

Provisioning (from the repo checkout/worktree; `bootstrap.sh` derives its root
from its own location):

```sh
./bootstrap.sh            # deploys AGS files, regenerates icons.json, re-seeds runtime, verifies
```

Per-change checks:

```sh
# manifest/template validity
itr list dotfiles/config/icon-template-color-scheme-mappings/icons.yaml \
  --icon tray --template-dir dotfiles/assets/icon-templates

# AGS syntax/bundling
cd dotfiles/config/ags && ags bundle app.tsx /tmp/ags-check.bundle.js --root .

# after provision: template, rendered icon, and generated manifest
ls ~/.local/share/dotfiles/icon-templates/status-bar/tray/tidal/default/icon.svg
grep -o 'fill="#[0-9a-fA-F]*"' ~/.local/state/dotfiles/current/icons/tray-tidal.svg
grep -A3 '"tray"' ~/.local/share/dotfiles/config/ags/icons.json
```

Restart only the bar after AGS changes:

```sh
ags list && ags quit && ags run
```

Runtime checks: the bar's `gjs` process should own
`org.kde.StatusNotifierWatcher`, and running tray apps should appear in
`RegisteredStatusNotifierItems`.

Commits on branch `feat/statusnotifier-tray`:

- `aff3a40` — StatusNotifier tray widget + tidal icon override
- `959e103` — crash-safe tray menus; merge nm-applet into network widget
- `52b40c6` — deferred-work note for custom AGS menus

---

## 8. Adding a new custom tray icon (quick reference)

1. Add the SVG under
   `dotfiles/assets/icon-templates/status-bar/tray/<app>/default/icon.svg`
   using palette placeholders (`{{COLOR_FOREGROUND}}`, …), never literal colors.
2. Add a `tray` variant in
   `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`
   (`name`, `template`, `output`).
3. Map the app's StatusNotifier identity to it in `TRAY_ICON_OVERRIDES` in
   `dotfiles/config/ags/bar/widgets/tray.tsx` (matched against `id` /
   `item-id` / `title`).
4. Run `./bootstrap.sh`, then restart the bar.

Nothing else is required: `icons.json` is generated from `icons.yaml` during
provisioning, and the runtime serves the rendered SVG through
`current/icons/`.
