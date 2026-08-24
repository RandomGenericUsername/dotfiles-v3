-- Keybindings configuration (Lua API)

local mod = "SUPER"

-- Terminal
hl.bind(mod .. " + Return", hl.dsp.exec_cmd("kitty"))

-- Window management
hl.bind(mod .. " + Q", hl.dsp.window.close())
hl.bind(mod .. " + F", hl.dsp.window.fullscreen({ action = "toggle" }))
hl.bind(mod .. " + M", hl.dsp.exit())

-- Focus / move
hl.bind(mod .. " + H", hl.dsp.focus({ direction = "left" }))
hl.bind(mod .. " + L", hl.dsp.focus({ direction = "right" }))
hl.bind(mod .. " + K", hl.dsp.focus({ direction = "up" }))
hl.bind(mod .. " + J", hl.dsp.focus({ direction = "down" }))

-- Workspaces
hl.bind(mod .. " + 1", hl.dsp.focus({ workspace = 1 }))
hl.bind(mod .. " + 2", hl.dsp.focus({ workspace = 2 }))
hl.bind(mod .. " + 3", hl.dsp.focus({ workspace = 3 }))
hl.bind(mod .. " + 4", hl.dsp.focus({ workspace = 4 }))
hl.bind(mod .. " + 5", hl.dsp.focus({ workspace = 5 }))

-- Application launcher (wofi)
hl.bind(mod .. " + D", hl.dsp.exec_cmd("wofi --show drun"))

-- File manager (Thunar)
hl.bind(mod .. " + E", hl.dsp.exec_cmd("thunar"))

-- Screenshot (grim + slurp)
hl.bind(mod .. " + Print", hl.dsp.exec_cmd('grim -g "$(slurp)" - | wl-copy'))
hl.bind(mod .. " + SHIFT + Print", hl.dsp.exec_cmd("grim - | wl-copy"))
