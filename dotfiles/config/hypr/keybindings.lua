-- Keybindings configuration
$mod = SUPER

-- Terminal
bind = $mod, Return, exec, kitty

-- Window management
bind = $mod, Q, killactive
bind = $mod, F, fullscreen
bind = $mod, M, exit

-- Focus / move
bind = $mod, H, movefocus, l
bind = $mod, L, movefocus, r
bind = $mod, K, movefocus, u
bind = $mod, J, movefocus, d

-- Workspaces
bind = $mod, 1, workspace, 1
bind = $mod, 2, workspace, 2
bind = $mod, 3, workspace, 3
bind = $mod, 4, workspace, 4
bind = $mod, 5, workspace, 5

-- Application launcher (wofi)
bind = $mod, D, exec, wofi --show drun

-- File manager (Thunar)
bind = $mod, E, exec, thunar

-- Screenshot (grim + slurp)
bind = $mod, Print, exec, grim -g "$(slurp)" - | wl-copy
bind = $mod, Shift, Print, exec, grim - | wl-copy