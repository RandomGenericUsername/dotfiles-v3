-- Animations configuration (Lua API)

hl.curve("myBezier", {
    type   = "bezier",
    points = { {0.05, 0.9}, {0.1, 1.05} },
})

hl.config({
    animations = {
        enabled = true,
    },
})

hl.animation({ leaf = "windows",    enabled = true, speed = 4, bezier = "myBezier" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 4, bezier = "default" })
hl.animation({ leaf = "border",     enabled = true, speed = 3, bezier = "default" })
hl.animation({ leaf = "fade",       enabled = true, speed = 3, bezier = "default" })
