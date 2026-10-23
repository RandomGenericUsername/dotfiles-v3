# Tasks

## 1. The manifest + validators

- [ ] 1.1 Add the pure `bar-manifest` (capabilities + params + icon groups) to the bar app. Verify: importing it needs no GJS (`node --test` import).
- [ ] 1.2 Implement `validateLayout` + `validateIcons` over the **declarations** (not runtime `Capability` objects). Verify: unit tests for each `IssueCode`.
- [ ] 1.3 Ship the `ags-bar-validate` CLI. Verify: it exits non-zero on a bad layout, zero on a good one.

## 2. Enforce

- [x] 2.1 Wire `ags-bar-validate` into provisioning as a **strict** gate. Verify: a bad `icons.json` fails the install.
- [x] 2.2 Run the same functions **leniently** in the bar at startup (skip unknown widget, apply defaults, blank a missing glyph). Verify: the bar starts against a deliberately broken layout.
- [x] 2.3 Add per-artifact `schemaVersion`; degrade on unknown. Verify: an unknown version warns and runs.

## 3. Gate

- [ ] 3.1 `make gates-ci` green.
