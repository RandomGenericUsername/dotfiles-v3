# Tasks — repair-package-manifest-drift

## 1. Per-key review (blocking; nothing below is legitimate without it)

- [x] 1.1 Measure the drift in all three lists and record which direction it runs
      (result: 3 manifest keys, 8 arch keys, 8 debian keys — all "in data, not in test")
- [x] 1.2 For each of the 8 drifted arch keys run `git log -S'<key>'` and read the
      introducing commit (`capture`, `portals`, `lock`, `dunst`, `thunar`, `libva-utils`,
      `nm-connection-editor`, `speedtest`)
- [x] 1.3 Same for the 8 Debian keys, reviewing the Debian **values** separately
      (`nm-connection-editor` → `network-manager-gnome`, a real per-manager mapping)
- [x] 1.4 Call out `libva-utils` explicitly as introduced by `e9beedc4`, the immediately
      preceding commit on this branch's base — not pre-existing drift — with its
      gpu-screen-recorder "your gpu does not support 'vpX'" rationale
- [x] 1.5 Record a written verdict per key in design.md §1 (what it is, why it was added,
      whether deliberate); flag anything untraceable, accidental, or duplicated
- [x] 1.6 Verdict on all 16 keys: every one traces to a commit with a named consumer.
      Nothing accidental found. The `test_*_packages_cover_exactly_logical_set` lock itself
      is the thing that never kept up.

## 2. Data correction where the data is wrong

- [x] 2.1 Check the owner's premise: are `speedtest` and `nm-connection-editor` really
      absent from `packages.yaml`? — **No**: already present at lines 19 and 91 from the
      bulk AGS import `496a0b4d`, alongside their `group_vars` keys. Adding them would
      create duplicates and fail the pre-existing duplicate-name check. Recorded in
      design.md §2; no data edit.
- [x] 2.2 Sweep the same direction (in `group_vars`, absent from the manifest) for any
      others — none found. Rollup keys (`capture`, `portals`, `lock`) and per-distro
      toolchain keys (`zsh`, `terminal`, `container_engine`, `display_manager`,
      `adw_gtk_theme`, `nvm`) are structural, not missing manifest entries.
- [x] 2.3 Sweep the reverse direction (in the manifest, no provisioning path installs it)
      — found 3: `lf`, `hyprcursor`, `xdg-utils`. **Not fixed** (unverifiable Debian
      names); pinned as an exact orphan set and flagged in design.md §5.

## 3. Re-snapshot the three expectations

- [x] 3.1 `_LOGICAL_PACKAGE_KEYS`: add `capture`, `portals`, `lock`, `dunst`, `thunar`,
      `libva-utils`, `nm-connection-editor`, `speedtest`, each with a one-line provenance
      comment. `_ARCH_EXTRA_KEYS` unchanged.
- [x] 3.2 `test_packages_manifest_has_verified_set`: add `libva-utils`,
      `nm-connection-editor`, `speedtest`, with a comment recording that the DATA was
      already correct and only the lock lagged.
- [x] 3.3 Confirm no assertion was weakened: all three remain exact-set equality; no key
      removed from any lock.
- [x] 3.4 Confirm the `pre-existing drift lock` comment survives.

## 4. New machine-checkable invariants

- [x] 4.1 `_rollup_problems` — non-empty list values; each member matches
      `^[A-Za-z0-9][A-Za-z0-9+._-]{0,99}$`; asserted for both distros
- [x] 4.2 `_empty_value_problems` — no `None`, blank, or non-string/non-list value;
      catches what `reject('equalto', '')` silently drops and what
      `str(None).strip()` wrongly passes
- [x] 4.3 `_duplicate_problems` — one name per key per map, with the Debian
      `bluez`/`bluez-utils` merge as the sole exception, pinned as an exact pair
- [x] 4.4 reachability — every `packages.yaml` entry reachable from a `group_vars` key,
      a `group_vars` value, or `aur_packages` (with `-git` stripped), against an exact
      pinned orphan set
- [x] 4.5 Negative tests for every invariant, plus positive controls so a helper that
      rejects valid shapes is caught too
- [x] 4.6 Prove each invariant fires against the REAL files, not just synthetic inputs:
      inject each defect into `group_vars` / `packages.yaml`, run the suite, restore.
      10 defects injected, 10 invariants fired, 6 of them with the exact-set lock still
      GREEN (design.md §4.1). Restore verified clean.
- [x] 4.7 Document in design.md §4 why the bookkeeping lock is KEPT and what each
      invariant catches that it cannot

## 5. Openspec change

- [x] 5.1 `proposal.md` — why, what changes, non-goals (including that the data needed
      no edit)
- [x] 5.2 `design.md` — per-key review table, the `libva-utils` call-out, the corrected
      premise, the lock-vs-invariants rationale, alternatives rejected
- [x] 5.3 `specs/repair-package-manifest-drift/spec.md` — `## ADDED Requirements`,
      `### Requirement:`, `#### Scenario:` matching `fix-capture-webm-codec`
- [x] 5.4 `tasks.md` — this file

## 6. Verification

- [x] 6.1 `uv run --directory src/provisioning pytest tests/unit -q` → **0 failed**, 711
      passed (baseline 3 failed / 685 passed; +26 new tests)
- [x] 6.2 `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at 33 used / 28 styled
- [x] 6.3 `make capture-typecheck` → 0 errors
- [x] 6.4 `make capture-test` → 115 tests, 115 pass
- [x] 6.5 capture `pytest tests/` → 97 passed
- [x] 6.6 `roles/verify/**` untouched; committed fix `98403c74` intact
- [x] 6.7 no `node_modules` staged (gitignored); nothing committed