-- Environment variables configuration
-- These are set for the Hyprland session

env = XCURSOR_SIZE, 24
env = XCURSOR_THEME, Adwaita
env = GTK_THEME, Adwaita:dark
env = QT_QPA_PLATFORMTHEME, gtk3
env = QT_QPA_PLATFORM, wayland
env = SDL_VIDEODRIVER, wayland
env = CLUTTER_BACKEND, wayland
env = ECORE_EVAS_ENGINE, wayland_egl
env = ELM_DISPLAY, wl
env = MOZ_ENABLE_WAYLAND, 1
env = XDG_CURRENT_DESKTOP, Hyprland
env = XDG_SESSION_DESKTOP, Hyprland
env = XDG_SESSION_TYPE, wayland