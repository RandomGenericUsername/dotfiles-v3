# Tray (StatusNotifier) App Integration Playbook

A precedent document for a recurring class of problem on this desktop: an
application's tray item shows up, but its **menu and/or left-click do nothing**,
and/or its **icon does not match the theme**. This is expected on this stack,
and it has a repeatable resolution. Use this as the starting point for every
new tray app.

Companion docs:

- `docs/ags_tray_statusnotifier.md` — how the AGS tray works, the crash-safe
  menu helper, and the icon-override pipeline (§7.1 there covers adding a tray
  icon).
- `_bmad-output/implementation-artifacts/deferred-work.md` — the deferred
  "custom AGS menus" work item.

---

## 1. The symptom class

Any of these, for an app that registers a StatusNotifierItem:

- The icon renders, but **right-click shows an empty / irrelevant / no-op menu**.
- **Left-click does nothing** (the app does not activate / restore its window).
- The icon is **off-theme or the wrong size** (a vendor pixmap instead of a
  palette SVG).

Seen so far: Tidal (webview menu), nm-applet (menu, since fixed by merging),
Google Chrome (menu + activate + branding icon).

---

## 2. Why it happens

There is no native tray on Wayland. The tray is the XDG
**StatusNotifierItem (SNI)** D-Bus spec: apps publish an item, the AGS bar acts
as watcher+host (`libastal-tray`), and renders it.

Four independent reasons an item can be non-functional:

1. **libastal-tray does not relay activations.** `TrayItem.action_group` is a
   local `Gio.SimpleActionGroup`; activating an action from it does **not**
   reach the owning app. Result: menus open and navigate, but selecting an item
   is a no-op. (Using the group naively also crashes AGS — see the crash-safe
   helper in `lib/status-notifier.ts`.)
2. **`ItemIsMenu` semantics.** If `ItemIsMenu` is `false`, the app expects a
   left click to call `Activate`. If the app does not implement `Activate`, or
   the activation does not relay, **left-click is dead**.
3. **Chromium/Electron menus are not real tray menus.** These apps export
   `com.canonical.dbusmenu` at `/org/chromium/DbusMenu/<n>`, and on this stack
   `GetLayout` frequently fails even after `AboutToShow` — so there is nothing
   useful for a host to render. (Tidal additionally surfaces the webview menu:
   `Edit → Select All/Copy`, etc.)
4. **Icons are vendor pixmaps / icon-names**, not palette-aware SVGs, so they
   ignore the generated theme and the bar's sizing conventions.

---

## 3. The general solution: per-app override

For each tray app, choose any combination of four levers:

