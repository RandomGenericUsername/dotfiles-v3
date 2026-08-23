-- Autostart configuration
-- Executed once on Hyprland startup

-- Wallpaper daemon
exec-once = hyprpaper

-- AGS (Aylur's GTK Shell) - status bar
exec-once = ags run

-- Notification daemon (dunst)
exec-once = dunst

-- Polkit authentication agent (hyprpolkitagent)
exec-once = systemctl --user start hyprpolkitagent

-- XDG Desktop Portal (for screen sharing, file picking, etc.)
exec-once = systemctl --user start xdg-desktop-portal-hyprland
exec-once = systemctl --user start xdg-desktop-portal-gtk

-- Clipboard manager (wl-clipboard)
exec-once = wl-paste --type text --watch cliphist store
exec-once = wl-paste --type image --watch cliphist store

-- Idle management (for screen lock, DPMS)
-- exec-once = swayidle -w timeout 300 'hyprctl dispatch dpms off' resume 'hyprctl dispatch dpms on' timeout 600 'hyprctl dispatch dpms off' before-sleep 'loginctl lock-session'

-- GTK theme sync (if using GTK apps)
-- exec-once = gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita:dark'
-- exec-once = gsettings set org.gnome.desktop.interface icon-theme 'Adwaita'