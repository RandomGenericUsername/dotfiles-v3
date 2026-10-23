# Tasks — harden-verify-probes-and-manifest

## 1. Defect 1 — the ungated `shell` probes

- [x] 1.1 Enumerate every `command`/`shell` task in `roles/verify/tasks/main.yml`
      by module key and record which are ungated.
      **Found FOUR, not two** — `Check system binaries on PATH`,
      `Check CLI tools on PATH`, `Check AstalNotifd binding package is
      installed`, `Check AstalWp binding package is installed`. All 26 `command`
      tasks were gated, so the blind spot was the whole `shell` module.
- [x] 1.2 Re-verify the `98403c74` reasoning rather than inheriting it: build a
      probe playbook whose `shell` task appends to a marker file, run it with
      `--check`. Confirmed nothing runs (marker absent), and the ungated
      register carries a **fabricated `rc: 0`** plus
      `"Command would have run if not in check mode"`.
- [x] 1.3 **Check every consumer of the four registers for an unguarded `.rc` /
      `.results` dereference** — the part that breaks `--check` if missed.
      `grep -rn` for `verify_notifd_binding_checks` and
      `verify_astal_wp_binding_checks` returns only the producing task and its
      assert; all four consumers are asserts already gated
      `when: not ansible_check_mode`. **No consumer edit needed** — unlike
      `98403c74`, whose consumer was an ungated `debug`. Recorded why in the
      `main.yml` comment.
- [x] 1.4 Reproduce the failure mode anyway, to show the guard is load-bearing:
      a probe playbook whose consumer dereferences the gated register unguarded
      fails with `object of type 'dict' has no attribute 'results'` and
      `failed=1`; behind `not ansible_check_mode and …` it skips with
      `failed=0`.
- [x] 1.5 Add `when: not ansible_check_mode` to all four probes, each with a
      comment citing `98403c74`'s reasoning and naming the already-gated
      consumer that makes it safe.
- [x] 1.6 Drive a slice playbook carrying the four probes and their four real
      consumers: `--check` → `skipped=8 failed=0`; real mode →
      `ok=8 failed=0 skipped=0`.

## 2. Defect 2 — the three manifest orphans

- [x] 2.1 Establish whether each package is **called** anywhere:
      `grep -rn` across `dotfiles/config/hypr/*` (23 `exec_cmd` bindings in
      `keybindings.lua`, `autostart.lua`, `cursor.lua`, `env-variables.lua`),
      the rofi launcher, shell rc, desktop files, and `src/gui-tools/**`.
- [x] 2.2 Establish **host installation** with `pacman -Qi` (a hand install is
      not provisioning).
- [x] 2.3 Establish whether a **spec or the project plan** calls for it:
      searched every `openspec/changes/*/specs/` and
      `docs/Hyprland Screenshot & Screen Recording Tool — Full Project Plan.md`.
