-- Autostart configuration (Lua API)
-- Executed once on Hyprland startup.

hl.on("hyprland.start", function()
    -- Wallpaper daemon
    hl.exec_cmd("hyprpaper")

    -- Restore persisted desktop (wallpaper/palette/icons from current.json).
    -- Without this, every login shows the static default.png from
    -- hyprpaper.conf while the runtime state remembers the last wallpaper.
    -- Waits (bounded, backgrounded) for the hyprpaper IPC socket, then runs
    -- `dotfiles-runtime reconcile`, which repoints current/ and re-fires all
    -- reloaders idempotently. Fail-open (|| true): login must never block on
    -- reconcile; output goes to the state dir for diagnosis. Wrapped in
    -- bash -lc like the staggers below (hl.exec_cmd has no shell semantics).
    hl.exec_cmd("bash -lc '(for i in $(seq 1 60); do [ -S \"$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.hyprpaper.sock\" ] && break; sleep 1; done; PATH=\"$HOME/.local/bin:$PATH\" dotfiles-runtime reconcile >>\"$HOME/.local/state/dotfiles/login-reconcile.log\" 2>&1 || true) &'")

    -- AGS (Aylur's GTK Shell) - status bar
    hl.exec_cmd("ags run")

    -- AGS capture tool (standalone instance `capture`, staggered: two
    -- concurrent `ags run` invocations collide on /run/user/$UID/ags.js).
    -- Wrapped in bash -lc like gloview-activate below: hl.exec_cmd has no
    -- shell semantics (no &&, no $HOME expansion) on its own. The log dir
    -- (~/.local/state/ags) is ensured by the gui_tools role — directory
    -- setup is provisioning's responsibility, this line only starts processes.
    hl.exec_cmd("bash -lc 'sleep 2 && ags run -d $HOME/.config/ags-capture --log-file $HOME/.local/state/ags/capture.log'")

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
