# Hyprspace --- Installation, Configuration, Hyprland Integration, and Styling Guide

> A practical guide to installing and configuring **Hyprspace**, the
> Hyprland workspace-overview plugin, with an emphasis on modern
> Hyprland (0.55+), Lua configuration, plugin management, touchpad
> gestures, integration, and styling.

## 1. What is Hyprspace?

Hyprspace is a Hyprland plugin that adds a workspace overview similar to
**macOS Mission Control**, KDE Plasma, and GNOME.

It provides a visual overview of workspaces and the windows inside them.
From the overview you can switch workspaces, interact with windows, and
navigate through the workspace panel.

Hyprspace is a **Hyprland plugin**, not a standalone Wayland
application. It is loaded into the Hyprland compositor as a shared
object (`.so`), which means it depends directly on the Hyprland version
and ABI it was built against.

### Main features

-   Workspace overview
-   Workspace minimap / workspace previews
-   Window previews
-   Click a workspace to switch to it
-   Click and drag windows in the overview
-   Move windows between workspaces
-   Create new workspaces from the overview
-   Keyboard exit with Escape
-   Workspace scrolling/swiping
-   Touchpad gesture support
-   Swipe to open the overview
-   Multi-monitor support
-   Monitor scaling support
-   Configurable colors, borders, spacing, panel placement, blur, and
    behavior
-   macOS/KDE-style centered workspace alignment

Hyprspace's upstream README currently marks the major overview,
interaction, styling, animation, multi-monitor, and gesture features as
implemented.

## 2. Important compatibility warning

Hyprspace is a compositor plugin, so **Hyprland and Hyprspace versions
need to be compatible**.

This is more important than with an ordinary application: a plugin runs
inside Hyprland and uses Hyprland's internal APIs. An incompatible
plugin can fail to build, fail to load, behave incorrectly, or in the
worst case destabilize Hyprland.

Hyprland's current plugin documentation recommends using `hyprpm`
because it builds plugins against the installed Hyprland headers.

Before installing or troubleshooting Hyprspace, check:

``` bash
hyprctl version
```

and:

``` bash
hyprpm --version
```

You can also inspect currently loaded plugins with:

``` bash
hyprctl plugin list
```

### Current-state note

Hyprland is a fast-moving project. Hyprspace's upstream README
explicitly warns that Hyprland changes rapidly and that issue resolution
may not always be immediate.

There are also currently open Hyprspace issues involving newer Hyprland
versions, including reports concerning Hyprland 0.55 and a build failure
reported against 0.56. Therefore, always verify compatibility before
updating Hyprland and Hyprspace independently.

## 3. Prerequisites

There are three practical installation approaches:

1.  `hyprpm` --- recommended for most distributions
2.  Manual source build
3.  Nix / NixOS

### 3.1 Hyprland

You must already have a working Hyprland installation.

Verify it with:

``` bash
hyprctl version
```

### 3.2 Hyprland headers

Building a plugin requires Hyprland headers that correspond to the
Hyprland version being used.

If your distribution provides a separate development/header package,
install it.

Examples include:

-   Arch-based systems: the normal Hyprland package provides what
    `hyprpm` needs in the supported setup.
-   Void: the Hyprland documentation specifically identifies
    `hyprland-devel` for plugin development.
-   Fedora/Debian and similar distributions: development/header packages
    may be separate.

The exact package names are distribution-specific.

### 3.3 Build tools

The current Hyprland plugin documentation lists these dependencies for
`hyprpm`:

``` text
cpio
cmake
git
meson
gcc
```

Depending on the distribution, additional development packages may be
required because some distributions split runtime libraries and
development headers.

## 4. Installation method 1 --- hyprpm

For a normal Hyprland installation, this is the preferred method.

### 4.1 Add Hyprspace

