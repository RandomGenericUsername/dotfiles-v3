-- GloView configuration and gestures.

local gloview_loaded = pcall(function()
    return hl.plugin.gloview.toggle
end)

if gloview_loaded then
    hl.config({
        plugin = {
            gloview = {
                layout = "rows",
                gap = 34,
                padding = 80,
                padding_top = 40,
                padding_bottom = 70,
                duration = 360,
                preview_round = 12,
                blur = 1,
                anchor = "top",
                dynamic_workspaces = 1,
                show_workspace_labels = 1,
                show_window_labels = 1,
                drag_to_swap = 1,
            },
        },
    })

    -- Three-finger swipe up opens the overview.
    hl.gesture({
        fingers = 3,
        direction = "up",
        action = function()
            hl.plugin.gloview.toggle()
        end,
    })
end
