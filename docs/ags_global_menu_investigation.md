# Investigation results

Yes. I investigated this specifically for **a macOS-style global application menu on Hyprland**, with AGS as a possible UI layer.

## Short answer

**The project is feasible, but my earlier assumption that Hyprland supports the KDE AppMenu protocol was incorrect.**

The current evidence points to this:

- **AGS/Astal is absolutely suitable for building the bar UI.**
- **Hyprland does not currently expose KDE AppMenu as one of its supported protocols.**
- Therefore, we cannot rely on the clean Wayland-native pipeline I previously described:

```text
Application
    ↓
KDE AppMenu protocol
    ↓
Hyprland
    ↓
AGS
```

That architecture is **not currently available on Hyprland**.

However, there is a different architecture that looks genuinely promising.

---

# 1. What AGS actually gives us

Current AGS v3 is best understood as the TypeScript scaffolding layer around:

```text
GJS
 │
 ├── GTK
 │
 ├── Astal
 │     └── system/backend libraries
 │
 └── Gnim
       └── JSX UI
```

AGS can create layer-shell windows, buttons, popovers, dynamic widgets, react to system state, and communicate through GLib/GIO/D-Bus.

In other words, **building the visual global menu bar is not the problem**.

For example:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  ◉   Firefox   File   Edit   View   History       WiFi  🔊  🔋  18:42 │
└─────────────────────────────────────────────────────────────────────────┘
```

AGS can own and render this entire interface.

The hard part is this:

> How does AGS discover the menu belonging to the currently focused application and invoke its actions?

---

# 2. The Linux global-menu ecosystem is fragmented

There is no single universal API saying:

```text
give me the menu for the focused application
```

Instead, applications may expose menus through several mechanisms:

```text
                    Application
                         │
        ┌────────────────┼────────────────┐
        │                │                │
     GTK menu        DBusMenu        Wayland AppMenu
        │                │                │
   org.gtk.Menus   com.canonical      KDE protocol
                   .dbusmenu
```

The two D-Bus mechanisms are particularly important:

### GTK

```text
org.gtk.Menus
org.gtk.Actions
```

### Qt / Electron / other applications

```text
com.canonical.dbusmenu
```

These are the mechanisms we can potentially consume directly from our own shell. Existing global-menu implementations already do this.

---

# 3. The most interesting discovery: NovaBar

The closest existing project I found to what we want is **NovaBar**.

It is particularly relevant because it already implements:

```text
Focused application
        ↓
Global menu discovery
        ↓
GTK menus
        +
Canonical DBusMenu
        ↓
Panel
```

Its documented architecture supports:

- `org.gtk.Menus`
- `com.canonical.dbusmenu`
- an AppMenu Registrar
- focused-window tracking
- GTK application menu interception
- Wayland panel positioning

And it explicitly lists **Hyprland** among the supported wlroots-based compositors.

This is extremely valuable for our project.

Not because I think we should necessarily use NovaBar.

But because **we now have a working open-source reference implementation for the difficult part**.

---

# 4. The GTK interception approach

NovaBar uses:

```text
appmenu-gtk-module
```

The idea is roughly:

```text
GTK application
      │
      ▼
GtkMenuBar
      │
      ▼
appmenu-gtk-module
      │
      ├── exports menu through D-Bus
      │
      └── hides/intercepts the application's normal menu
               │
               ▼
          Global Menu
```

The relevant interfaces include:

```text
org.gtk.Menus
org.gtk.Actions
```

NovaBar documents that the module intercepts GTK menubars and exports them through D-Bus, while its panel reads and displays them.

This gives us a realistic way to support many GTK applications even without Hyprland implementing KDE AppMenu.

---

# 5. Qt / Electron / DBusMenu

Another important mechanism is:

```text
com.canonical.dbusmenu
```

This is already a known global-menu protocol used in the Linux ecosystem.

The Wayland KDE AppMenu protocol itself is interesting because it associates a `wl_surface` with a D-Bus menu:

```text
wl_surface
    │
    └── service name
            +
        object path
              │
              ▼
    com.canonical.dbusmenu
```

The protocol itself does not contain the menu. It tells the compositor where the D-Bus menu lives.

That is also why modern Chromium development and Firefox work around this architecture.

Chromium added Wayland support for publishing DBus appmenu information in 2025, explicitly describing the protocol as associating a Wayland surface with a global application menu using `com.canonical.dbusmenu`.

Mozilla also moved Firefox toward the KDE AppMenu approach because the competing generic D-Bus annotation protocol had not been merged or deployed.

So the industry direction is roughly:

```text
Application
     │
     ▼
D-Bus menu
     │
     ├── ideally associated with its Wayland surface
     │
     ▼
