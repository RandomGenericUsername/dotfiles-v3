# PolicyKit Agent Integration for Hyprland/UWSM

## Current Status: BLOCKED - Arch Package Dependency Issue

### The Problem
The `hyprpolkitagent` package (0.2.0-1) in the Arch extra repository requires `libhyprtoolkit.so.6`, but the current system has `hyprtoolkit 0.5.4-5` which provides `libhyprtoolkit.so.5`. Upgrading hyprtoolkit to 0.6.0-1 would break dependencies for `hyprland-guiutils` and `hyprpaper`.

This is a repository synchronization issue in Arch Linux, not a dotfiles configuration problem.

## Architecture Analysis

### Your Dotfiles Architecture
Your dotfiles use **UWSM** (systemd-managed Wayland session launcher) with a consistent pattern for session-level services:

1. **Systemd user units** with `WantedBy=graphical-session.target`
2. **Provisioning via Ansible roles** (e.g., `runtime_daemon`, `runtime_clipboard`)
3. **Runtime/executable split**: Ansible owns the unit configuration, runtime owns the executable
4. **Session-scoped**: Services require `dbus.socket` and start after `graphical-session.target`

### Session Service Pattern
Existing examples in your dotfiles:
- `runtime_daemon.service` - Type=dbus, BusName=org.dotfiles.Events
- `runtime_clipboard.service` - Type=simple, ExecStart calls dotfiles-runtime
- Both use `After=dbus.socket graphical-session.target`
- Both use `WantedBy=graphical-session.target`

## Proposed Integration (When Packages Sync)

### 1. Package Mapping
Add to `src/provisioning/ansible/group_vars/arch.yml`:
```yaml
hyprpolkitagent: hyprpolkitagent
```

### 2. Systemd User Service
The `hyprpolkitagent` package ships its own systemd unit at `/usr/lib/systemd/user/hyprpolkitagent.service`:
```ini
[Unit]
Description=Hyprland Polkit Authentication Agent
PartOf=graphical-session.target
After=graphical-session.target
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
ExecStart=/usr/lib/hyprpolkitagent/hyprpolkitagent
Slice=session.slice
TimeoutStopSec=5sec
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

### 3. Ansible Role
Create `src/provisioning/ansible/roles/polkit_agent/` with:
- `vars/main.yml` - unit name configuration
- `tasks/main.yml` - enable the package's unit for graphical-session.target
- `handlers/main.yml` - restart handler

### 4. Bootstrap Integration
Add to `src/provisioning/ansible/playbooks/bootstrap.yaml`:
```yaml
- import_playbook: polkit-agent.yaml
```

### 5. Remove Manual Startup
Remove from `dotfiles/config/hypr/autostart.lua`:
```lua
hl.exec_cmd("systemctl --user start hyprpolkitagent")
```

## Validation Steps (Once Packages Sync)

After implementation, verify:
```bash
# Check the service is running
systemctl --user status hyprpolkitagent

# Verify it's registered with D-Bus
busctl --user list | grep -i polkit

# Test authentication (e.g., try to mount a USB drive without auto-mount)
```

## Current Workaround

The manual startup line has been commented out in `autostart.lua` with a detailed note explaining the blocker. Once the Arch packages synchronize, uncomment the line or migrate to the systemd integration as described above.

## Key Architectural Principles Preserved

1. **Session-scoped services** use systemd user units, not shell commands
2. **Provisioning manages configuration**, runtime manages execution
3. **UWSM integration** via `graphical-session.target`
4. **No duplicate startup mechanisms** - systemd handles lifecycle
5. **Reproducible across machines** via Ansible provisioning
