# Design — harden-verify-probes-and-manifest

## 1. Defect 1: the ungated `shell` probes

### 1.0 There are four, not two

The brief named the two `pacman -Q` probes (AstalNotifd, AstalWp). Enumerating
every `command`/`shell` task in the role by module key found **four** ungated
probes:

| line (pre-fix) | task | module | register |
|---|---|---|---|
| 150 | `Check system binaries on PATH` | `ansible.builtin.shell` (`command -v {{ item }}`) | `verify_system_binary_checks` |
| 362 | `Check CLI tools on PATH` | `ansible.builtin.shell` (`command -v {{ item }}`) | `verify_cli_tool_checks` |
| 388 | `Check AstalNotifd binding package is installed` | `ansible.builtin.shell` (`pacman -Q {{ item }}`) | `verify_notifd_binding_checks` |
| 412 | `Check AstalWp binding package is installed` | `ansible.builtin.shell` (`pacman -Q {{ item }}`) | `verify_astal_wp_binding_checks` |

All 26 `command` tasks were gated. So the blind spot was not "two stragglers" —
it was **the entire `shell` module**, four of four tasks ungated, invisible to a
command-only invariant. Fixing only the two named would have left the invariant
red and the defect half-alive.

### 1.1 Why the gate is still worth declaring (citing `98403c74`, not reinventing)

`98403c74` established the reasoning for the Hyprland `command` probe and it
applies verbatim here. Re-verified, not assumed:

- ansible-core 2.21 **already short-circuits** both `command` and `shell` under
  `--check`. So nothing actually ran before this change — a probe playbook that
  shelled out to append a marker file left the marker uncreated.
- The gate is still a **declared invariant**, not something to inherit:
  `shell` is documented `check_mode: support: PARTIAL` exactly like `command`. An
  upgrade that began executing check-mode shell tasks would spawn a real
  `pacman -Q` during every dry run with **no test failing** — these tests assert
  YAML text, not runtime.
- The short-circuit **fabricates `rc: 0`** — a probe that never ran reports
  success.

### 1.2 Mechanism, reproduced before and after

A standalone probe playbook (`ANSIBLE_CONFIG` pointed at
`src/provisioning/ansible/ansible.cfg`, the project's own inventory for
`ansible_connection: local`).

**Before (ungated, as shipped):**

```
TASK [A ungated shell probe] ***************************************************
skipping: [localhost]

TASK [A dump ungated register] *************************************************
ok: [localhost] => {
    "probe_ungated": {
        "changed": false,
        "msg": "Command would have run if not in check mode",
        "rc": 0,                      <-- FABRICATED success
        "skipped": true,
        ...
    }
}

$ cat marker
cat: marker: No such file or directory   <-- nothing actually ran
```

**After (gated):**

```
TASK [B gated shell probe] *****************************************************
skipping: [localhost]

TASK [B dump gated register] ***************************************************
ok: [localhost] => {
    "probe_gated": {
        "changed": false,
        "false_condition": "not ansible_check_mode",
        "skip_reason": "Conditional result was False",
        "skipped": true
    }                                        <-- NO rc key, NO results key
}
```

### 1.3 The subtle part: consumers

`98403c74`'s real finding was that gating a probe is **not** a one-line change:
a conditionally-skipped register carries no `rc`, so its consumer had to become
`not ansible_check_mode and <reg>.rc != 0` or `--check` broke.

I checked every consumer of the four registers. **All four consumers were
already gated `when: not ansible_check_mode`**:

| register | consumer | consumer `when` (pre-fix) |
|---|---|---|
| `verify_system_binary_checks` | `Assert system binaries are on PATH` | `not ansible_check_mode` |
| `verify_cli_tool_checks` | `Assert CLI tools are on PATH` | `not ansible_check_mode` |
| `verify_notifd_binding_checks` | `Assert AstalNotifd binding is installed` | `not ansible_check_mode` |
| `verify_astal_wp_binding_checks` | `Assert AstalWp binding is installed` | `not ansible_check_mode` |

`grep -rn` across the whole repo for the two Astal register names returns only
the producing task and its assert — no other consumer, no `debug`, no summary.

So **no consumer edit is required here**, and that is the difference from
`98403c74`: its consumer was a `debug` whose `when` read the register, so
skipping the producer forced a change. These are asserts already gated, which is
pinned by the pre-existing `test_shell_check_asserts_are_check_gated` and
`test_every_state_assert_is_check_gated`.

The failure mode is still real and still worth demonstrating — if a consumer had
been ungated, this is what `--check` would do:

