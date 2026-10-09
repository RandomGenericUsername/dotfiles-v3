## Why

`bar-typecheck` landed on this branch to close a real hole: `ags bundle`
**transpiles without type checking**, and a `bluetoothFailure` re-export of a
deleted accessor bundled clean (`exit 0`). The gate works — it is green on the
Bluetooth-owned files.

But it is green by *tolerating everything else*:

```
==> bar-typecheck
    tolerated third-party errors (/usr/share/ags/js): 29
    NOTE: pre-existing errors outside the Bluetooth-owned files (do not fail this gate; fix in their own change):
      11 dotfiles/config/ags/app.tsx
       5 dotfiles/config/ags/audio/AudioPopup.tsx
       5 dotfiles/config/ags/bar/widgets/battery.tsx
       3 dotfiles/config/ags/tests/ts/battery-presentation.test.ts
       3 dotfiles/config/ags/tests/ts/battery-icon.test.ts
       3 dotfiles/config/ags/services/wifi-service.ts
       3 dotfiles/config/ags/components/battery/BatteryContent.tsx
       2 ... (5 more files)
```

**48 errors across 15 files, 11 distinct TS codes** — printed on every `make
gates` run and failing nothing.

Tolerating them was the right call to unblock the Bluetooth work: 11 of the 48
were in `app.tsx`, which the Bluetooth change had just edited, and stopping to
clear the whole tree would have blocked the panel on unrelated work.

It is the wrong resting state. The gate's pass/fail line currently means *"the
Bluetooth files are clean"*, not *"the bar tree typechecks"*. Every new file
lands on top of 48 known-broken ones, and the tolerance list has no expiry and
no owner.

## What Changes

The investigation (design §1) found that **three of the five categories are
single-root-cause and account for ~30 of the 48 errors**, and that the largest
remaining category is *suspected to be downstream of one of them* — a failed
`createBinding` collapses its return type to a union, which then poisons every
JSX prop it feeds.

So this change is **staged, with a re-measurement gate after each stage**, not 48
individual fixes:

1. **Scope corrections and single-cause fixes** — three edits expected to clear
   ~30 errors: the bar config sweeping in `tests/` (which has its own gate, 8
   errors), the `app.add_window` element type (11 errors, all in one file), and
   `createBinding` property casing (~11 errors).
2. **Re-measure.** Category D is a hypothesis until this runs. If it dissolves,
   it needs no work; if it does not, it is scoped then, with the residue known
   rather than assumed.
3. **The genuine safety errors last** — `connection` possibly null, `Object is of
   type 'unknown'`, `ConstructorProps` missing fields. These are real defects
   that the typechecker earned, and they are fixed as such rather than silenced.
4. **Tighten the gate**: once the tree is clean, `bar-typecheck` stops tolerating
   our own tree and fails on any error, the same posture `capture-typecheck`
   already has. The `NOTE:` block and the owner-file list are deleted, not
   widened.

## Capabilities

### New Capabilities

- `bar-typecheck-errors`: the bar tree typechecks with zero errors in its own
  files, and the gate enforces that rather than reporting it.

### Modified Capabilities

- `bar-typecheck` (introduced on this branch): its tolerance for non-Bluetooth
  files is removed. The Bluetooth-owned file list stops being a whitelist and
  becomes just the set of files that happened to be touched first.