Run:

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
```

Then enable it:

``` bash
hyprpm enable Hyprspace
```

### 4.2 Reload plugins

After enabling the plugin:

``` bash
hyprpm reload
```

You can also use:

``` bash
hyprpm reload -n
```

to receive a notification when the plugin is successfully loaded or when
a warning/error occurs.

### 4.3 Verify installation

List plugins managed by hyprpm:

``` bash
hyprpm list
```

Then check the plugins actually loaded into Hyprland:

``` bash
hyprctl plugin list
```

You should see Hyprspace in the loaded plugin list.

### 4.4 Automatically load plugins at startup

Hyprland's current plugin documentation recommends adding a plugin
reload command to your startup configuration.

With the Lua configuration system, this belongs in your autostart
configuration.

For example, conceptually:

``` lua
hl.config({
    exec = {
        "hyprpm reload -n",
    },
})
```

Use the autostart syntax appropriate to your existing Lua configuration
structure.

Do not add another mechanism if your dotfiles already have a centralized
`autostart.lua`.

## 5. Installation method 2 --- manual build

Manual installation is useful if you want to build Hyprspace yourself or
need to debug compatibility.

Clone the repository:

``` bash
git clone https://github.com/KZDKM/Hyprspace
cd Hyprspace
```

Build it:

``` bash
make all
```

The upstream instructions require Hyprland headers to be installed.

After building, locate the generated `.so` file.

Load it with:

``` bash
hyprctl plugin load /absolute/path/to/Hyprspace.so
```

The path must be absolute.

For example:

``` bash
hyprctl plugin load /home/user/Hyprspace/Hyprspace.so
```

Verify:

``` bash
hyprctl plugin list
```

### 5.1 Loading a manually built plugin at startup

If you want to load a manually built plugin automatically, the upstream
README suggests using an autostart command.

Conceptually:

``` bash
hyprctl plugin load /absolute/path/to/Hyprspace.so
```

Add that command to your Hyprland startup configuration.

Be aware that a manually built `.so` is tied closely to the Hyprland
version it was built against. After upgrading Hyprland, you should
generally rebuild the plugin.

## 6. Installation method 3 --- Nix / NixOS

Hyprspace provides a Nix flake setup.

The important part is that Hyprspace follows the same Hyprland input so
the plugin and compositor stay synchronized.

The upstream example uses:

``` nix
{
  inputs = {
    hyprland = {
      type = "git";
      url = "https://github.com/hyprwm/Hyprland";
      submodules = true;
      inputs.nixpkgs.follows = "nixpkgs";
    };

    Hyprspace = {
      url = "github:KZDKM/Hyprspace";
      inputs.hyprland.follows = "hyprland";
    };
  };

  # ... normal Hyprland configuration

  wayland.windowManager.hyprland.plugins = [
    inputs.Hyprspace.packages.${pkgs.system}.Hyprspace
  ];
}
```

The important concept is:

``` nix
inputs.hyprland.follows = "hyprland";
```

This prevents Hyprspace from being built against a different Hyprland
input than the one used by your system.

For Home Manager/NixOS, adapt the plugin declaration to your existing
Hyprland module structure.

## 7. Distribution-specific guidance

Hyprspace itself does not provide separate official installation
packages for every Linux distribution. Its upstream installation
documentation currently describes `hyprpm`, manual compilation, and Nix.

Therefore, the portable strategy is:

### Arch / EndeavourOS / other Arch-based systems

This is the simplest environment for Hyprland plugins.

Install Hyprland and make sure `hyprpm` is available.

Then:

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
hyprpm enable Hyprspace
hyprpm reload
```

Your system should already have the common compiler/build dependencies
if your Hyprland development setup is complete.

### Fedora

Use the distribution's Hyprland package and development packages where
required.

Install the build dependencies required by `hyprpm`, plus Hyprland
development/header packages if your Fedora packaging separates them.

Then use:

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
hyprpm enable Hyprspace
hyprpm reload
```

If the plugin fails to build, run the command with verbose output and
verify that the Hyprland headers correspond to the running Hyprland
version.

### Debian / Ubuntu

Hyprland availability depends heavily on the specific release and
repository configuration.

Once Hyprland and its development headers are available, the same
`hyprpm` process applies:

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
hyprpm enable Hyprspace
hyprpm reload
```

You may need separate `-dev` packages for Hyprland's dependencies.

### Void Linux

Hyprland's documentation specifically mentions `hyprland-devel` when
plugins are required.

After installing Hyprland and its development package, use the normal
`hyprpm` installation.

### NixOS

Prefer the Nix/flake method described above because it gives you
explicit control over the Hyprland/Hyprspace dependency relationship.

## 8. Integrating Hyprspace with modern Hyprland Lua configuration

Hyprland 0.55 and newer use Lua configuration instead of the older
hyprlang configuration model.

That matters because older examples on the Internet may show:

