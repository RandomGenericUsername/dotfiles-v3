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

-- No geometry animation for layer surfaces. `layers` eases a layer surface
-- between sizes by stretching its buffer, which turns a rounded panel into a
-- squared one for the duration — measured from a 60fps recording of the capture
-- window resizing (screenshot <-> recording <-> settings): ~230ms of stretched,
-- square-cornered panel. Layer surfaces here are fixed-size overlays (bar,
-- capture, clipboard, wallpaper picker) so nothing wants a geometry animation,
-- and the notification stack is better off snapping to height than stretching.
-- Open/close still animate: those are `layersIn`/`layersOut`, untouched.
hl.animation({ leaf = "layers", enabled = false })
