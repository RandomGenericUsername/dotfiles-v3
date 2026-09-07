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
        title = "^(Icons manifest \\(edited by tool\\)|SVG template root \\(read-only\\)|Color scheme \\(read-only\\))$",
    },
    float = true,
    size  = "1280 800",
    center = true,
})
