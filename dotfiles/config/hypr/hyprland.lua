-- Hyprland main configuration (Lua format)
-- This file is templated - paths are resolved at provisioning time.
--
-- Hyprland >= 0.55 uses the Lua config API (hl.* functions). Modules are
-- included with Lua's dofile(), NOT hyprlang's `source =` directive.

local cfg = "{{ compositor_configs_xdg_config_home }}/hypr"

dofile(cfg .. "/env-variables.lua")
dofile(cfg .. "/monitors.lua")
dofile(cfg .. "/input.lua")
dofile(cfg .. "/decoration.lua")
dofile(cfg .. "/animations.lua")
dofile(cfg .. "/cursor.lua")
dofile(cfg .. "/keybindings.lua")
dofile(cfg .. "/window-rules.lua")
dofile(cfg .. "/autostart.lua")
