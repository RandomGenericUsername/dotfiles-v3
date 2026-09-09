-- Environment variables configuration
-- Set for the Hyprland session (Lua API)

hl.env("XCURSOR_SIZE", "24")
hl.env("XCURSOR_THEME", "Adwaita")
-- GTK_THEME REMOVED (gt-4-1, 2026-09-08): forcing "Adwaita:dark" here made GTK
-- load the plain GTK theme in place of libadwaita's stylesheet at a priority
-- that beats ALL user-CSS overrides (~/.config/gtk-4.0/gtk.css) — the runtime's
-- wallpaper-derived palette (current/colors.adw.css via the gtk-4.0 chain)
-- never reached libadwaita apps while this was set (machine-verified: pure-red
-- override rendered only after unsetting this var). Light/dark now comes from
-- gsettings org.gnome.desktop.interface color-scheme; colors come from the
-- runtime palette CSS.
hl.env("QT_QPA_PLATFORMTHEME", "gtk3")
hl.env("QT_QPA_PLATFORM", "wayland")
hl.env("SDL_VIDEODRIVER", "wayland")
hl.env("CLUTTER_BACKEND", "wayland")
hl.env("ECORE_EVAS_ENGINE", "wayland_egl")
hl.env("ELM_DISPLAY", "wl")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
