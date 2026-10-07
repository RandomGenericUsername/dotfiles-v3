## Why

Placement of the capture app is **per-file**. `gui_tools_app_files` names each
source and its spine dest individually, and the role loops that list — a source
that is not in the list is not deployed, and nothing says so. There is no error,
no warning, no partial-state marker: the file simply never arrives on the machine.

The `verify` role exists to catch exactly that. It stats
`verify_gui_tools_app_files` and asserts the count matches, so any path present
in that list is guaranteed to exist in the spine after provisioning. But the two
lists are maintained **by hand, independently**, and nothing derived one from the
other.

Derived comparison of the two lists (real Ansible YAML loader,
`ansible.parsing.dataloader.DataLoader`, not a regex over the file):

```
gui_tools_app_files entries under ags-capture/:            24
verify_gui_tools_app_files entries under ags-capture/:     19
MISSING from verify (5):
  domain/capture-request.ts
  domain/cli-args.ts
  ui/shared/groups.ts
  ui/shared/icons.ts
  ui/shared/rows.ts
verify entries with no placement (0):
covered: 19/24
```

Five placed capture files are unasserted. A placement regression on any of them
passes verify green.

The worst of the five is **`domain/cli-args.ts`**. It is the tool's single
request→argv translator — the one module in the whole tool that writes an argv
literal for `capture-tool screenshot|start`, and the one place the two vocabulary
traps the backend's argparse rejects live (`--size 75`, not `75%`; `--audio mic`,
not `microphone`). It is loaded through the AGS bundle, so a spine that lacks it
means every capture dies at bundle time. `ui/shared/*` are the shared row /
group / icon builders both layouts import; `domain/capture-request.ts` is the
value-object pair they take. None of the five is optional at runtime.

This gap was already missed once by hand-reviewing the YAML — which is the
argument for deriving the coverage mechanically instead of by eye.

## What Changes

- **Five paths added to `verify_gui_tools_app_files`**, each with a comment naming
  the bundling consequence of its absence, matching the rationale density of the
  existing capture entries.
- **A derived-coverage test** in `src/provisioning/tests/unit/test_verify_role.py`
  that computes the expected `ags-capture/` dest set *from*
  `gui_tools_app_files` and asserts full coverage. The next placement entry added
  without a matching verify entry fails loudly, naming the path — instead of
  silently joining this list.
- **The `test_verify_passes_on_a_provisioned_machine` fixture** grows the five
  files, since the fixture is a stand-in for a provisioned machine and verify now
  checks five more paths.

`gui_tools_app_files` and every deployed source are **untouched**. This is
verification coverage only.

## Non-goals

- **Not auditing the non-capture apps** (`ags-icme`, `ags-hypr-pano`,
  `ags-wallpaper-selector`, `ags-notifications`). Those lists have their own gaps
  of the same shape — `verify_gui_tools_app_files` is a partial mirror of four
  placement manifests, not just one. Scope here is the capture app, which is the
  one whose missing file kills the feature outright.
- **Not restructuring the deployment** to directory sources, which would make the
  question moot. The per-file discipline is deliberate and load-bearing
  (`gui_tools/vars/main.yml:1–16`): a `copy` with a directory source and a
  pre-existing dest dir is a silent no-op, review finding 2026-08-12.
- **Not touching `src/gui-tools/capture-tool/`.** Not one line.
- **Not auto-generating `verify_gui_tools_app_files` from the placement manifest.**
  Generation would make the mirror tautological — verify would assert only what
  placement already claims, and a placement *regression* (an entry present in both,
  but never actually written) would still pass. Derivation belongs in the test,
  where a human-curated list is compared against the manifest.

## Impact

- `src/provisioning/ansible/roles/verify/vars/main.yml` — 5 new entries in
  `verify_gui_tools_app_files`, 19 → 24 for `ags-capture/`.
- `src/provisioning/tests/unit/test_verify_role.py` — one new derived-coverage
  test; the runtime fixture gains 5 files.
- **Runtime**: none. `verify` now stats 5 more files per run; both roles'
  behaviour on a correctly provisioned machine is unchanged.
- **No deployed source changes.**