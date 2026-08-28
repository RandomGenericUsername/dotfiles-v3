-- ============================================================
-- Keybindings configuration (Lua API)
-- ============================================================

local mod = "SUPER"


-- ============================================================
-- Applications
-- ============================================================

-- Terminal
hl.bind(
    mod .. " + Return",
    hl.dsp.exec_cmd("kitty"),
    { description = "Open terminal" }
)

-- Application launcher
hl.bind(
    mod .. " + D",
    hl.dsp.exec_cmd("wofi --show drun"),
    { description = "Open application launcher" }
)

-- File manager
hl.bind(
    mod .. " + E",
    hl.dsp.exec_cmd("thunar"),
    { description = "Open file manager" }
)


-- ============================================================
-- Window Management
-- ============================================================

-- Close active window
hl.bind(
    mod .. " + Q",
    hl.dsp.window.close(),
    { description = "Close active window" }
)

-- Toggle fullscreen
hl.bind(
    mod .. " + F",
    hl.dsp.window.fullscreen({ action = "toggle" }),
    { description = "Toggle fullscreen" }
)

-- Toggle floating mode
hl.bind(
    mod .. " + SPACE",
    hl.dsp.window.float({ action = "toggle" }),
    { description = "Toggle floating mode" }
)

-- Toggle pseudo mode
hl.bind(
    mod .. " + P",
    hl.dsp.window.pseudo({ action = "toggle" }),
    { description = "Toggle pseudo mode" }
)

-- Cycle to next window
hl.bind(
    mod .. " + Tab",
    hl.dsp.window.cycle_next(),
    { description = "Focus next window" }
)


-- ============================================================
-- Window Focus
-- ============================================================

-- Focus window in direction
hl.bind(
    mod .. " + H",
    hl.dsp.focus({ direction = "left" }),
    { description = "Focus window to the left" }
)

hl.bind(
    mod .. " + L",
    hl.dsp.focus({ direction = "right" }),
    { description = "Focus window to the right" }
)

hl.bind(
    mod .. " + K",
    hl.dsp.focus({ direction = "up" }),
    { description = "Focus window above" }
)

hl.bind(
    mod .. " + J",
    hl.dsp.focus({ direction = "down" }),
    { description = "Focus window below" }
)


-- ============================================================
-- Move Windows
-- ============================================================

-- Move active window in direction
hl.bind(
    mod .. " + SHIFT + H",
    hl.dsp.window.move({ direction = "left" }),
    { description = "Move window left" }
)

hl.bind(
    mod .. " + SHIFT + L",
    hl.dsp.window.move({ direction = "right" }),
    { description = "Move window right" }
)

hl.bind(
    mod .. " + SHIFT + K",
    hl.dsp.window.move({ direction = "up" }),
    { description = "Move window up" }
)

hl.bind(
    mod .. " + SHIFT + J",
    hl.dsp.window.move({ direction = "down" }),
    { description = "Move window down" }
)


-- ============================================================
-- Workspaces
-- ============================================================

-- Switch to workspace
hl.bind(
    mod .. " + 1",
    hl.dsp.focus({ workspace = 1 }),
    { description = "Switch to workspace 1" }
)

hl.bind(
    mod .. " + 2",
    hl.dsp.focus({ workspace = 2 }),
    { description = "Switch to workspace 2" }
)

hl.bind(
    mod .. " + 3",
    hl.dsp.focus({ workspace = 3 }),
    { description = "Switch to workspace 3" }
)

hl.bind(
    mod .. " + 4",
    hl.dsp.focus({ workspace = 4 }),
    { description = "Switch to workspace 4" }
)

hl.bind(
    mod .. " + 5",
    hl.dsp.focus({ workspace = 5 }),
    { description = "Switch to workspace 5" }
)

hl.bind(
    mod .. " + 6",
    hl.dsp.focus({ workspace = 6 }),
    { description = "Switch to workspace 6" }
)

hl.bind(
    mod .. " + 7",
    hl.dsp.focus({ workspace = 7 }),
    { description = "Switch to workspace 7" }
)

hl.bind(
    mod .. " + 8",
    hl.dsp.focus({ workspace = 8 }),
    { description = "Switch to workspace 8" }
)

hl.bind(
    mod .. " + 9",
    hl.dsp.focus({ workspace = 9 }),
    { description = "Switch to workspace 9" }
)

-- 0 is used as the keyboard shortcut for workspace 10
hl.bind(
    mod .. " + 0",
    hl.dsp.focus({ workspace = 10 }),
    { description = "Switch to workspace 10" }
)