- [x] 2.4 Establish whether a **config silently breaks** without the binary.
- [x] 2.5 `xdg-utils` → **(a) needed**. Four call sites, three inside this
      repo's provisioning (`gui_tools` `xdg-mime default`, verify `xdg-mime query
      default`, capture-tool + hypr-pano `xdg-open`);
      `pacman -Qo` confirms both binaries are owned by `xdg-utils`. Add to
      **both** `group_vars` maps with a provenance comment. Debian name verified
      against the Debian archive madison/sources APIs: `xdg-utils` 1.2.1-2 in
      `stable`/`testing`, architecture `all`. Not AUR-only → `aur_packages`
      untouched.
- [x] 2.6 `hyprcursor` → **(b) remove**. No consumer anywhere; no `.hlc` theme;
      `XCURSOR_THEME=Adwaita` is a plain Xcursor name. Decisive:
      `pacman -Qi hyprland` lists `hyprcursor` as a **direct dependency**, and
      `hyprland` is already declared in both maps — so it arrives transitively.
      Removed from `packages.yaml` with a comment recording that.
- [x] 2.7 `lf` → **(b) remove**. Not host-installed; no keybind, autostart,
      desktop file, config, spec, or plan-doc mention. Both it and `hyprcursor`
      came from the `e00a6773` bulk "must-have packages" block alongside
      `cliphist`, which `a1de8bfa` later retired the same way.
- [x] 2.8 No package needed resolution (c): all three were decidable from the
      repo's own call sites plus `pacman -Qi` and the Debian API.
- [x] 2.9 Re-snapshot the three drift locks with a provenance comment per
      changed key: `_LOGICAL_PACKAGE_KEYS` (`+ xdg-utils`),
      `_DECLARED_NOT_PROVISIONED` (now empty, kept as a pin),
      `test_packages_manifest_has_verified_set` (`- lf`, `- hyprcursor`).
      All three remain exact-set equality; none weakened.

## 3. The widened invariant

- [x] 3.1 Add `_PROBE_MODULES = ("ansible.builtin.command",
      "ansible.builtin.shell")`, `_probe_tasks()`, and
      `_ungated_probe_problems(tasks)` to `test_verify_role.py`. The helper is
      extracted so negative cases can feed it synthetic tasks.
- [x] 3.2 Widen `test_settings_parse_gate_tasks_exist_and_are_check_gated` from
      `_command_tasks()` to `_probe_tasks()`.
- [x] 3.3 Add role-wide `test_every_probe_task_is_check_gated` with a failure
      message naming the `rc`/`results` consequence.
- [x] 3.4 Negative-test the widened invariant:
      - [x] fires on an ungated `shell` task (the historical command-only form
            returned `[]` for exactly that task)
      - [x] rejects 4 near-miss gate values: none, reversed, compound, bare
            `<reg>.rc != 0`
      - [x] accepts the correct gate on both modules (not a tautology)
      - [x] ignores `stat` / `assert` / `copy` (scoped, matching the role header)
      - [x] asserts the role's probes really span both modules
- [x] 3.5 Update `test_system_binary_and_cli_tool_checks_use_shell_command_v`,
      which asserted `when is None` and therefore **pinned the defect**. Now
      requires `when == "not ansible_check_mode"` — a strengthening.
- [x] 3.6 Prove the widened invariant fires on the REAL file: remove the gate
      from `Check AstalWp binding package is installed`, run the suite, confirm
      red, restore (`diff` against a pre-injection copy → identical).

## 4. openspec change

- [x] 4.1 `proposal.md`
- [x] 4.2 `design.md` — mechanism evidence (§1.2/§1.4), the per-package
      evidence table (§2), the widened-invariant rationale (§3)
- [x] 4.3 `specs/harden-verify-probes-and-manifest/spec.md` —
      `## ADDED Requirements` / `### Requirement:` / `#### Scenario:`
- [x] 4.4 `tasks.md` (this file)

## 5. Verification

- [x] 5.1 `uv run --directory src/provisioning pytest tests/unit -q` →
      **0 failed**, 720 passed (baseline 711 passed; +9 are the new invariant
      and its negative cases).
- [x] 5.2 `python3 scripts/capture-hexagonal-gate.py` → PASS, check 6 at
      33 used / 28 styled.
- [x] 5.3 `make capture-typecheck` → 0 errors. `make capture-test` → 115.
- [x] 5.4 capture `pytest tests/` → 97.
- [x] 5.5 `src/gui-tools/capture-tool/**` untouched; `roles/verify/**` touched
      only in `tasks/main.yml`'s four probes and their comments.

## 6. Not done, recorded

- `docs/99-dotfiles-hexagonal-architecture.md:1288` still lists `lf` and
  `hyprcursor` in a historical "Changes Applied" table for `e00a6773`. That table
  also still lists `cliphist`, removed from the manifest by `a1de8bfa`, so it is
  a changelog rather than a live requirement. Left alone deliberately.
- No consumer was invented for `lf` (e.g. a new keybind). Resolving whether the
  system needs a package and deciding to adopt one are different changes.