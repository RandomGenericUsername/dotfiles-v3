-- Decoration configuration (Lua API)

hl.config({
    decoration = {
        rounding         = 8,
        active_opacity   = 1.0,
        inactive_opacity = 0.9,
        shadow           = {
            enabled      = false,
            range        = 10,
            render_power = 3,
            color        = 0x000000,
        },
        blur = {
            enabled            = true,
            size               = 3,
            passes             = 1,
            new_optimizations  = true,
        },
    },
})