-- ============================================================
-- Move Window to Workspace
-- ============================================================

-- Move active window to workspace
hl.bind(
    mod .. " + SHIFT + 1",
    hl.dsp.window.move({ workspace = 1 }),
    { description = "Move window to workspace 1" }
)

hl.bind(
    mod .. " + SHIFT + 2",
    hl.dsp.window.move({ workspace = 2 }),
    { description = "Move window to workspace 2" }
)

hl.bind(
    mod .. " + SHIFT + 3",
    hl.dsp.window.move({ workspace = 3 }),
    { description = "Move window to workspace 3" }
)

hl.bind(
    mod .. " + SHIFT + 4",
    hl.dsp.window.move({ workspace = 4 }),
    { description = "Move window to workspace 4" }
)

hl.bind(
    mod .. " + SHIFT + 5",
    hl.dsp.window.move({ workspace = 5 }),
    { description = "Move window to workspace 5" }
)

hl.bind(
    mod .. " + SHIFT + 6",
    hl.dsp.window.move({ workspace = 6 }),
    { description = "Move window to workspace 6" }
)

hl.bind(
    mod .. " + SHIFT + 7",
    hl.dsp.window.move({ workspace = 7 }),
    { description = "Move window to workspace 7" }
)

hl.bind(
    mod .. " + SHIFT + 8",
    hl.dsp.window.move({ workspace = 8 }),
    { description = "Move window to workspace 8" }
)

hl.bind(
    mod .. " + SHIFT + 9",
    hl.dsp.window.move({ workspace = 9 }),
    { description = "Move window to workspace 9" }
)

hl.bind(
    mod .. " + SHIFT + 0",
    hl.dsp.window.move({ workspace = 10 }),
    { description = "Move window to workspace 10" }
)


-- ============================================================
-- Monitor Navigation
-- ============================================================

-- Focus adjacent monitor
hl.bind(
    mod .. " + SHIFT + O",
    hl.dsp.focus({ monitor = "relative:1" }),
    { description = "Focus next monitor" }
)

hl.bind(
    mod .. " + SHIFT + I",
    hl.dsp.focus({ monitor = "relative:-1" }),
    { description = "Focus previous monitor" }
)


-- ============================================================
-- Move Windows Between Monitors
-- ============================================================

-- Move active window to adjacent monitor
hl.bind(
    mod .. " + CTRL + SHIFT + H",
    hl.dsp.window.move({ monitor = "relative:-1" }),
    { description = "Move window to previous monitor" }
)

hl.bind(
    mod .. " + CTRL + SHIFT + L",
    hl.dsp.window.move({ monitor = "relative:1" }),
    { description = "Move window to next monitor" }
)


-- ============================================================
-- Workspace Navigation
-- ============================================================

-- Scroll through workspaces
hl.bind(
    mod .. " + mouse_down",
    hl.dsp.focus({ workspace = "e+1" }),
    { description = "Switch to next workspace" }
)

hl.bind(
    mod .. " + mouse_up",
    hl.dsp.focus({ workspace = "e-1" }),
    { description = "Switch to previous workspace" }
)


-- ============================================================
-- Move Window Between Workspaces
-- ============================================================

-- Move active window to adjacent workspace
hl.bind(
    mod .. " + SHIFT + mouse_down",
    hl.dsp.window.move({ workspace = "e+1" }),
    { description = "Move window to next workspace" }
)

hl.bind(
    mod .. " + SHIFT + mouse_up",
    hl.dsp.window.move({ workspace = "e-1" }),
    { description = "Move window to previous workspace" }
)


-- ============================================================
-- Screenshots
-- ============================================================

-- Select region and copy screenshot to clipboard
hl.bind(
    mod .. " + Print",
    hl.dsp.exec_cmd('grim -g "$(slurp)" - | wl-copy'),
    { description = "Screenshot selected region to clipboard" }
)

-- Screenshot entire screen and copy to clipboard
hl.bind(
    mod .. " + SHIFT + Print",
    hl.dsp.exec_cmd("grim - | wl-copy"),
    { description = "Screenshot entire screen to clipboard" }
)


-- ============================================================
-- Session
-- ============================================================

-- Exit Hyprland
-- Intentionally requires CTRL + SHIFT to prevent accidental logout.
hl.bind(
    mod .. " + CTRL + SHIFT + M",
    hl.dsp.exit(),
    { description = "Exit Hyprland" }
)