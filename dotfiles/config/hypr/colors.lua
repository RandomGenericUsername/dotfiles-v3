-- Runtime palette → border glow (Hyprland Lua).
--
-- Reads the runtime-owned palette ($XDG_STATE_HOME/dotfiles/current/
-- colors.conf — the Hyprland-format artifact the seeder repoints on every
-- wallpaper swap) and applies the animated gradient border from it. The
-- runtime's HyprlandReloader runs `hyprctl reload` after each palette
-- repoint, so this module re-executes on every theme change and the border
-- glow follows the wallpaper with no extra daemon or polling.
--
-- All colors resolve from colors.conf at dofile time; the module is inert
-- (keeps the config default) when the file is missing. Border thickness and
-- animation speed live here as the single tunable surface.

local state_home = os.getenv("XDG_STATE_HOME") or (os.getenv("HOME") .. "/.local/state")
local palette = state_home .. "/dotfiles/current/colors.conf"

local colors = {}
local f = io.open(palette, "r")
if f then
    for line in f:lines() do
        local key, hex = line:match("^%$([%w]+) = rgb%(([%x]+)%)")
        if key and hex then
            colors[key] = hex
        end
    end
    f:close()
end

if colors.color0 then
    local function c(hex)
        return tonumber("0xff" .. hex)
    end

    -- Gradient from the palette's brighter mid-tone family (color2/4/6/8/10
    -- are the accent ramp; color0/background + foreground bracket it).
    hl.config({
        general = {
            border_size = 3,
            col = {
                active_border = {
                    colors = {
                        c(colors.color10),  -- bright accent
                        c(colors.color6),   -- mid accent
                        c(colors.color2),   -- deep accent
                        c(colors.color12),  -- light accent
                    },
                    angle = 270,
                },
                inactive_border = {
                    colors = {
                        c(colors.color1),   -- muted, subtle
                        c(colors.color0),   -- near background
                    },
                    angle = 270,
                },
            },
        },
    })
    hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "default", style = "loop" })
end
