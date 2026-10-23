# Design: verify-capture-placement-coverage

## Why derivation cannot be done with a regex

The gap was missed once already by a hand-review of the YAML. The obvious cheap
check — grep `verify/vars/main.yml` for `ags-capture/` lines — is wrong in a way
that reliably hides exactly this class of bug, for three independent reasons:

1. **The two files spell the seam differently.** Placement writes
   `{{ gui_tools_spine_config_dir }}/ags-capture/...`; verify writes
   `{{ install_dir | trim }}/config/ags-capture/...`. `gui_tools_spine_config_dir`
   *is* `<install>/config`, but nothing in either file says so on the same line. A
   regex matching `ags-capture/` happens to work; one matching a full dest prefix
   does not.
2. **Placement entries are flow mappings with comments interleaved.** The relevant
   entries are `  - { name: ..., source: ..., dest: "..." }`, with the rationale
   comments *between* entries and inside the flow mapping's own line. A regex
   keyed on `- "…"` (list-of-strings shape, which is how verify spells its list)
   silently matches zero placement entries — which reads as "zero gaps," the exact
   wrong answer.
3. **Comments contain path-like text.** The rationale blocks name source paths
   (`src/gui-tools/capture-tool/domain/cli-args.ts`) and retired spine paths
   (`ui/CaptureWindow.tsx`, from `gui_tools_capture_obsolete`). A line-oriented
   scan picks those up as if they were entries.

So the check parses both files with the loader the roles themselves use:

```python
from ansible.parsing.dataloader import DataLoader
loader = DataLoader()
placed = loader.load_from_file(".../gui_tools/vars/main.yml")["gui_tools_app_files"]
verified = loader.load_from_file(".../verify/vars/main.yml")["verify_gui_tools_app_files"]
```

(`load_from_file`, not `load`: `DataLoader.load` takes a path whose *contents* it
returns as a tagged str when called the obvious way, which silently yields a
string instead of the mapping.)

The gap *analysis* above uses the Ansible loader, because the claim being made is
about what Ansible itself will place, and `DataLoader` is what the roles run
under. The shipped **test** uses this file's existing `_vars()` /
`_sibling_vars()` helpers (`yaml.safe_load`), matching every other role-vars test
in the repo — what matters for the test is that it is a real parser, not that it
happens to be the same one. The two agree on these files.

## Comparison key

Comparing the two lists needs a key that is stable across the seam-vocabulary
difference above. The choice is the **spine-relative tail after `ags-capture/`**:

```
placed:   "{{ gui_tools_spine_config_dir }}/ags-capture/domain/cli-args.ts"  → domain/cli-args.ts
verified: "{{ install_dir | trim }}/config/ags-capture/domain/cli-args.ts"  → domain/cli-args.ts
```

Rejected alternatives:

- **Full dest string.** Never matches — the seam spellings differ (reason 1).
- **Source path → dest reverse map.** Depends on a second manifest, and the
  verify list is dests by design; deriving the reverse map would just be another
  hand-maintained table to drift.
- **Filename only.** Collapses `ports/settings-store.ts` and
  `adapters/glib-settings-store.ts` ambiguously, and a `lib/theme.ts` in three
  apps into one entry. The tail is the finest key that is *actually* comparable.

Both sides are asserted **duplicate-free** before the set difference, so a
repeated dest on either side is caught rather than collapsed by the set.

## Where the assertion lives, and what it does not assert

In `test_verify_role.py`, `TestVerifyVars`, alongside the existing parity locks
(`test_ags_always_on_instances_parity_with_gui_tools`,
`test_settings_files_parity_with_settings_role`). It derives:

```python
placed = {
    tail(str(e["dest"]))
    for e in _sibling_vars("gui_tools")["gui_tools_app_files"]
    if "ags-capture/" in str(e["dest"])
}
verified = {
    tail(str(f)) for f in _vars()["verify_gui_tools_app_files"]
    if "ags-capture/" in str(f))
}
assert placed <= verified, sorted(placed - verified)
```

**Subset, not equality — deliberately.** `verify_gui_tools_app_files` is a mirror
of *four* placement manifests plus the ICME event-seam modules, and this change is
scoped to the capture app. Equality would drag all four apps into this change and
fail today for reasons that are out of scope. `placed <= verified` states exactly
the invariant that matters and has no false positives.

The reverse direction (`verified - placed`) is also asserted **empty for the
capture app**. That is not a style choice: the gate asserts
`stat.results | selectattr('isreg') | length == verify_gui_tools_app_files | length`,
so an entry with no corresponding placement is a path verify demands that the role
has no task creating — a guaranteed future false failure.

### Why a test and not a gate script

`scripts/capture-hexagonal-gate.py` already checks per-file provisioning
registration for the capture tool. The question is whether coverage belongs there
instead. No: the gate is a repo-level architecture gate that reads
`src/gui-tools/capture-tool/` and its placement entries; this is a **cross-role
parity lock between `gui_tools/vars` and `verify/vars`**. The existing cross-role
parity locks in this repo all live in `tests/unit/test_verify_role.py`
(`test_ags_always_on_instances_parity_with_gui_tools` reads the gui_tools role's
var from inside the verify test). Matching the established location is the point —
the next person adding a placement entry will be editing a file that already has
these locks in it.

## Why not generate the list

Generating `verify_gui_tools_app_files` from `gui_tools_app_files` would make the
mirror self-fulfilling: verify would assert precisely what placement already
claims. The failure mode being guarded is a *placement regression* — an entry
present in both lists but never written to disk (a stale `source`, a renamed dir,
a task that stops looping). Auto-generated coverage cannot see that; a
hand-curated list compared *against* the manifest by a test can, because the
curation is what carries the "does this file actually matter at runtime"
judgement. The comments on the entries are the record of that judgement, and they
are worth keeping for the same reason.

## The runtime fixture

`TestVerifyRuntime._build_provisioned_layout` stands in for a provisioned machine;
`test_verify_passes_on_a_provisioned_machine` runs the real tasks against it. Five
new verify entries mean five new files in that fixture, or the "provisioned
machine" stops being one. This is fixture maintenance in the required direction —
it makes the stand-in machine *more* complete, and it strengthens the negative
tests (`test_verify_fails_when_not_provisioned` and friends) which assert verify
fails when things are missing.