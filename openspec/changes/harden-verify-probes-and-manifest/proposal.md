# Proposal — harden-verify-probes-and-manifest

## Why

Two defects recorded as known gaps by `repair-package-manifest-drift` and
`98403c74`, both in the verify role's check-gate discipline and the package
manifest's reachability.

**Defect 1 — ungated `shell` probes.** `roles/verify/tasks/main.yml` had four
`ansible.builtin.shell` host-state probes with no `when: not ansible_check_mode`,
while every `ansible.builtin.command` sibling carried it. The brief named two
(`Check AstalNotifd binding package is installed` and `Check AstalWp binding
package is installed`); there are **four** — `Check system binaries on PATH` and
`Check CLI tools on PATH` were ungated too. The check-gate invariant
(`test_settings_parse_gate_tasks_exist_and_are_check_gated`) only iterated
`ansible.builtin.command`, so it was structurally blind to all four.

**Defect 2 — three manifest entries no role installs.** `packages.yaml` declared
`hyprcursor`, `lf` and `xdg-utils`; none was a `group_vars` key, a
`group_vars` value, or in `aur_packages`. Two were host-installed by hand, which
is exactly how the drift arose. `repair-package-manifest-drift` pinned them as
`_DECLARED_NOT_PROVISIONED` and stopped there.

## What changes

1. **Declare the check gate on all four ungated `shell` probes.** All four
   consumers (the matching asserts) are *already* gated
   `when: not ansible_check_mode`, so no consumer edit is needed — see
   `design.md` §1.3, which is the subtle part and the reason the fix is safe
   rather than a `--check` regression.

2. **Widen the invariant to cover `shell`.** The old command-only loop is what
   made the defect invisible; `harden-verify-probes-and-manifest` replaces it
   with a role-wide probe invariant over both modules, plus negative tests that
   prove it fires on a `shell` task and rejects near-miss gate values.

3. **Resolve all three manifest orphans, per package, on evidence.**

   | package | resolution | one-line reason |
   |---|---|---|
   | `xdg-utils` | **add** to both `group_vars` maps | gui_tools runs `xdg-mime default`, verify gates `xdg-mime query default`, capture-tool and hypr-pano shell `xdg-open` — hard consumers |
   | `hyprcursor` | **remove** from `packages.yaml` | no consumer anywhere, and it is already a direct pacman dependency of `hyprland`, so it arrives transitively |
   | `lf` | **remove** from `packages.yaml` | no consumer anywhere: no keybind, autostart entry, desktop file, config, spec, or plan-doc requirement; not host-installed either |

   The per-package evidence table is in `design.md` §2. No package was added that
   nothing calls, and none was removed that something calls.

4. **Re-snapshot the drift locks** that pin those key sets, with a provenance
   comment per added key (and per removed one).

## Impact

- `uv run --directory src/provisioning pytest tests/unit -q`: 711 passed →
  **720 passed**, 0 failed. The +9 are the new probe-gate invariant and its
  negative cases.
- Real-run behaviour of the verify role is unchanged; only the `--check` skip
  path moved. `design.md` §1.4 has the before/after recap.
- `packages.yaml` shrinks by two entries (`lf`, `hyprcursor`); `group_vars`
  grows by one key in each map (`xdg-utils`). Both drift locks re-snapshotted.

## Out of scope

- `src/gui-tools/capture-tool/**` — untouched.
- The verify role's other tasks — untouched.
- `docs/99-dotfiles-hexagonal-architecture.md` still lists `lf` and `hyprcursor`
  in a *historical* "Changes Applied" table (line 1288) describing the `e00a6773`
  Lua migration. That table is a record of what a past commit did, not a live
  requirement — the same table still lists `cliphist`, which `a1de8bfa` removed
  from the manifest when hypr-pano superseded it. Left alone; rewriting history
  in a changelog table would be the wrong fix.