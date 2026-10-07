# Design — repair-package-manifest-drift

## 0. The drift, measured

Three lists, one-directional drift: every missing key exists in the data and is absent from the
test's hardcoded expectation. Nothing was expected-but-missing.

| list | expected | actual | missing keys |
|---|---|---|---|
| `dotfiles/provisioning/packages.yaml` | 45 | 48 | `libva-utils`, `nm-connection-editor`, `speedtest` |
| `group_vars/arch.yml` | 37 | 45 | `capture`, `dunst`, `libva-utils`, `lock`, `nm-connection-editor`, `portals`, `speedtest`, `thunar` |
| `group_vars/debian-family.yml` | 37 | 45 | same eight |

Three of the eight (`capture`, `portals`, `lock`) are **rollup keys whose value is a list**, not
a scalar name. The remaining five are individual packages.

## 1. Per-key review (the point of this change)

Method: `git log -S'<key>' -- <file>` per key, then the introducing commit was read in full.
Owner requirement: per-key review, not a bulk accept. Every row below is traceable.

### Arch (`group_vars/arch.yml`) — 8 drifted keys

| key | introducing commit | what it is / why it was added | verdict |
|---|---|---|---|
| `capture` | `4a57afc2` "fix(packages): declare grim/slurp/wl-clipboard and gate them in verify" (inumaki, 2026-09-30) | Rollup `[grim, slurp, wl-clipboard]`. The capture tool shells `grim`/`slurp`/`wl-copy`; the runtime clipboard watcher needs `wl-paste --watch`. All three were absent while verify stayed green — capture failed with `[Errno 2] slurp`. Same commit pinned the four binaries in `verify_system_binaries`. | **Deliberate.** Direct response to an observed runtime failure; the commit also wires the verify gate so it cannot recur. |
| `portals` | `b6ecb27e` "fix(packages): declare session services, lock stack, dunst, thunar; gate lock/polkit binaries" (inumaki, 2026-09-30) | Rollup `[hyprpolkitagent, xdg-desktop-portal-hyprland, xdg-desktop-portal-gtk]`. `autostart.lua` starts these at login; undeclared means silent start failure — broken auth dialogs, no screen-share/screencast. | **Deliberate.** Traced to a named consumer (`autostart.lua`). |
| `lock` | `b6ecb27e` (same commit) | Rollup `[hyprlock, hypridle]`. The file's own comment says "presence only until lock/idle binds + config land — no role consumes them yet." | **Deliberate, but consumer-pending.** The key exists ahead of its consumer; both binaries are pinned in verify, so an omission is loud. Accept. |
| `dunst` | `b6ecb27e` (same commit) | Installed **only to be masked** — `gui_tools` masks it because the AGS overlay owns notifications. verify's mask gate hard-requires the unit file, so an undeclared dunst fails fresh machines at the gate. | **Deliberate and load-bearing** — it is a negative requirement (must be present to be masked). |
| `thunar` | `b6ecb27e` (same commit) | File manager launched by `keybindings.lua`; the file's comment says "host-default luck only." | **Deliberate.** Traceable to a real consumer. |
| `libva-utils` | `e9beedc4` "fix(provisioning): declare libva-utils; repair an unparseable packages manifest" (opencode, 2026-10-02) | The VA-API codec probe `vainfo`. gpu-screen-recorder names it verbatim in its own "your gpu does not support 'vpX'" failure, so without it the capture tool cannot tell a hardware codec limit (WebM's gsr default VP8) from a missing VA driver — from the launcher both look identical: `start` reports success, no file appears. | **Deliberate — see §1.1, it is NOT pre-existing drift.** |
| `nm-connection-editor` | `496a0b4d` "backup" (Claude Code, 2026-09-26) | The NM GUI connection editor; comment: "standalone extra package (split from network-manager-applet); AGS Wi-Fi Settings footer target." Added in the bulk AGS import alongside the Wi-Fi settings panel work. | **Deliberate in effect, weakly-sourced commit.** `496a0b4d` is a squashed bulk import ("backup", 1 commit for a whole feature batch), so the message does not explain the addition. Corroborated by `openspec/changes/add-speedtest-notifications` and `wifi-settings-nm-editor`, and by `speedtest-service.ts` / the Wi-Fi footer actually consuming both. |
| `speedtest` | `496a0b4d` (same bulk import) | `speedtest-cli`. Consumed by `dotfiles/config/ags/services/speedtest-service.ts`, which shells the binary and parses its JSON (the file documents the `speedtest` vs `speedtest-cli` binary-name distinction explicitly). | **Deliberate in effect, weakly-sourced commit** — same corroboration as above. |

### Debian (`group_vars/debian-family.yml`) — the same 8 keys

`git log -S` returns the same introducing commits for every one of the eight: Debian map
changes ride the same commits as the Arch map (NFR-3 distro isolation is applied per pair).
The Debian *values* were reviewed separately and each is a real apt name:

| key | Debian value | verdict |
|---|---|---|
| `capture` | `[grim, slurp, wl-clipboard]` | Same upstream names; the file notes all three exist in the Debian archive. |
| `portals` | `[hyprpolkitagent, xdg-desktop-portal-hyprland, xdg-desktop-portal-gtk]` | Upstream names kept; availability is a packages-role concern (the file says so for `hyprland` too). |
| `lock` | `[hyprlock, hypridle]` | Same as Arch. |
| `dunst` | `dunst` | Same install-to-mask rationale. |
| `thunar` | `thunar` | Same. |
| `libva-utils` | `libva-utils` | Same package name on both distros; `vainfo` ships in `libva-utils` on Debian too. |
| `nm-connection-editor` | `network-manager-gnome` | **Not the same name** — Debian ships the editor inside `network-manager-gnome`. Correct per-manager mapping, not drift. |
| `speedtest` | `speedtest-cli` | Same name on both distros. |

### 1.1 `libva-utils` — called out explicitly

`libva-utils` is **not** pre-existing drift. It was introduced by `e9beedc4`, the commit
immediately preceding this work on this branch's base, as part of diagnosing why WebM
recordings silently produce no file. Without `vainfo`, the capture tool cannot distinguish
"this GPU cannot encode VP8" (a hardware limit — WebM's gsr default codec) from "the VA driver
is not wired up" (a provisioning defect). From the launcher the two are indistinguishable:
`start` reports `{"state": "recording"}` and no file ever appears.

That same commit also discovered `packages.yaml` was **unparseable** — lines 82-87 were
indented 3 spaces where the rest use 2, so `yaml.safe_load` and Ansible's own loader both
raised `ParserError`. Nothing loads the manifest except its own test reader, so it went
unnoticed, and it was *masking* the very failure now being fixed.

`e9beedc4` explicitly deferred this work: *"Pre-existing, NOT fixed here: the three now-red
tests … `test_*_packages_cover_exactly_logical_set` encodes an expectation that predates the
rollup keys (`capture:`, `terminal:`, `zsh:`, `lock:`, `portals:`) and AUR routing in
`aur_packages` — an exact set match cannot hold against that structure. Recorded, not
repaired; that is its own change."* This is that change.

### 1.2 Nothing untraceable, nothing accidental

Every one of the 16 drifted keys traces to a specific commit, and every one is a real
declaration with a named consumer (config file, service, keybinding, or verify gate). **No
key looks accidental, duplicated, or wrong.** The one thing that does not look deliberate is
the *test lock* itself: it was written before the rollup keys existed and never revisited
across three subsequent data fixes.

## 2. Why no data change was needed — the owner's premise, checked

The instruction was: *"`packages.yaml` is missing packages that ARE in `group_vars` — add
them. Specifically `speedtest` and `nm-connection-editor` are installed on the host but
absent from the logical manifest."*

Checked, and the premise does not hold: both are **already in `packages.yaml`**.

```
$ grep -n "speedtest\|nm-connection-editor" dotfiles/provisioning/packages.yaml
19:  - name: nm-connection-editor  # NM GUI connection editor (AGS Wi-Fi Settings footer target)
91:  - name: speedtest          # Ookla speedtest CLI (network speed measurements)
```

Line 19 came in with the AGS Wi-Fi settings panel, line 91 with the AGS speedtest service —
both are in the bulk import `496a0b4d`, the same commit that added the group_vars keys. Both
are host-installed (`pacman -Qi nm-connection-editor speedtest-cli` → present). They are
absent from the **test expectation**, not from the manifest.

Adding them would have produced duplicate entries and failed the pre-existing
`len(names) == len(set(names))` duplicate check in the very test being repaired. No other
package in the same direction was found: every remaining manifest entry is either a group_vars
key, a group_vars value, or in the AUR channel (see §5).

**Conclusion: the drift was entirely in the lock, not in the data.** This is the opposite of
the instruction's assumption and it is worth stating plainly rather than inventing a data edit
to match it.

## 3. The re-snapshotted expectations

`_LOGICAL_PACKAGE_KEYS` (shared base, 37 → 45 keys): `+ capture, portals, lock, dunst, thunar,
libva-utils, nm-connection-editor, speedtest`. `_ARCH_EXTRA_KEYS` unchanged.

`test_packages_manifest_has_verified_set` (45 → 48 names): `+ libva-utils,
nm-connection-editor, speedtest`.

Every added entry traces to a row in §1. Nothing else was touched, no key removed, no test
weakened: the assertions remain exact-set equality in all three tests.

## 4. Why keep the bookkeeping lock — and what the new invariants add

The lock is KEPT, on purpose. It is not useless; it is **low-value on its own**:

- It has fired three times without anyone acting, because acting on it means hand-diffing three
  copies of one list. A red test nobody acts on trains everyone to ignore red tests.
- It cannot catch a single real defect class, because it compares **key sets only**. Every
  defect below keeps the key present, so the lock stays green through all of them.

What it DOES still buy: it is the only thing that catches *silent* divergence between the
logical layer and the per-manager layer, which is what `libva-utils` and the rollups are. If a
future change adds a package to Arch and forgets Debian, no other check in the repo notices.
That is worth a red test even if that red test has fired three times.

So the lock stays and four invariants are added **underneath** it, in
`TestPackageListInvariants` — defects an exact-set comparison structurally cannot see:

| # | invariant | defect it catches that the lock cannot |
|---|---|---|
| 1 | Rollup list values are non-empty, and every member matches `^[A-Za-z0-9][A-Za-z0-9+._-]{0,99}$` | `capture: []` installs nothing; `capture: ["grim", "slurp wl-clipboard"]` or `["grim,slurp"]` installs a package literally named that (the classic "forgot the list dash" YAML bug). The key is present either way — **lock stays green**. |
| 2 | No key has an empty / blank / non-string value | The packages role flattens with `reject('equalto', '')`, so `thunar:` (bare) or `thunar: "  "` is dropped **without a word**. The key is present, so the lock stays green. `test_*_package_names_are_non_empty` did NOT catch this: `str(None).strip()` is `"None"`, which is truthy. |
| 3 | No package declared under two keys in the same map | Installs twice, and a later edit to one copy silently diverges from the other. One documented exception, asserted as an exact pair: Debian's `bluez` / `bluez-utils` merge (`bluez-utils` is merged into `bluez` on Debian — the file says so). |
| 4 | Every `packages.yaml` entry is reachable from a provisioning path | A manifest entry nothing installs is a promise a fresh machine breaks — it only works because someone ran the manager by hand. Reachable = a group_vars key, a group_vars value, or `aur_packages` (with the upstream `-git` suffix stripped, so logical `tidal-hifi` matches AUR `tidal-hifi-git`). |

Invariant 4 found a real defect immediately — see §5.

### 4.1 Each invariant was proven to fire against the real files

The negative tests cover the helpers in isolation. To rule out "the invariant is
structurally unreachable", each defect was injected into the **real** `group_vars` /
`packages.yaml` files (surgically replacing an existing value so the YAML stays valid),
the suite was run, and the file restored:

| defect injected | invariant that fired | exact-set lock |
|---|---|---|
| `capture: []` | rollup non-empty | **GREEN** — cannot see it |
| `capture: [grim, "slurp wl-clipboard"]` | single-name regex | **GREEN** |
| `capture: [grim, grim,slurp]` | single-name regex | **GREEN** |
| `thunar:` (bare → `None`) | no empty value | **GREEN** |
| `thunar: "   "` | no empty value | **GREEN** |
| `thunar: 42` | no empty value | **GREEN** |
| `rofi` under both `rofi` and `launcher` | no duplicate key | red |
| a 2nd duplicate in `debian-family.yml` | pinned-exemption assertion | red |
| `promised-but-unprovisioned` added to `packages.yaml` | reachability | **GREEN** |
| `lf: lf` added (a pinned orphan gains an installer) | pinned-exception-set equality | red |

Every "GREEN" row is a defect the retained lock is structurally blind to, which is the whole
argument for adding the invariants rather than relying on the lock alone. Restore verified
clean (`git diff --stat` on `group_vars` → empty).

Each invariant has a matching negative test in `TestPackageListInvariantsNegative` that feeds
the same helper a synthetic broken map and asserts it complains. A defect detector nobody
proved fires is a comment.

## 5. Finding: three manifest entries no provisioning path installs

Invariant 4 failed on its first run against real data. `packages.yaml` declares `lf`,
`hyprcursor`, and `xdg-utils`; none is a group_vars key, a group_vars value, or in
`aur_packages`. `grep -rn 'hyprcursor\|xdg-utils' src/provisioning/ansible` → no hits. Only
the packages role and the display_manager role install anything, so a fresh machine gets
none of the three.

Two of them are host-installed right now (`pacman -Qi hyprcursor xdg-utils` → present;
`lf` is not), which is exactly how this drift happened in the first place.

**Not fixed here, deliberately.** Fixing it means choosing Debian package names that cannot be
verified without a Debian host, and adding packages to a working provisioning set is not a
drive-by. Instead they are pinned as `_DECLARED_NOT_PROVISIONED = frozenset({"lf",
"hyprcursor", "xdg-utils"})` and asserted as an **exact set**: an unlisted orphan fails the
test, and growing the set is a deliberate edit to one visible line. The assertion message
names both directions (unexpected orphan / no-longer-orphaned). Flagged for the owner as the
follow-up this change should spawn.

## 6. Alternatives rejected

- **Delete the exact-set locks and derive the expectations** (e.g. `set(packages.keys()) ==
  set(manifest)`). Rejected by explicit instruction and on merit: it removes the only signal
  that catches Arch-vs-Debian divergence, and the file carries an explicit
  `pre-existing drift lock` comment recording that intent.
- **Generate `group_vars` from `packages.yaml`.** Rejected: per-manager names and
  Arch-only extras (`adw_gtk_theme`, `power-options-gtk`, `hyprmod`, `nvm`) are exactly what
  NFR-3 keeps in Ansible, and a generator would move them into Python or the manifest.
- **Absorb `lf` / `hyprcursor` / `xdg-utils` into the manifest lock as "fine".** They already
  are in it. That is the status quo that hid the finding; pinning them as an exact orphan set
  is what keeps it visible.
- **Relax the invariants to warnings.** A warning in a suite nobody reads is a comment.

## 7. Verification

- `uv run --directory src/provisioning pytest tests/unit -q` → **0 failed**, 711 passed
  (baseline 3 failed / 685 passed).
- `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at 33 used / 28 styled.
- `make capture-typecheck` → 0 errors. `make capture-test` → 115 tests, 115 pass.
- capture `pytest tests/` → 97 passed.
- `roles/verify/**` untouched; the committed check-gate fix (`98403c74`) is intact.