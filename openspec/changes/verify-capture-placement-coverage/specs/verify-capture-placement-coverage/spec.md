## ADDED Requirements

### Requirement: Every placed capture file SHALL be asserted by the verify role

`verify_gui_tools_app_files` SHALL contain a dest for **every** source placed by
`gui_tools_app_files` under `ags-capture/`. A placement entry with no matching
verify entry is a placement regression no gate can see, because the gui_tools role
loops the placement list silently — a source absent from it is simply never
written to the spine, with no error and no warning.

Rationale: placement is per-file by deliberate design (`gui_tools/vars/main.yml:1–16`,
the review finding 2026-08-12 that a directory `copy` against a pre-existing dest
is a silent no-op). Per-file placement therefore has exactly one failure mode —
omission — and `verify_gui_tools_app_files` is the only thing standing between a
newly added file and a feature that is deployed nowhere.

#### Scenario: The five currently unasserted capture files are asserted

- **WHEN** `verify_gui_tools_app_files` is inspected
- **THEN** it contains `{{ install_dir | trim }}/config/ags-capture/domain/capture-request.ts`,
  `.../config/ags-capture/domain/cli-args.ts`, `.../config/ags-capture/ui/shared/rows.ts`,
  `.../config/ags-capture/ui/shared/groups.ts` and `.../config/ags-capture/ui/shared/icons.ts`

#### Scenario: `domain/cli-args.ts` absence is a dead capture, not a warning

- **GIVEN** the spine lacks `ags-capture/domain/cli-args.ts`
- **THEN** AGS fails to bundle the capture app, so **every** capture — screenshot
  and recording alike — fails
- **AND** this is the highest-consequence member of the set: it is the single
  request→argv translator and carries the two tokens the backend's argparse
  rejects (`--size 75`, not `75%`; `--audio mic`, not `microphone`)

#### Scenario: The `ui/shared/` builder kit is asserted

- **GIVEN** any of `ui/shared/{rows,groups,icons}.ts` is absent from the spine
- **THEN** the capture panel cannot bundle — both layouts import the kit, and it is
  what stops a second layout growing its own divergent row builders

### Requirement: Coverage SHALL be derived, not asserted by hand

The relationship between `gui_tools_app_files` and `verify_gui_tools_app_files`
SHALL be enforced by a test that **derives** the expected capture dest set from
the placement manifest and asserts full coverage. Both lists are maintained by
hand and independently; nothing derived one from the other, which is why five
placed files sat unasserted through a full review cycle.

A test that hardcodes the five paths would pass the moment a sixth placement entry
is added without a matching verify entry — reproducing the same silent gap under a
new name.

#### Scenario: A new placement entry without a verify entry fails loudly

- **WHEN** an entry is added to `gui_tools_app_files` under `ags-capture/` and the
  corresponding dest is NOT added to `verify_gui_tools_app_files`
- **THEN** `tests/unit/test_verify_role.py` fails, and the failure message names
  the missing spine-relative path

#### Scenario: The derivation uses a real YAML parser

- **WHEN** the coverage test reads the two vars files
- **THEN** it parses them with a real YAML loader through this file's existing
  `_vars()` / `_sibling_vars()` helpers — never a regex or a naive line scan over
  the YAML

Rationale: placement entries are flow mappings with interleaved rationale
comments, and the two files spell the spine seam differently
(`{{ gui_tools_spine_config_dir }}` vs `{{ install_dir | trim }}/config`). A
regex keyed on either list's textual shape silently matches the wrong set and
reports zero gaps.

#### Scenario: The comparison key survives the seam-spelling difference

- **WHEN** a placement dest `{{ gui_tools_spine_config_dir }}/ags-capture/<X>` is
  compared against a verify dest `{{ install_dir | trim }}/config/ags-capture/<X>`
- **THEN** both reduce to the same spine-relative tail `<X>`

### Requirement: The coverage test SHALL be scoped to the capture app

The coverage assertion SHALL be a **subset** check
(`placed_capture ⊆ verified_capture`), not set equality.

Rationale: `verify_gui_tools_app_files` is a mirror of *four* placement manifests
plus the ICME event-seam modules. Equality would drag `ags-icme`,
`ags-hypr-pano`, `ags-wallpaper-selector` and `ags-notifications` into a change
scoped to the capture app and would fail today for reasons that are out of scope.

#### Scenario: A missing non-capture app entry does not fail this test

- **WHEN** a dest under `ags-icme/`, `ags-hypr-pano/`, `ags-wallpaper-selector/`
  or `ags-notifications/` is absent from `verify_gui_tools_app_files`
- **THEN** the capture-app coverage test does not fail — those apps' coverage is a
  separate change

### Requirement: The coverage test SHALL be non-vacuous in both directions

The assertion SHALL hold in both directions for the capture app:

- every placed `ags-capture/` dest is verified (**no gap**), and
- every verified `ags-capture/` dest has a placement (**no phantom**).

A verify entry with no placement is a path verify demands that no task creates —
a guaranteed false failure on a correctly provisioned machine. Both sides SHALL be
checked for duplicates before the set difference, so a repeated dest is caught
rather than collapsed by the set.

#### Scenario: A phantom verify entry fails

- **WHEN** a dest under `ags-capture/` is added to `verify_gui_tools_app_files`
  with no corresponding `gui_tools_app_files` entry
- **THEN** the coverage test fails, naming the phantom path

#### Scenario: A duplicate dest on either side fails

- **WHEN** the same `ags-capture/` dest appears twice in either list
- **THEN** the coverage test fails rather than passing because a set collapsed it

### Requirement: Deployed sources SHALL NOT change

This change SHALL add verification coverage only. `gui_tools_app_files`,
`gui_tools/vars/main.yml` and every file under `src/gui-tools/capture-tool/` SHALL
be byte-identical before and after.

#### Scenario: The deployment manifests are untouched

- **WHEN** the change is reviewed as a diff
- **THEN** no hunk touches `roles/gui_tools/vars/main.yml` or anything under
  `src/gui-tools/capture-tool/`

#### Scenario: The gates stay green

- **WHEN** `scripts/capture-hexagonal-gate.py`, `make capture-test` and the capture
  tool's own `pytest tests/` are run
- **THEN** they report PASS / 85 / 97 respectively, unchanged from the baseline