Desktop global menu
```

The problem for us is that **Hyprland currently does not provide that association through KDE AppMenu**.

---

# 6. This is the main architectural problem

Suppose Firefox and VS Code both expose D-Bus menus.

We can find menus on the session bus.

But how do we know:

> "This particular D-Bus menu belongs to the currently focused Hyprland window"?

Ideally:

```text
Focused Hyprland window
          │
          ▼
Wayland surface
          │
          ▼
KDE AppMenu association
          │
          ▼
D-Bus service + object path
```

But Hyprland does not currently expose that protocol.

So we need another strategy.

---

# 7. The promising workaround: PID-based D-Bus discovery

This is where the investigation becomes more interesting.

Hyprland already gives us information about the focused window, including its process identity through its IPC.

Conceptually:

```text
Hyprland
    │
    ▼
Focused window
    │
    ├── application class
    ├── title
    └── PID
```

Then:

```text
PID
 │
 ▼
D-Bus process ownership
 │
 ├── org.gtk.Menus
 │
 └── com.canonical.dbusmenu
         │
         ▼
Associated application menu
```

There are already projects experimenting with exactly this style of discovery: inspect the D-Bus services owned by the focused application's process and look for known menu interfaces.

That gives us a possible architecture:

```text
                  Hyprland IPC
                       │
                       ▼
                 Focused window
                       │
                       ▼
                      PID
                       │
                       ▼
              D-Bus service discovery
                       │
              ┌────────┴─────────┐
              │                  │
        org.gtk.Menus      DBusMenu
              │                  │
              └────────┬─────────┘
                       │
                       ▼
                 Menu Model
                       │
                       ▼
                      AGS
                       │
                       ▼
                Global Menu UI
```

This is currently the architecture I consider the **most promising for Hyprland**.

---

# 8. What about the actual applications?

We should expect a compatibility matrix.

Something approximately like this:

| Application type | Expected approach | Confidence |
|---|---|---|
| Traditional GTK3 apps | `appmenu-gtk-module` + GTK D-Bus menu | High |
| GTK apps exposing GMenu | `org.gtk.Menus` | High |
| Qt apps | DBusMenu | High |
| Electron apps | Depends on application/version | Medium |
| Chromium | Modern Wayland AppMenu support exists, but mapping is harder on Hyprland | Medium |
| Firefox | Global-menu work exists; configuration may be required | Medium |
| GTK4/libadwaita | Often no traditional menubar exists | Low/variable |
| Kitty | No traditional application menubar | None |
| Terminal applications | No GUI menu to export | None |

This is an important realization:

**A global menu cannot exist for an application that does not have an application menu.**

For example:

```text
Kitty
```

doesn't have a traditional:

```text
File  Edit  View  Help
```

menu to export.

So the bar would simply show:

```text
◉ Kitty
```

without application menu items.

That's normal and acceptable.

---

# 9. Firefox is now especially interesting

Firefox is no longer just a hypothetical case.

Mozilla explicitly changed its Wayland implementation toward KDE AppMenu because it was already deployed, unlike the proposed generic protocol.

Community reports from 2025 also indicate Firefox Wayland global-menu functionality working when the relevant preferences are enabled, including:

```text
widget.gtk.global-menu.enabled
widget.gtk.global-menu.wayland.enabled
```

Those reports should be treated as implementation/testing evidence rather than a universal guarantee, but they make Firefox a good candidate for our eventual proof of concept.

However, because Hyprland lacks KDE AppMenu, we would need to investigate whether Firefox's menu can be discovered through an alternative D-Bus route or whether the lack of the compositor protocol prevents the necessary association.

That needs to be **tested on the actual system** rather than assumed.

---

# 10. The standard Wayland situation is still unresolved

There has been an effort to create a more generic Wayland mechanism for associating windows with D-Bus objects.

But it has been stuck for years and, according to recent discussion, still has not become the broadly implemented cross-desktop solution that global menus need.

So unfortunately, in 2026, Linux still looks like:

```text
              Global Menu

                    ❌
          No universal standard

       ┌────────────┼────────────┐
       │            │            │
      GTK          Qt        Electron
       │            │            │
   Different      Better      Variable
   mechanisms    support
```

This is why macOS-style global menus are relatively easy on macOS but remain surprisingly complicated on Linux.

---

# 11. Can AGS communicate with D-Bus?

Yes.

This part is not a blocker.

AGS runs on GJS and the GNOME/GLib stack, so it has access to `Gio` and D-Bus functionality.

So we can write something conceptually like:

```text
GlobalMenuService
        │
        ├── listen to Hyprland focus changes
        │
        ├── get focused PID
        │
        ├── discover D-Bus services
        │
        ├── inspect menu interfaces
        │
        ├── build internal menu model
        │
        └── notify UI
