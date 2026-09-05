-- Autostart configuration (Lua API)
-- Executed once on Hyprland startup.

hl.on("hyprland.start", function()
    -- Wallpaper daemon
    hl.exec_cmd("hyprpaper")

    -- AGS (Aylur's GTK Shell) - status bar
    hl.exec_cmd("ags run")

    -- AGS capture tool (standalone instance `capture`, staggered: two
    -- concurrent `ags run` invocations collide on /run/user/$UID/ags.js)
    hl.exec_cmd("sleep 2 && ags run -d $HOME/.config/ags-capture --log-file $HOME/.local/state/ags/capture.log")

    -- Notification daemon (dunst)
    hl.exec_cmd("dunst")

    -- Polkit authentication agent (hyprpolkitagent)
    hl.exec_cmd("systemctl --user start hyprpolkitagent")

    -- XDG Desktop Portal (for screen sharing, file picking, etc.)
    hl.exec_cmd("systemctl --user start xdg-desktop-portal-hyprland")
    hl.exec_cmd("systemctl --user start xdg-desktop-portal-gtk")

    -- Hyprland plugins require a live IPC session.
    hl.exec_cmd("bash -lc '$HOME/.local/bin/gloview-activate'")

    -- Clipboard manager (wl-clipboard)
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
end)
