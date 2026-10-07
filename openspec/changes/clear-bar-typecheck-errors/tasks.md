## 1. Baseline the count, and correct the reported figure

- [ ] 1.1 Capture the baseline exactly as the gate sees it:
      ```bash
      npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json \
        > /tmp/bar-ts-baseline.txt 2>&1
      grep -E "^dotfiles/config/ags/" /tmp/bar-ts-baseline.txt | wc -l
      ```
      Expected: **48** in our tree, plus 29 tolerated under `/usr/share/ags/js`.
- [ ] 1.2 Confirm the per-file table in design §1 matches, and record any drift
      in the change rather than adjusting the table silently.
- [ ] 1.3 Confirm **`ags bundle` still exits 0** with these 48 errors present.
      This is the premise of the whole change: the bundler does not typecheck.
      (Precedent: the deleted-accessor re-export on this branch bundled clean.)

## 2. Category A — stop the bar config sweeping in `tests/`

- [ ] 2.1 Add `"tests"` to `tsconfig.bar.json`'s `exclude`, with a comment naming
      `tests/tsconfig.tests.json` as the owner and `ags-test` as the gate.
- [ ] 2.2 Re-measure. Expected: **48 → 40**; the 8 `tests/ts/*.test.ts` errors
      gone.
- [ ] 2.3 Confirm `make ags-test` still passes — the tests must keep their
      `@types/node` and `allowImportingTsExtensions` from their own config, and
      nothing in this step may weaken that.
- [ ] 2.4 Negative proof: temporarily point `ags-test` at a config without
      `"types": ["node"]` and confirm the suite still typechecks from its own
      config path, i.e. the bar's `exclude` is not load-bearing for the tests.

## 3. Category B — one type for `app.add_window`

- [ ] 3.1 Reproduce in isolation:
      ```bash
      grep -c "TS2345.*not assignable to parameter of type 'Window'" /tmp/bar-ts-baseline.txt
      ```
      Expected: **11**, all in `app.tsx`.
- [ ] 3.2 Add a single typed helper in `app.tsx` (e.g. `addWindow(w)`) that
      accepts the JSX element type and forwards to `app.add_window`, with the
      cast justified in a comment: these elements *are* `Gtk.Window`s at runtime
      and only the static type disagrees.
- [ ] 3.3 Convert all 12 registrations to the helper. Re-measure. Expected:
      **40 → 29**.
- [ ] 3.4 Verify the bar still starts and every window appears — this is the one
      fix in A/B/C that touches a code path rather than a config, so it gets a
      live check, not just a green typecheck.

## 4. Category C — `createBinding` property casing

- [ ] 4.1 List the call sites and, for each, confirm the camelCase name is the
      same GObject property (design §2 C, `kebabify` round-trip). Expected sites:
      `bar/widgets/battery.tsx`, `components/battery/BatteryContent.tsx`,
      `components/sliders/VolumeSlider.tsx` (`"default-speaker"`),
      `bar/widgets/workspaces.tsx` (`"focused-workspace"`).
- [ ] 4.2 Change each literal to the declared casing.
- [ ] 4.3 Re-measure. Expected: **29 → ~18**. Record the exact delta.
- [ ] 4.4 **Live-check the affected surfaces** — the battery bar widget, the
      volume slider, and the workspace indicator. Their values must still update:
      `kebabify` makes the spellings equivalent, but that is the claim being
      tested, not an assumption.
- [ ] 4.5 For any site where the camelCase name does **not** round-trip, stop and
      treat it as a real defect rather than a rename.

## 5. The re-measurement gate — is category D real?

- [ ] 5.1 Regenerate the residue:
      ```bash
      npx tsc --noEmit -p dotfiles/config/ags/tsconfig.bar.json \
        | grep -E "^dotfiles/config/ags/" > /tmp/bar-ts-after-c.txt
      cat /tmp/bar-ts-after-c.txt
      ```
- [ ] 5.2 Classify every remaining error as **D** (gnim JSX/Accessor typing) or
      **E** (genuine safety). Record the split in `design.md`.