``` text
bind = SUPER, R, overview:toggle
```

or:

``` text
plugin:overview:panelColor = ...
```

as standalone hyprlang configuration lines.

In a modern Lua configuration, use the Lua API.

For your configuration architecture, a clean structure is:

``` text
hypr/
├── hyprland.lua
├── env-variables.lua
├── monitors.lua
├── input.lua
├── decoration.lua
├── animations.lua
├── cursor.lua
├── keybindings.lua
├── window-rules.lua
└── autostart.lua
```

Your main configuration loads these files with `dofile()`.

Hyprspace configuration belongs naturally in a dedicated plugin
configuration section, or in a file such as:

``` text
hyprspace.lua
```

if you want to keep plugin configuration separate.

## 9. Opening Hyprspace

Hyprspace exposes three dispatchers:

``` text
overview:toggle
overview:open
overview:close
```

They operate on the current monitor.

Adding the `all` argument operates on all monitors.

### Toggle

Use:

``` text
overview:toggle
```

### Open

Use:

``` text
overview:open
```

### Close

Use:

``` text
overview:close
```

With multiple monitors:

``` text
overview:toggle all
overview:open all
overview:close all
```

## 10. Adding a keyboard shortcut

For your Lua keybinding architecture, the exact way to execute a
Hyprland dispatcher depends on the dispatcher API exposed by your
current Hyprland Lua version.

The conceptual binding is:

``` text
SUPER + Tab → overview:toggle
```

If your Lua API exposes the dispatcher through the corresponding
`hl.dsp` function, use that API rather than reverting your entire
configuration to old hyprlang syntax.

A practical alternative is to invoke the dispatcher through `hyprctl` if
your configuration requires it.

The important dispatcher is:

``` text
overview:toggle
```

## 11. Touchpad gestures

Hyprspace has built-in touchpad/gesture support.

The upstream project documents:

-   workspace swipe
-   scrolling through the workspace panel
-   swipe to open

Hyprspace's touchpad gesture behavior follows Hyprland's workspace swipe
settings.

Relevant Hyprland settings include:

``` text
gestures:workspace_swipe_fingers
gestures:workspace_swipe_cancel_ratio
gestures:workspace_swipe_min_speed_to_force
```

This means Hyprspace can integrate naturally with the three-finger
workspace gestures you are already configuring.

### Swipe to open overview

Hyprspace supports opening/closing the overview through a vertical
workspace swipe.

This is particularly useful for a laptop setup:

``` text
3 fingers left/right
        ↓
change workspace

3 fingers up/down
        ↓
Hyprspace overview
```

If the gesture direction feels reversed compared with macOS, Hyprspace
provides:

``` text
plugin:overview:reverseSwipe
```

to reverse the swipe direction.

### Disable Hyprspace gestures

If you want to handle gestures yourself, Hyprspace exposes:

``` text
plugin:overview:disableGestures
```

This is useful if another gesture system or plugin should own touchpad
gestures.

## 12. How the overview works

When Hyprspace is open:

### Workspace switching

Click a workspace preview to switch to that workspace.

### Window interaction

Clicking a window allows it to be dragged.

Dragging a window into another workspace moves the window there.

### Exit

By default:

``` text
Escape
```

exits the overview.

Clicking without dragging also exits when:

``` text
plugin:overview:exitOnClick
```

is enabled.

### Navigation

When many workspaces are visible, the workspace panel can be
scrolled/swiped to navigate through the workspace views.

## 13. Styling Hyprspace

Hyprspace exposes a set of plugin configuration variables under:

``` text
plugin:overview:
```

The styling options are divided into colors and layout.

### 13.1 Colors

#### Panel background

``` text
plugin:overview:panelColor
```

Controls the overview panel background.

#### Panel border

``` text
plugin:overview:panelBorderColor
```

Controls the panel border color.

#### Active workspace background

``` text
plugin:overview:workspaceActiveBackground
```

Controls the background of the currently active workspace preview.

#### Inactive workspace background

``` text
plugin:overview:workspaceInactiveBackground
```

Controls inactive workspace previews.

#### Active workspace border

``` text
plugin:overview:workspaceActiveBorder
```

Controls the active workspace border.

#### Inactive workspace border

``` text
plugin:overview:workspaceInactiveBorder
```

Controls inactive workspace borders.

