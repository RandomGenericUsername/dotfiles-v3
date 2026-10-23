# Tasks

## 0. Precondition

- [ ] 0.1 The platform is extracted and consumed; `make gates-ci` is green **before** any deletion. Verify: `make gates-ci` exit 0.

## 1. Delete the duplicated seams

- [ ] 1.1 Delete the 5 `icon-registry.ts` copies. Verify: `find . -name icon-registry.ts` → none; icons resolve via the platform.
- [ ] 1.2 Delete the 4 `event-bus-core.ts`/`event-bus.ts` copies + 2 bespoke readers. Verify: `find . -name 'event-bus*.ts'` → only the platform import; `speedtest-events.ts`/`wallpaper-events.ts` gone.
- [ ] 1.3 Delete the duplicated popup chrome; all popups use `PopupHost`. Verify: `git grep -n "settings-catcher"` → only `PopupHost`.
- [ ] 1.4 Delete the 3 `theme.ts` copies. Verify: `find . -name theme.ts` → none.

## 2. Reconcile

- [ ] 2.1 Remove the deleted files from the provisioning lists. Verify: `verify` passes on a fresh host.
- [ ] 2.2 `make bar-typecheck`, `make ags-typecheck`, `make ags-test`, `make gates-ci` green.