```
TASK [gated shell probe] *******************************************************
skipping: [localhost]

TASK [consumer -- rc dereferenced unguarded] ***********************************
fatal: [localhost]: FAILED! => {"msg": "Task failed: A 'when' expression failed:
  Error while evaluating conditional: object of type 'dict' has no attribute
  'results'"}

PLAY RECAP *********************************************************************
localhost : ok=0 changed=0 unreachable=0 failed=1 skipped=1 ...
```

and with the short-circuit guard the same slice is clean:

```
when: not ansible_check_mode and probe_gated.results[0].rc != 0
-> skipping: [localhost]
localhost : ok=0 changed=0 unreachable=0 failed=0 skipped=2
```

### 1.4 The four real probes, before and after

A slice playbook carrying the four probes and their real consumers verbatim:

| | `--check` | real mode |
|---|---|---|
| **after (gated)** | `ok=0 changed=0 unreachable=0 failed=0 skipped=8` | `ok=8 changed=0 unreachable=0 failed=0 skipped=0` |

All four asserts run and pass for real; nothing dereferences a missing key under
`--check`. The change moves only the skip path — real-mode behaviour is
unchanged.

### 1.5 A test was pinning the defect

`test_system_binary_and_cli_tool_checks_use_shell_command_v` asserted
`task.get("when") is None` with the rationale *"shell checks are skipped under
`--check` by ansible-core; the assert is the gated half"*. That test **required
the ungated state**, which is why two of the four probes survived the earlier
gate sweep. It now requires `when == "not ansible_check_mode"`.

This is a strengthening, not a relaxation: it moves from "no gate at all" to
"the exact gate", and it is strictly narrower than the new invariant in
§3.1 — which is what caught it (that test was red immediately after the
`main.yml` edit, before the test file was touched).

## 2. Defect 2: the per-package evidence table

Method: `grep -rn` for each binary across `dotfiles/config/hypr/*` (keybindings,
autostart, cursor, env-variables), all `exec_cmd` bindings, the rofi launcher,
shell rc, desktop files, and `src/gui-tools/**`; `pacman -Qi` for host
installation; `git log -S` per entry for provenance; a search of every
`openspec/changes/*/specs/` and of the project plan doc.

| package | called anywhere? | host-installed? | a spec/plan wants it? | config breaks without it? | resolution |
|---|---|---|---|---|---|
| **`xdg-utils`** | **YES — 4 hard call sites** | yes (`pacman -Qi xdg-utils` → 1.2.1-2) | yes — `add-ags-notifd-notifications/spec.md` and the verify/gui_tools gates | **YES** | **(a) add** |
| **`hyprcursor`** | no | yes (0.1.13-7) — but **transitively via hyprland** | no | no | **(b) remove** |
| **`lf`** | no | **no** (`pacman -Qi lf` → not found) | no | no | **(b) remove** |

### 2.1 `xdg-utils` → (a) genuinely needed. Evidence:

Four call sites, three of them inside this repo's own provisioning:

```
src/provisioning/ansible/roles/gui_tools/tasks/main.yml:214
  cmd: "xdg-mime default thunar.desktop inode/directory"
src/provisioning/ansible/roles/verify/tasks/main.yml:596
  cmd: "xdg-mime query default inode/directory"        (gated assert at :604)
src/gui-tools/capture-tool/bin/capture-tool:957,962
  subprocess.run(["xdg-open", str(path)], check=False)   # "Show in folder"
src/gui-tools/hypr-pano/lib/history.ts:112
  Gio.Subprocess.new(["xdg-open", target], ...)         # URL opener
```

Binary ownership confirmed on the host: `pacman -Qo /usr/bin/xdg-mime
/usr/bin/xdg-open` → both owned by `xdg-utils 1.2.1-2`.

Why it matters concretely: the `gui_tools` task pins `inode/directory` to
`thunar.desktop` *because* the mime database's own resolution order picked
`kitty-open.desktop`, so the capture tool's "Show in folder" opened a terminal
instead of a file manager. Undeclared, that `xdg-mime default` invocation has no
binary at all, the pin never happens, `verify`'s gate fails, and the original
symptom returns on a fresh machine. This is a real defect, not bookkeeping.

**Debian name verified** (the brief asked, and `repair-package-manifest-drift`
deferred this change partly for lack of a Debian host — an API is enough):

```
$ curl -s "https://api.ftp-master.debian.org/madison?package=xdg-utils&f=json"
[{"xdg-utils":{"oldoldstable":{"1.1.3-4.1":{...}},"oldstable":{"1.1.3-4.1":{...}},
  "stable":{"1.2.1-2":{"component":"main","architectures":["source","all"],
  "source":"xdg-utils",...}},
  "testing":{"1.2.1-2":{...}},"unstable":{"1.2.1-2":{...}}}}]

$ curl -s "https://sources.debian.org/api/search/xdg-utils/"
{"query":"xdg-utils","results":{"exact":{"name":"xdg-utils"},...}}
```

