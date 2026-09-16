-- Window rules configuration (Lua API)
-- Examples:
--   hl.window_rule({
--       name  = "float-pavucontrol",
--       match = { class = "^(pavucontrol)$" },
--       float = true,
--   })
--   hl.window_rule({
--       name  = "workspace-firefox",
--       match = { class = "^(firefox)$" },
--       workspace = 2,
--   })

-- Add your window rules here

-- Icon color mapping editor's file choosers: the editor window is a
-- layer-shell OVERLAY surface, which always stacks above regular windows,
-- so it hides itself while a chooser is open (app-side). This rule makes
-- any of the editor's three choosers (inputs manifest, template root,
-- color scheme) become its replacement while open: floated, the same
-- 1280x800 dimensions, centered on the screen. Scoped to these titles so
-- other apps' portal dialogs keep their normal behavior.
hl.window_rule({
    name  = "icme-filechooser-replaces-editor",
    match = {
        class = "^(xdg-desktop-portal-gtk)$",
        title = "^(Icons manifest \\(edited by tool\\)|SVG template root|Color scheme \\(read-only\\)|Template file)$",
    },
    float = true,
    size  = "1280 800",
    center = true,
})

-- Capture tool's window is a layer-shell OVERLAY that RESIZES whenever the user
-- switches views (screenshot / recording / settings), so its height changes.
-- Hyprland animates layer-surface resizes through the `layers` animation, which
-- eased the surface between sizes for ~230ms — measured from a screen recording
-- at 60fps — and read as the panel trailing a rectangle as it shrank. The
-- window declares `namespace = "capture"` (Astal Window) so this rule targets
-- only it, leaving the bar and the notification overlay animated as before.
hl.layer_rule({
    name  = "capture-no-resize-anim",
    match = { namespace = "capture" },
    no_anim = true,
})
