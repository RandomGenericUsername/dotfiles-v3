## ADDED Requirements

### Requirement: Every drifted package key SHALL be individually traced to its introducing commit

Before any test expectation is re-snapshotted, each key present in a `group_vars` `packages`
map (or in the logical manifest) but missing from the test's hardcoded expectation SHALL be
traced with `git log -S'<key>'` to the commit that introduced it, that commit SHALL be read,
and a written verdict — what the key is, why it was added, and whether it looks deliberate —
SHALL be recorded. A bulk accept of the whole diff SHALL NOT satisfy this requirement.

Rationale: the drift is one-directional (a package was added to the DATA, the expectation
never followed), so every missing key corresponds to a real fix somebody already shipped.
Accepting the diff wholesale would lock in a key nobody inspected — the exact failure this
change exists to prevent.

#### Scenario: A key traces to a commit and a deliberate rationale
- **WHEN** `capture` is missing from `_LOGICAL_PACKAGE_KEYS` and `git log -S'capture' -- src/provisioning/ansible/group_vars/arch.yml` returns `4a57afc2`
- **THEN** the review records the commit subject, the reason (the capture tool shells `grim`/`slurp` and the clipboard watcher needs `wl-paste --watch`; all three were absent while verify stayed green), and the verdict "deliberate"

#### Scenario: A key introduced by the immediately preceding commit is called out
- **WHEN** `libva-utils` is found missing and `git log -S'libva-utils'` returns `e9beedc4` — the commit immediately preceding this work on this branch's base
- **THEN** the review names it explicitly as NOT pre-existing drift, with its rationale (the VA-API probe `vainfo` that gpu-screen-recorder names verbatim in its "your gpu does not support 'vpX'" failure), rather than listing it as ordinary drift

#### Scenario: A key that cannot be traced is reported
- **WHEN** a drifted key has no introducing commit, or its commit's message does not account for it and no consumer corroborates it
- **THEN** the review flags it as untraceable or accidental, and it is NOT absorbed into the snapshot

### Requirement: The re-snapshotted expectation SHALL match the reviewed data, and the data SHALL be corrected where it is wrong

Where review finds the DATA to be wrong (a package installed on the host and provisioned in
`group_vars` but absent from the logical manifest), the manifest SHALL be corrected. The test
expectation SHALL then be re-snapshotted to the reviewed reality, key by key.

#### Scenario: The data is already correct and only the lock lagged
- **WHEN** review finds `speedtest` and `nm-connection-editor` already present in `dotfiles/provisioning/packages.yaml` (lines 19 and 91, added by the bulk AGS import `496a0b4d`) and in both `group_vars` maps
- **THEN** no manifest entry is added — adding them would create duplicate entries and fail the pre-existing duplicate-name check — and the test expectation alone is extended

#### Scenario: The data is genuinely missing a package
- **WHEN** review finds a package in a `group_vars` `packages` map that has no logical-manifest entry
- **THEN** the entry is added to `dotfiles/provisioning/packages.yaml` before the expectation is re-snapshotted

### Requirement: The hardcoded drift locks SHALL be retained

The exact-set assertions SHALL remain hardcoded. They SHALL NOT be replaced by a derived
comparison between the three lists, and the `pre-existing drift lock` comment SHALL NOT be
removed. Rationale: the lock is the only signal in the repo that catches silent Arch-vs-Debian
divergence of the package set.

#### Scenario: Divergence between the two distros still fails
- **WHEN** a key is added to `group_vars/arch.yml` but not to `group_vars/debian-family.yml`
- **THEN** `test_debian_family_packages_cover_exactly_logical_set` fails with the key named as extra on one side and missing on the other

#### Scenario: An existing Drift-lock key is removed
- **WHEN** `hyprmod` is deleted from the Arch map
- **THEN** `test_arch_packages_cover_exactly_logical_set` fails, naming `hyprmod`

### Requirement: Machine-checkable invariants SHALL catch package-list defects an exact-set comparison cannot

Alongside the retained locks, the following invariants SHALL be asserted against the real
`group_vars` data. Each addresses a defect class that keeps every KEY present, and therefore
leaves the exact-set lock green:

1. Every list-valued (rollup) key SHALL have a non-empty list, and every member SHALL match `^[A-Za-z0-9][A-Za-z0-9+._-]{0,99}$`.
2. No key SHALL have an empty, blank, `None`, or non-string/non-list value.
3. No package name SHALL be declared under two different keys in the same map, except documented exceptions pinned as exact key pairs.
4. Every entry in `packages.yaml` SHALL be reachable from a provisioning path — a `group_vars` key, a `group_vars` value, or the `aur_packages` AUR channel (compared with the upstream `-git` suffix stripped) — except a pinned, exact set of entries that no path installs.

#### Scenario: An empty rollup is caught
- **WHEN** `group_vars/arch.yml` declares `capture:` with no list
- **THEN** the rollup invariant fails naming `capture` as an EMPTY rollup — while `test_arch_packages_cover_exactly_logical_set` still passes, because the key is present

#### Scenario: A space- or comma-joined member is caught
- **WHEN** `capture` is declared as `[grim, "slurp wl-clipboard"]` or `[grim,slurp]`
- **THEN** the rollup invariant fails naming the member as not a single plausible package name — the glued string would install a package literally named that

#### Scenario: A blank value is caught even though the role drops it silently
- **WHEN** `thunar:` is declared with no value, or `thunar: "   "`
- **THEN** the empty-value invariant fails naming `thunar` — the packages role's `reject('equalto', '')` would drop it without a word, and `str(None).strip()` is truthy so the existing non-empty-name assertions do not catch it

#### Scenario: A package under two keys is caught
- **WHEN** `rofi` is declared under both `rofi` and `launcher`
- **THEN** the duplicate invariant fails naming `rofi` and both keys

#### Scenario: The one documented duplicate stays allowed and stays exact
- **WHEN** `group_vars/debian-family.yml` maps both `bluez` and `bluez-utils` to `bluez` (Debian merges `bluez-utils` into `bluez`)
- **THEN** the duplicate invariant passes for that map, a separate assertion pins that this pair is the ONLY unexempted duplicate, and any OTHER duplicate in that map fails

#### Scenario: A manifest entry nothing installs is caught
- **WHEN** a name appears in `packages.yaml` but is neither a `group_vars` key, a `group_vars` value, nor an `aur_packages` entry
- **THEN** the reachability invariant fails naming it, unless it is in the pinned exception set

#### Scenario: The orphan exception set cannot silently grow
- **WHEN** the reachability invariant's orphan set differs from the pinned set in either direction — a new unlisted orphan, or a pinned entry that became reachable
- **THEN** the test fails and the message names which entries are unexpected and which are no longer orphaned

### Requirement: Every new invariant SHALL have a negative test proving it fires

Each invariant above SHALL be accompanied by at least one test that feeds the same
comparison helper a synthetic broken value and asserts the failure is reported. A detector
whose firing has not been demonstrated is a comment, not an invariant.

#### Scenario: Negative tests are green against the real suite
- **WHEN** the full unit suite runs
- **THEN** every negative test passes because its synthetic input genuinely trips its invariant — and the invariant's positive counterpart fails only on real data that is actually broken