`xdg-utils` is a real Debian binary package in `stable` and `testing`
(1.2.1-2, architecture `all`) — the same name as Arch, so both maps take
`xdg-utils: xdg-utils`. Not AUR-only, so `aur_packages` is untouched.

### 2.2 `hyprcursor` → (b) not needed; it is already transitive. Evidence:

Not called. `grep -rn hyprcursor` over the whole repo returns only
`packages.yaml`, two docs, the test locks, and this change's own files. No
`exec_cmd`, no keybind, no autostart entry, no desktop file. Nothing breaks
without it.

There is one `cursor` config file — `dotfiles/config/hypr/cursor.lua` — and it
sets `no_hardware_cursors = false` only; that is a Hyprland compositor setting
with no `hyprcursor` involvement. `env-variables.lua` sets
`XCURSOR_THEME=Adwaita`, a plain **Xcursor** name (the legacy `libxcursor`
mechanism `hyprland` depends on directly), not a hyprcursor `.hlc` theme. There
is no `.hlc` file anywhere in the repo and no spec or plan doc mentions a cursor
theme.

Decisively, it does not need declaring:

```
$ pacman -Qi hyprland | grep "Depends On"
Depends On : cairo aquamarine ... hyprcursor libhyprcursor.so=0-64 hyprgraphics
             libhyprgraphics.so=4-64 hyprland-guiutils hyprlang ... libxcursor ...
```

`hyprcursor` is a **direct dependency of `hyprland`**, and `hyprland` is already
declared in both `group_vars` maps. So a fresh machine gets it transitively.
Declaring it separately would duplicate a dependency pacman already resolves and
would imply a consumer that does not exist — the exact failure mode this change
exists to remove. The manifest entry carried the comment "Cursor themes", which
describes an intent no config in this repo realises.

### 2.3 `lf` → (b) not needed. Evidence:

Not called anywhere. `grep -rnE "(^|[^A-Za-z0-9_./-])lf([^A-Za-z0-9_.-]|$)"`
across the whole repo (excluding `node_modules`/`.git`) returns only: a Python
local variable in two `.agents/skills/**` scripts, and two docs. Specifically
negative for every place that would make it a consumer:

- `keybindings.lua` — 23 `exec_cmd` bindings enumerated; `SUPER+E` is `thunar`,
  no terminal file manager. No `lf`.
- `autostart.lua` — no `lf`.
- rofi launcher (`dotfiles/config/rofi/launcher/config.rasi`) — no `lf`.
- desktop files — the repo has exactly one (`tidal-hifi.desktop`), no `lf`.
- shell rc / `zsh_config` — no `lf`. No `~/.config/lf` directory is deployed.
- specs and the project plan doc — no mention. `docs/Hyprland Screenshot &
  Screen Recording Tool — Full Project Plan.md` never mentions `lf`.

It is not even host-installed (`pacman -Qi lf` → "package 'lf' was not found"),
so unlike the other two there is not even a hand-install masking the gap.

Provenance: both `lf` and `hyprcursor` entered `packages.yaml` in the same
commit, `e00a6773` ("feat(hyprland): migrate from hyprlang to Lua format"), in a
bulk "must-have packages" block with no consumer added alongside. The same block
listed `cliphist`, which `a1de8bfa` later removed from the manifest when
hypr-pano superseded it. That is the precedent: entries in that bulk block are
intentions, not wiring, and are retired when nothing consumes them.

### 2.4 Not (c)

No package needed to be left undecidable. `xdg-utils` was decidable from the
repo's own call sites plus the Debian API; `hyprcursor` and `lf` were decidable
from an exhaustive negative grep plus `pacman -Qi`. The Debian-name concern that
blocked `repair-package-manifest-drift` is answered for `xdg-utils` in §2.1, and
did not arise for the other two because they are removals.

## 3. The widened invariant

### 3.1 What replaced what

`test_settings_parse_gate_tasks_exist_and_are_check_gated` looped
`_command_tasks()`. It now loops `_probe_tasks()`, defined over
`_PROBE_MODULES = ("ansible.builtin.command", "ansible.builtin.shell")`, and a
new role-wide `test_every_probe_task_is_check_gated` asserts the same rule with
a failure message that names the consequence.

The parsing lives in `_ungated_probe_problems(tasks)` rather than inline, so the
negative cases can feed it synthetic tasks — otherwise the invariant could only
be exercised against the real file, where it is green by construction.

`_PROBE_MODULES` is a tuple, so widening it again is a one-line edit, and
`test_probe_gate_invariant_covers_the_real_role_both_modules` fails if the role
ever stops using one of them (which would silently make the other half of the
invariant dead).

### 3.2 The invariant is scoped, not bludgeoning