```

Then the UI remains clean:

```tsx
<GlobalMenu menu={globalMenu.current} />
```

The ugly protocol/D-Bus logic stays behind that component.

---

# 12. My recommended architecture

After this investigation, **I would not build the global-menu logic directly inside random AGS components**.

I would structure the project like this:

```text
global-shell/
│
├── app.ts
│
├── services/
│   │
│   ├── hyprland.ts
│   │      ├── focused window
│   │      ├── PID
│   │      └── application metadata
│   │
│   └── global-menu/
│          │
│          ├── index.ts
│          │
│          ├── discovery.ts
│          │      └── find D-Bus menu for focused app
│          │
│          ├── gtk-menu.ts
│          │      └── org.gtk.Menus
│          │
│          ├── dbusmenu.ts
│          │      └── com.canonical.dbusmenu
│          │
│          └── model.ts
│                 └── unified internal menu model
│
├── widgets/
│   │
│   ├── bar.tsx
│   │
│   ├── global-menu.tsx
│   │
│   ├── menu-popup.tsx
│   │
│   ├── clock.tsx
│   ├── workspaces.tsx
│   └── system-indicators.tsx
│
└── style/
    └── main.css
```

The key principle would be:

> **AGS draws the shell. The backend discovers and controls application menus.**

---

# 13. The unified menu model

We should avoid letting the UI know whether a menu came from GTK or DBusMenu.

Instead:

```typescript
type MenuItem = {
    id: string
    label: string
    enabled: boolean
    visible: boolean

    shortcut?: string

    submenu?: MenuItem[]

    activate: () => void
}
```

Then both:

```text
org.gtk.Menus
```

and:

```text
com.canonical.dbusmenu
```

become:

```text
MenuItem[]
```

The UI doesn't care where the menu came from:

```text
                 GTK
                  │
                  ▼
             ┌──────────┐
             │ Adapter  │
             └────┬─────┘
                  │
                  │
DBusMenu ──► Adapter ──► Unified Menu Model ──► AGS
```

This would make the architecture much easier to extend.

---

# 14. My recommended proof of concept

We should **not build the entire macOS bar yet**.

The first project should be extremely small:

```text
┌──────────────────────────────────────────────┐
│ AppName      File   Edit   View   Help       │
└──────────────────────────────────────────────┘
```

Only these components:

### Step 1

Track the focused Hyprland window.

```text
Focused window
      ↓
Firefox
PID: 12345
```

### Step 2

Find whether that process exposes:

```text
org.gtk.Menus
```

or:

```text
com.canonical.dbusmenu
```

### Step 3

Extract:

```text
File
Edit
View
Help
```

### Step 4

Render those items in AGS.

### Step 5

Click:

```text
File
```

### Step 6

Render the actual submenu:

```text
┌─────────────────────┐
│ New Window          │
│ New Tab             │
│ Open File...        │
├─────────────────────┤
│ Quit                │
└─────────────────────┘
```

### Step 7

Clicking an item invokes the actual application action.

If we achieve that with **one application**, the hardest technical problem is solved.

Then we expand compatibility.

---

# Final conclusion

My conclusion after the investigation is:

## AGS is a good choice

For your goal, **yes**.

It can build the entire macOS-style bar and has enough access to GTK, GIO, D-Bus, and the system to serve as the frontend and orchestration layer.

## The global menu is possible, but not plug-and-play

The main problem is **application menu discovery**, especially associating a D-Bus menu with the currently focused Wayland window.

Hyprland currently does **not** appear to implement the KDE AppMenu protocol, so the cleanest Wayland-native association mechanism is unavailable.

## The best path is a hybrid approach

```text
                    HYPRLAND
                       │
              focused window/PID
                       │
                       ▼
              GlobalMenuService
                       │
          ┌────────────┴────────────┐
          │                         │
    GTK Menu Provider         DBusMenu Provider
          │                         │
          └────────────┬────────────┘
                       │
                Unified model
                       │
                       ▼
                      AGS
                       │
                       ▼
              macOS-style bar
```

And **NovaBar is currently the most valuable implementation to study**, because it already solves many of these pieces on Wayland using GTK menu interception, D-Bus menus, an AppMenu Registrar, and focused-window tracking.

### My recommendation for our next step

Before installing and building a full AGS shell, I recommend a **second investigation phase on your actual machine**: inspect which applications you use most and determine exactly what menu interfaces they expose. That would let us produce a real compatibility matrix and choose the first application for the proof of concept.

For example:

```text
Application       Menu detected?      Protocol
──────────────────────────────────────────────
Firefox           ?                   ?
VS Code           ?                   ?
Chromium          ?                   ?
Thunar            ?                   ?
GIMP              ?                   ?
Your IDE          ?                   ?
```

That is now the most valuable next step, because it moves us from **"this architecture should work"** to **"here is exactly what works on your Hyprland installation."**
