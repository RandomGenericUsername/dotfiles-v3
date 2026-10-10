# ags-bar-validate-at-install

## Why

The provisioning contract (spine **AD-15**, **AD-16**) makes the validator the **only place** the runtime artifacts and the app's declared expectations meet: provisioning runs `validateLayout` + `validateIcons` and **fails install on any error**, while the bar runs the **same functions** at startup and degrades. Neither exists today — there is no `bar-manifest`, no `ags-bar-validate`, and the artifacts carry no `schemaVersion`.

Evidence: `git grep -n "ags-bar-validate\|bar-manifest\|validateLayout"` → none; `contracts/schemas/current.schema.json:10` shows the structural artifacts already use a `schema_version`.
Verify: `make gates-ci` currently has no validation step for the bar layout/icons.

## What Changes

- Add the pure `bar-manifest` (declarations) to the bar app (spine AD-14).
- Ship `ags-bar-validate` that runs `validateLayout` + `validateIcons` over `icons.json` / `bar.json` / the manifest.
- Wire it into provisioning as a **strict** install gate; the bar runs the same functions **leniently** at startup.
- Give each runtime artifact its own `schemaVersion`; an unknown version degrades, never crashes.

## Non-goals

- Not the codegen of the event contract (separate `contracts` work).
- Not the layout chain itself (spine AD-9) — only its validation.
- No new runtime artifact beyond `icons.json` / optional `bar.json` / `colors.gtk.css`.

## Impact

- `dotfiles/config/ags/bar/**` (the manifest + startup validation).
- `src/provisioning/**` (the install-time gate).
- A platform CLI `ags-bar-validate`.