`test_probe_gate_invariant_ignores_non_probe_modules` asserts `stat`,
`assert`, and `copy` tasks are **not** reported. This is deliberate and matches
the role's own header: `stat` runs honestly under `--check` with no mutation
(so those tasks are legitimately ungated), and the CONFIG seam asserts must fail
under `--check` too. A naive "every task must be gated" rule would have been
both wrong and unsatisfiable.

### 3.3 Negative tests

| test | what it proves |
|---|---|
| `test_probe_gate_invariant_bites_on_an_ungated_shell_task` | **the widened invariant fires on a `shell` task** — the historical command-only form returned `[]` for exactly that task |
| `test_probe_gate_invariant_rejects_wrong_gate_values` | 4 near-misses rejected: no gate, reversed gate, compound expression, bare `<reg>.rc != 0` |
| `test_probe_gate_invariant_accepts_the_correct_gate` | not a tautology — correctly gated `command` + `shell` is clean |
| `test_probe_gate_invariant_ignores_non_probe_modules` | scoped: `stat`/`assert`/`copy` not flagged |
| `test_probe_gate_invariant_covers_the_real_role_both_modules` | the role really uses both modules, so the invariant has teeth |

The near-miss cases are the substantive ones. `verify_probe.rc != 0` is
precisely the shape that broke `--check` in `98403c74`; requiring the *exact*
string means a well-meaning edit to a compound condition is caught rather than
silently reintroducing the dereference.

### 3.4 Proven to bite on the real file

Gate removed from the real `Check AstalWp binding package is installed` probe,
suite run, file restored (`diff` against a pre-injection copy → identical):

```
E  AssertionError: probe 'Check AstalWp binding package is installed'
   (ansible.builtin.shell) must be check-gated
E  assert None == 'not ansible_check_mode'
FAILED tests/unit/test_verify_role.py::TestVerifyTasks::
       test_settings_parse_gate_tasks_exist_and_are_check_gated
1 failed, 9 passed
```

Both the widened parse-gate loop and the new role-wide invariant fire on a real
`shell` defect.

## 4. Re-snapshotted drift locks

The locks pin exact key sets, so both data edits require re-snapshotting. Added
keys carry a provenance comment in the existing style:

- `test_ansible_scaffold.py::_LOGICAL_PACKAGE_KEYS` — `+ xdg-utils`, commented
  with its four consumers and the fact it was a manifest orphan until now.
- `test_ansible_scaffold.py::_DECLARED_NOT_PROVISIONED` — now an **empty**
  `frozenset()`, with the per-package resolution recorded above it. Kept rather
  than deleted: the assertion still fails on any *new* orphan and names both
  directions, so deleting it would remove the pin that makes the next drift
  visible.
- `adapters/test_yaml_manifest_reader.py::test_packages_manifest_has_verified_set`
  — `- lf`, `- hyprcursor`, with a comment recording why each went and why
  `xdg-utils` stayed.

No assertion was relaxed; all three remain exact-set equality.

## 5. Alternatives rejected

- **Gate only the two named probes.** Leaves the invariant red (two more ungated
  `shell` tasks) and the defect class alive. §1.0.
- **Change the four consumers to `not ansible_check_mode and …`** as
  `98403c74` did. Unnecessary — they are already gated, and adding the prefix to
  an already-gated `when` is noise that obscures the real invariant.
- **Add `hyprcursor` to `group_vars` anyway.** It is a transitive dependency of
  an already-declared package and nothing calls it; this is precisely "add a
  package nothing calls".
- **Add `lf` to `group_vars`** to preserve the manifest's stated intent. Same
  objection, stronger: `lf` is not even installed on the host, so nothing
  indicates a real want — only an abandoned entry from a bulk migration commit.
- **Delete `_DECLARED_NOT_PROVISIONED` now that it is empty.** Removes the pin
  that surfaces the next orphan. Kept, commented.
- **Rewrite `docs/99-…-architecture.md:1288`** to drop `lf`/`hyprcursor`. That
  table is a historical "Changes Applied" log for `e00a6773` and still lists
  `cliphist`, removed from the manifest by `a1de8bfa`. Rewriting a changelog is
  not a fix; the live declaration is `packages.yaml`.
- **Add an `lf` keybind so the entry becomes true.** Out of scope — inventing a
  consumer for an orphan is not the same as resolving whether the system needs
  the package.

## 6. Verification

- `uv run --directory src/provisioning pytest tests/unit -q` → **0 failed**,
  720 passed (baseline 711 passed).
- `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at 33 used / 28 styled.
- `make capture-typecheck` → 0 errors. `make capture-test` → 115.
- capture `pytest tests/` → 97.
- `src/gui-tools/capture-tool/**` untouched; `roles/verify/**` touched only in
  `tasks/main.yml`'s four probes plus their comments.