- [ ] 5.3 State whether the "D is downstream of C" hypothesis held. **Either
      answer is a result; do not bend the classification to fit it.**
- [ ] 5.4 **Scope D from this residue only.** If D is now empty, delete §2 D from
      the design and note the hypothesis was confirmed. If it is not, enumerate
      the specific errors; do not carry a category forward as a placeholder.

## 6. Category E — the genuine safety errors

- [ ] 6.1 `services/nm-client.ts:103` and `services/mpris-service.ts:400` —
      `'connection' is possibly 'null'`. Fix by narrowing the local, not by
      `!`. If the null case is genuinely impossible, assert it with a comment
      saying why.
- [ ] 6.2 `services/wifi-service.ts:581,649,786` — `Object is of type
      'unknown'` from `recursiveUnpack()[0] as string[]`-style access. Type the
      unpack properly or assert with a reason.
- [ ] 6.3 `lib/status-notifier.ts:82` — `ConstructorProps` missing
      `parameter_type`/`state`/etc. Determine whether the object is genuinely
      incomplete or the type is over-strict, and fix the correct side.
- [ ] 6.4 Re-measure. Expected: **0** errors in `dotfiles/config/ags/`.

## 7. Make the gate strict

- [ ] 7.1 Delete the `NOTE:` tolerance block and the Bluetooth-owned file list
      from the `bar-typecheck` target. The gate fails on **any** error in
      `dotfiles/config/ags/`; the only tolerance left is the third-party
      `/usr/share/ags/js` bucket, by location, exactly as `capture-typecheck`.
- [ ] 7.2 Update the target's comment: it currently says the tolerance exists
      because the errors belong to "other workstreams' files, some diverged into
      other branches". That is no longer true.
- [ ] 7.3 Enable the captured **positive** run to be observed *reversed*:
      `ALLOWLIST`/tolerance checks that never fail are the "implemented but
      invisible" pattern this repo keeps hitting.

## 8. Prove the gate bites, in both directions

- [ ] 8.1 Plant `const BREAK_PROOF: number = "not a number"` in a **non**-
      Bluetooth bar file (e.g. `bar/widgets/tray.tsx`). `make bar-typecheck`
      **must** exit non-zero and name the file and line. Remove it.
- [ ] 8.2 Plant the same in a Bluetooth-owned file. Same expectation — proving
      the strictness is tree-wide, not file-specific.
- [ ] 8.3 Confirm a clean run reports **exit 0** and names no owned errors.

## 9. Gate and suite integrity

- [ ] 9.1 `make gates` exit 0, with `bar-typecheck` strict and green.
- [ ] 9.2 `make gates-ci` exit 0, and still excludes `capture-typecheck` and
      `bar-typecheck` (both need the desktop stack).
- [ ] 9.3 `make ags-test` unchanged and green.
- [ ] 9.4 `make capture-typecheck` unchanged and green — this change must not
      touch the capture config.
- [ ] 9.5 Run `make gates` **from a second worktree** as well. The gate's
      `node_modules` symlinks are per-directory and were only discovered to be
      missing elsewhere when that was first tried (`3b283830`); re-verify the
      provisioning holds.

## 10. Live verification

- [ ] 10.1 Deploy and restart the bar. Confirm no startup regressions and no new
      CSS/JS console errors.
- [ ] 10.2 Exercise every surface touched by a rename or a helper: bar windows
      all appear (B), battery widget (C), volume slider (C), workspace indicator
      (C).
- [ ] 10.3 Confirm behaviour is unchanged — this change is type-level, so any
      visible difference is a bug in it.

## 11. Recorded, not fixed

- [ ] 11.1 The 29 `/usr/share/ags/js` third-party errors — tolerated by
      location, as `capture-typecheck` does.
- [ ] 11.2 The four unresolved `gi://Astal*` typelibs — investigated and found
      **not** to cause any of our 48 (design §5). Record so it is not re-chased.