| Lever | What it does | Where |
|---|---|---|
| **Icon override** | Replace the native pixbuf with a runtime-generated palette SVG | `icons.yaml` `tray` group + `TRAY_ICON_OVERRIDES` in `bar/widgets/tray.tsx` |
| **Menu override** | Replace the SNI menu with an AGS-built popover with real callbacks | new AGS menu builder (deferred) |
| **Activate override** | Map left-click to a real action (e.g. focus the app's window) | `activate` override in the tray registry |
| **Hide + merge** | Drop the item and fold its affordance into an existing widget | `isNetworkItem`-style filter + a widget handler |

The key shift: **do not treat the SNI menu as a fallback we can rely on.** For
apps we care about, the native menu/activate is usually broken; the working
behavior is the one *we* build.

---

## 4. Triage procedure (per app)

1. Identify the item and its contract:

   ```sh
   busctl --user get-property org.kde.StatusNotifierWatcher \
     /StatusNotifierWatcher org.kde.StatusNotifierWatcher RegisteredStatusNotifierItems

   # for each "<bus>/<path>" returned (bus is before the first '/')
   busctl --user get-property <bus> <path> org.kde.StatusNotifierItem Id
   busctl --user get-property <bus> <path> org.kde.StatusNotifierItem Title
   busctl --user get-property <bus> <path> org.kde.StatusNotifierItem Menu
   busctl --user get-property <bus> <path> org.kde.StatusNotifierItem ItemIsMenu
   busctl --user get-property <bus> <path> org.kde.StatusNotifierItem IconName
   ```

2. Decide, using these rules:
   - `ItemIsMenu=false` and the app has a meaningful "restore/focus" → prefer an
     **activate override** (focus window) over a menu.
   - Menu needed and `Menu` is a Chromium/Electron DBusMenu whose `GetLayout`
     fails → **build a menu in AGS** (do not wait on libastal).
   - Vendor icon clashes with the theme → **icon override**.
   - The item duplicates a widget we already have (network, battery…) →
     **hide + merge**.
3. Implement via the override registry (§5).
4. Verify: icon renders, left-click does the intended thing, right-click menu
   works. Restart the bar (`ags quit && ags run`) — AGS bundles at startup.

---

## 5. The override registry (proposed shape)

Today `tray.tsx` holds a small `TRAY_ICON_OVERRIDES` map. The general shape we
want is one table per app:

```ts
type TrayOverride = {
  match: string                     // SNI identity substring (id/item-id/title)
  icon?: [group: string, variant: string]  // icons.yaml group/variant
  hidden?: boolean                  // skip rendering (merged into another widget)
  menu?: (item: TrayItem) => void   // AGS-built popover with real callbacks
  activate?: (item: TrayItem) => void // left-click handler
}
```

Current table (as implemented):

- `tidal` → `icon: ["tray", "tidal"]`.
- `nm-applet` → `hidden: true`, right-click handled by the network widget.

Planned additions: `chrome` (activate → focus window; optional menu/icon).

---

## 6. Worked example: Google Chrome

- SNI bus `org.freedesktop.StatusNotifierItem-<pid>-1`, path `/StatusNotifierItem`.
- `Id=chrome_status_icon_1`, `Title=""`, `ItemIsMenu=false`,
  `Menu=/org/chromium/DbusMenu/1`, `Category=ApplicationStatus`, `Status=Active`.
- `IconName` `Get` errors (it likely ships a pixmap); `Menu` `GetLayout` fails
  even after `AboutToShow` (Chromium menu not readable by this client).
- **Observed:** icon shows; left-click does nothing; right-click menu is useless.

Recommended override:

- **activate** → focus the Chrome window through Hyprland (window class
  `google-chrome`) instead of relying on SNI `Activate`.
- **menu** (optional) → an AGS popover with real actions (New window, New
  incognito window, focus) — or hide the item if the affordance is not worth it.
- **icon** (optional) → map to a `tray` variant if the branding pixmap clashes
  with the bar.

Rationale: with `ItemIsMenu=false`, the app's own contract is "activate", but the
relay is unreliable and Chromium's menu is unreadable — so both levers are ours.

---

## 7. Implications / planning notes

- **Menus are app-specific.** Each menu override is a small builder; there is no
  generic SNI menu we can fall back on for the useful cases. Budget for this.
- **Focus-window is the cheap win.** For most single-window apps, an activate
  override that focuses the app (Hyprland class/initial-class) covers the primary
  use; build a menu only when the app has meaningful actions.
- **Icon overrides ride the normal pipeline.** Add a `tray` group variant +
  `TRAY_ICON_OVERRIDES` entry and re-provision; see
  `docs/ags_tray_statusnotifier.md` §3.3 and §7.1.
- **Unmapped apps keep the current SNI attempt** (may be empty/odd). That is the
  accepted fallback until each app is evaluated.
- **The native menu helper is crash-safe but non-relaying.** It will not start
  working on its own; treat any "it might work for this app" as unverified until
  observed.

---

## 8. Quick reference

```sh
# inventory current tray items
busctl --user list | grep -iE 'StatusNotifierItem|NotificationItem'

# what the bar currently hosts
busctl --user status org.kde.StatusNotifierWatcher

# Chrome focus target (if using an activate override)
hyprctl clients -j | python3 -c "import sys,json;[print(c['address'],c['class']) for c in json.load(sys.stdin)]"
```