#### Drag opacity

``` text
plugin:overview:dragAlpha
```

Controls the opacity of a window while it is being dragged.

The range is:

``` text
0 → completely transparent
1 → completely opaque
```

#### Blur

``` text
plugin:overview:disableBlur
```

Disables the overview blur effect.

## 14. Layout styling

### Panel height

``` text
plugin:overview:panelHeight
```

Controls the height of the overview panel.

### Panel border width

``` text
plugin:overview:panelBorderWidth
```

Controls the thickness of the panel border.

### Panel position

``` text
plugin:overview:onBottom
```

Controls whether the overview panel is displayed at the bottom instead
of the top.

### Workspace spacing

``` text
plugin:overview:workspaceMargin
```

Controls the spacing between workspace previews and the panel edges.

### Reserved top area

``` text
plugin:overview:reservedArea
```

Adds padding above the panel.

The upstream documentation specifically describes this as useful for a
MacBook camera notch.

### Workspace border size

``` text
plugin:overview:workspaceBorderSize
```

Controls workspace preview border thickness.

### Center alignment

``` text
plugin:overview:centerAligned
```

This is particularly relevant for a macOS-style setup.

When enabled, workspace previews are centered like KDE/macOS.

When disabled, they use a left-aligned Windows-like arrangement.

For a Mission Control-style design, enable:

``` text
plugin:overview:centerAligned = true
```

## 15. Layer visibility

Hyprspace provides controls for which Wayland layers are displayed while
the overview is active.

### Background layers

``` text
plugin:overview:hideBackgroundLayers
```

### Top layers

``` text
plugin:overview:hideTopLayers
```

### Overlay layers

``` text
plugin:overview:hideOverlayLayers
```

### Real workspace layers

``` text
plugin:overview:hideRealLayers
```

These are useful when integrating Hyprspace with Waybar, wallpapers,
notifications, or other layer-shell applications.

Be careful with these options: hiding layers can make the overview
visually cleaner, but can also make expected UI elements disappear.

## 16. Active workspace rendering

``` text
plugin:overview:drawActiveWorkspace
```

Controls whether the active workspace is drawn in the overview as-is.

This can be useful if you want the current workspace to remain visually
prominent instead of being treated exactly like the miniature workspace
previews.

## 17. Gaps

Hyprspace can override layout gaps while the overview is active.

Enable:

``` text
plugin:overview:overrideGaps
```

Then configure:

``` text
plugin:overview:gapsIn
plugin:overview:gapsOut
```

The effect is to give the workspace views their own gap configuration
instead of inheriting the normal workspace layout gaps.

This is useful when your normal Hyprland gaps are large or visually
optimized for normal use but you want tighter spacing in the overview.

### Strut / reserved space

``` text
plugin:overview:affectStrut
```

Controls whether the overview panel pushes windows aside.

The upstream documentation notes that disabling this also disables
`overrideGaps`.

## 18. Animation

Hyprspace uses the Hyprland `windows` animation curve for its slide-in
animation.

You can override the animation speed with:

``` text
plugin:overview:overrideAnimSpeed
```

This is useful if your Hyprland animation configuration is intentionally
fast or slow.

For a macOS-like experience, the animation should generally feel smooth
rather than instantaneous.

## 19. Behavior configuration

### Automatic dragging

``` text
plugin:overview:autoDrag
```

When enabled, clicking a window while the overview is open always begins
dragging it.

### Automatic workspace scrolling

``` text
plugin:overview:autoScroll
```

When enabled, mouse scrolling over the active workspace area switches
workspaces.

### Exit after clicking

``` text
plugin:overview:exitOnClick
```

When enabled, clicking without dragging exits the overview.

### Switch workspace on drop

``` text
plugin:overview:switchOnDrop
```

When enabled, dropping a window into another workspace switches to that
workspace.

### Exit after switching

``` text
plugin:overview:exitOnSwitch
```

When enabled, the overview closes after switching workspaces through a
click or a drop.

### Show a new workspace

``` text
plugin:overview:showNewWorkspace
```

Adds a new empty workspace at the end of the workspace overview.

### Show empty workspaces

``` text
plugin:overview:showEmptyWorkspace
```

Controls whether empty workspaces between non-empty workspaces are
displayed.

### Show special workspace

``` text
plugin:overview:showSpecialWorkspace
```

