# ags-delete-redundant-code

## Why

Once the platform is extracted and consumed (spine **AD-20**, sequenced), this repo's duplicate seams are dead weight: **5 icon-registry copies**, **4 full `DomainEventBusCore` copies + 2 bespoke notification readers**, **5 duplicated popup chromes**, and **3 `theme.ts` copies**. Deleting them is the point of the split — but only after the platform is green.

Evidence: `find -name icon-registry.ts` → 5; `find -name event-bus-core.ts` → 4; popup chrome in 5 files; `theme.ts` byte-identical ×3 (`md5` equal).
Verify: the greps above, after the platform is consumed.

## What Changes

- Delete the 5 icon-registry copies; all icon resolution goes through the platform `IconProvider`.
- Delete the 4 `event-bus-core.ts`/`event-bus.ts` copies + 2 bespoke notification readers; all events go through the one client.
- Delete the duplicated popup chrome; all popups use `PopupHost`.
- Delete the 3 `theme.ts` copies; theming goes through the `Theme` port.

## Non-goals

- Not the extraction or the app migration (separate epics).
- Not deleting the bar-specific code (layout, surfaces, shapes) — that moves to `ags-apps`.

## Impact

- `dotfiles/config/ags/lib/{icon-registry,event-bus-core,event-bus}.ts`, `bar/widgets/**`, `components/*Popup.tsx`, `settings-panel/**`.
- `src/gui-tools/**` once the apps migrate.
- Provisioning file manifests (the deleted files are removed from the lists).
