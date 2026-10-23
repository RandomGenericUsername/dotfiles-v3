# ags-consume-platform

## Why

The AGS platform is being extracted into `ags-platform` (spine **AD-1**: `contracts ← ags-platform ← ags-apps`). This repo is the host that must **consume** it: install the framework as one versioned unit and resolve it by a bare specifier, replacing the per-file enumeration that already drifts.

Evidence: `src/provisioning/ansible/roles/gui_tools/vars/main.yml:270-277` (the notifications list) omits `lib/speedtest-events.ts`, yet `src/gui-tools/notifications/ui/NotificationsWindow.tsx:8,1033` imports it.
Verify: `git grep -n speedtest-events src/provisioning` → **no matches** (the omission).

## What Changes

- Install the framework as **one versioned unit** at `<install>/ags-platform/<version>/` (spine AD-17).
- Create a **shared-ancestor** `node_modules/ags-platform` shortcut so `config/ags` **and** every `config/ags-*` resolve it by bare specifier.
- Replace the five per-app file lists + the bar list with the single-unit install, and remove the ~200 retired per-file copies.
- Record the pinned framework version so rollback is a shortcut repoint.

## Non-goals

- Not extracting the platform (that is the `ags-platform` repo epic).
- Not the validator (separate change `ags-bar-validate-at-install`).
- No behaviour change to the apps or the bar.

## Impact

- `src/provisioning/ansible/roles/{gui_tools,compositor_configs,config_links,verify}/**` and their unit tests.
- `dotfiles/config/ags/**` imports move to the platform (spine AD-1).