Controls whether special workspaces are shown.

The default is false.

### Exit key

``` text
plugin:overview:exitKey
```

Controls which key exits overview mode.

The default is:

``` text
Escape
```

Set it to an empty value if you want to disable keyboard exit.

## 20. A sensible macOS-style starting configuration

For a setup intended to resemble macOS Mission Control, the most
interesting options are:

``` text
plugin:overview:centerAligned = true
plugin:overview:onBottom = false
plugin:overview:disableBlur = false
plugin:overview:exitOnClick = true
plugin:overview:exitOnSwitch = true
plugin:overview:showNewWorkspace = true
plugin:overview:showEmptyWorkspace = true
```

Then tune:

``` text
panelHeight
workspaceMargin
workspaceBorderSize
panelBorderWidth
```

to match your monitor resolution and Waybar layout.

If your top bar occupies part of the screen, also consider:

``` text
plugin:overview:reservedArea
```

so the overview does not visually collide with the bar/notch area.

## 21. Integration with Waybar

Hyprspace does not replace Waybar.

The two operate at different levels:

``` text
Hyprland
├── Waybar
│   └── status / workspaces / system information
│
└── Hyprspace
    └── workspace overview / window previews
```

Your existing Waybar workspace module can continue to work normally.

Hyprspace provides a separate visual overview that appears when
activated.

A good design is therefore:

``` text
Normal desktop
    ↓
Waybar shows compact workspace state

3-finger swipe up
    ↓
Hyprspace opens

Hyprspace
    ↓
large visual workspace overview
```

## 22. Integration with your Lua configuration structure

Given a modular configuration such as:

``` text
hypr/
├── hyprland.lua
├── env-variables.lua
├── monitors.lua
├── input.lua
├── decoration.lua
├── animations.lua
├── cursor.lua
├── keybindings.lua
├── window-rules.lua
└── autostart.lua
```

a clean approach is to add:

``` text
hyprspace.lua
```

and load it from the main configuration:

``` lua
dofile(cfg .. "/hyprspace.lua")
```

Place it after the general Hyprland configuration has been initialized.

Then keep:

-   `input.lua` → touchpad and input configuration
-   `keybindings.lua` → keyboard shortcuts
-   `hyprspace.lua` → Hyprspace-specific plugin configuration
-   `autostart.lua` → startup commands such as plugin reload, if
    required

This keeps the plugin isolated from the rest of your compositor
configuration.

## 23. Plugin management and updates

With `hyprpm`, the normal lifecycle is:

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
hyprpm enable Hyprspace
hyprpm reload
```

To inspect:

``` bash
hyprpm list
hyprctl plugin list
```

To update:

``` bash
hyprpm update
```

After updating Hyprland, it is a good practice to update/rebuild the
plugin as well.

## 24. Troubleshooting

### Plugin does not build

Check:

``` bash
hyprctl version
```

Then run:

``` bash
hyprpm update
```

and retry the build.

If necessary, use verbose output from `hyprpm` to identify the failing
build step.

The most common causes are:

-   Hyprland was updated but the plugin has not caught up
-   Hyprland headers do not match the running version
-   Required compiler/build dependencies are missing
-   Another plugin or patch changes Hyprland internals
-   A plugin compatibility regression exists

### Plugin does not appear in `hyprctl plugin list`

Check:

``` bash
hyprpm list
```

Then:

``` bash
hyprpm reload
```

If it still does not load, inspect Hyprland's log/output for the plugin
loading error.

### Hyprland becomes unstable after enabling Hyprspace

Disable the plugin:

``` bash
hyprpm disable Hyprspace
```

Then reload plugins:

``` bash
hyprpm reload
```

Hyprland's plugin documentation explicitly warns that plugins run inside
the compositor and can affect compositor stability.

### Gesture does not work

First verify the touchpad:

``` bash
hyprctl devices
```

Then check the Hyprland workspace gesture configuration.

Relevant settings include:

``` text
gestures:workspace_swipe_fingers
gestures:workspace_swipe_cancel_ratio
gestures:workspace_swipe_min_speed_to_force
```

Also check:

``` text
plugin:overview:disableGestures
```

If that is enabled, Hyprspace gesture handling is disabled.

### Gesture direction feels backwards

Use:

``` text
plugin:overview:reverseSwipe
```

to reverse the direction.

## 25. Compatibility with other Hyprland plugins

Hyprspace explicitly documents tested compatibility with:

-   `hyprsplit`
-   `split-monitor-workspaces`
-   `hyprexpo`

It also states that it works with layout plugins generally, except
plugins that override Hyprland's workspace management.

If you use another plugin that changes workspace semantics, test
carefully.

## 26. Security considerations

Hyprland plugins are shared libraries loaded directly into the
compositor.

That means installing a plugin is fundamentally different from
installing an ordinary GUI application.

Only install Hyprspace from a source you trust.

The official Hyprland plugin documentation explicitly warns against
loading random `.so` files.

For Hyprspace, the primary upstream repository is:

KZDKM/Hyprspace

## 27. Recommended setup for a modern Hyprland laptop

For a laptop using modern Hyprland Lua configuration, a good final setup
is:

``` text
Hyprland
│
├── Lua configuration
│   ├── input.lua
│   │   └── touchpad configuration
│   │
│   ├── keybindings.lua
│   │   └── SUPER + H/J/K/L
│   │   └── SUPER + 1..0
│   │
│   ├── hyprspace.lua
│   │   └── overview styling / behavior
│   │
│   └── autostart.lua
│       └── hyprpm reload
│
├── Waybar
│   └── compact workspace/status information
│
└── Hyprspace
    ├── workspace overview
    ├── window previews
    ├── workspace switching
    ├── window movement
    └── touchpad gestures
