-- Input configuration (Lua API)

hl.config({
    input = {
        kb_layout     = "us",
        follow_mouse  = 1,
        sensitivity   = 0,
        accel_profile = "flat",
        touchpad      = {
            natural_scroll = true,
            tap_to_click   = true,
        },
    },
})

hl.gesture({
    fingers = 3,
    direction = "left",
    action = function()
        hl.exec_cmd("hyprctl gloviewnext")
    end,
})

hl.gesture({
    fingers = 3,
    direction = "right",
    action = function()
        hl.exec_cmd("hyprctl gloviewprev")
    end,
})