```

A natural interaction model is:

``` text
SUPER + 1..0
    → switch workspace

SUPER + SHIFT + 1..0
    → move window to workspace

SUPER + H/J/K/L
    → focus window

SUPER + SHIFT + H/J/K/L
    → move window

3-finger horizontal swipe
    → workspace navigation

3-finger vertical swipe
    → Hyprspace overview

Escape
    → close overview
```

This gives you a workflow that is very close to the combination of
**Hyprland's tiling model + macOS Mission Control**.

## 28. Sources and further reading

Primary Hyprspace documentation:

-   Hyprspace repository and README: KZDKM/Hyprspace
-   Hyprspace source code and `hyprpm.toml`

Hyprland documentation:

-   Hyprland plugin management
-   Hyprland Lua configuration
-   Hyprland input and gesture configuration
-   Hyprland plugin development / ABI guidance

For installation and troubleshooting, prefer the current Hyprland wiki
and the upstream Hyprspace repository over older blog posts or
configuration snippets written for Hyprland 0.54 and earlier.

------------------------------------------------------------------------

## Quick reference

### Install with hyprpm

``` bash
hyprpm add https://github.com/KZDKM/Hyprspace
hyprpm enable Hyprspace
hyprpm reload
```

### Verify

``` bash
hyprpm list
hyprctl plugin list
```

### Update

``` bash
hyprpm update
```

### Manual build

``` bash
git clone https://github.com/KZDKM/Hyprspace
cd Hyprspace
make all
```

### Manual load

``` bash
hyprctl plugin load /absolute/path/to/Hyprspace.so
```

### Overview dispatchers

``` text
overview:open
overview:close
overview:toggle
```

### Important styling variables

``` text
plugin:overview:panelColor
plugin:overview:panelBorderColor
plugin:overview:workspaceActiveBackground
plugin:overview:workspaceInactiveBackground
plugin:overview:workspaceActiveBorder
plugin:overview:workspaceInactiveBorder
plugin:overview:dragAlpha
plugin:overview:disableBlur

plugin:overview:panelHeight
plugin:overview:panelBorderWidth
plugin:overview:onBottom
plugin:overview:workspaceMargin
plugin:overview:reservedArea
plugin:overview:workspaceBorderSize
plugin:overview:centerAligned
plugin:overview:overrideGaps
plugin:overview:gapsIn
plugin:overview:gapsOut
plugin:overview:affectStrut

plugin:overview:overrideAnimSpeed

plugin:overview:autoDrag
plugin:overview:autoScroll
plugin:overview:exitOnClick
plugin:overview:switchOnDrop
plugin:overview:exitOnSwitch
plugin:overview:showNewWorkspace
plugin:overview:showEmptyWorkspace
plugin:overview:showSpecialWorkspace
plugin:overview:disableGestures
plugin:overview:reverseSwipe
plugin:overview:exitKey
```
