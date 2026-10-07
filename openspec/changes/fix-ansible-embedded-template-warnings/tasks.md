## 1. Reproduce, and pin the trigger

- [ ] 1.1 Reproduce the warning from a clean run:
      ```bash
      cd src/provisioning
      PATH="$PWD/.venv/bin:$PATH" .venv/bin/dotfiles-provision verify
      ```
      Expect: exit 0, and on stderr the embedded-template warning with
      `Origin: .../roles/verify/tasks/main.yml:1289:11`.
- [ ] 1.2 Confirm the trigger shape with the four-case probe (design §1):
      case A (nested in a `search` argument) warns; case B (`~` concatenation),
      case C (top-level template in a `fail_msg`) and case D (plain `lookup`
      argument) do not. **Re-run it; do not take design §1 on trust.**
- [ ] 1.3 Confirm the warning is deduped by message, so counting warning lines
      undercounts sites. Establish the count by reading the tree, not the output.

## 2. Establish the true count of sites

- [ ] 2.1 Sweep for the shape across the whole Ansible tree, not just `verify`:
      ```bash
      grep -rnE "is (search|match|regex)" src/provisioning/ansible --include='*.yml'
      ```
- [ ] 2.2 For each hit, decide whether the `{{ }}` is inside a **Jinja string
      literal** (a trigger) or is **top-level templating** (correct). Expected:
      `:283` and `:1162` are already `~`-concatenated and correct; `:1276-1277`
      and `:1290-1291` nest.
- [ ] 2.3 Check the other shape the warning's help text names — an embedded
      template plus a comparison in a conditional
      (`when: "{{ a_var }}" == 42`):
      ```bash
      grep -rnE "^\s*(when|that|changed_when|failed_when|until):.*\{\{.*(==|!=|>|<|is )" src/provisioning/ansible --include='*.yml'
      ```
      Expected: none. Record the result either way.
- [ ] 2.4 Record the final count and every site in `design.md`. If it is not
      two, the change is bigger than proposed and that is a finding, not a
      reason to re-scope silently.

## 3. Fix the two sites

- [ ] 3.1 `:1276-1277` — `color_theme` regex: split the Jinja literal around the
      variable and join with `~`. **Preserve the `["'']` quote class exactly**;
      in a Jinja single-quoted literal `''` is an escaped quote, so the value is
      the regex class `["']`.
- [ ] 3.2 `:1290-1291` — `save_config_on_exit` regex: same treatment.
- [ ] 3.3 Re-run `verify` and confirm the warning is **gone from stderr**, the
      run still exits 0, and both btop assertions still pass (`ok`, not
      `changed`/`skipped`).
- [ ] 3.4 Negative proof that the assertions still bite: temporarily set the
      rendered `save_config_on_exit` to the wrong value and confirm the assertion
      **fails**. A regex that stops matching is the exact failure this change
      risks introducing, so it is tested rather than assumed.

## 4. The static lint gate

- [ ] 4.1 Write `scripts/ansible-embedded-template-lint.py` (stdlib + PyYAML):
      load every `.yml`/`.yaml` under `src/provisioning/ansible/`, walk to the
      expression-context keys (`assert.that` including list items, `when`,
      `changed_when`, `failed_when`, `until`), and flag any quoted region
      containing `{{`. Name file, line and the offending literal.
- [ ] 4.2 Parsing, not grepping: the two real sites are folded block scalars
      spanning two lines, so a line-oriented scan cannot see them. Assert this
      by confirming the lint catches `:1276-1277` **before** the fix.
- [ ] 4.3 Confirm the lint does **not** flag the known-correct top-level
      templates: `packages.yaml:26-27`, `verify:607-608`, `cli_tools:177`,
      `assets/tasks/main.yml:75`, `packages/tasks/main.yml:156`. These are the
      false positives a naive grep produces, and flagging them would make the
      gate noise.
- [ ] 4.4 Run it before the fix (red) and after (green) — the same both-
      directions proof the other gates in this repo carry.
- [ ] 4.5 Add a `make` target, and wire it into `gates-ci` (it needs no desktop
      stack — PyYAML via the provisioning env, like `icons-json-drift`).
- [ ] 4.6 Plant a nested template in a scratch file and confirm the gate exits
      non-zero naming it; remove it.

## 5. Record what is *not* being fixed

- [ ] 5.1 Confirm `INJECT_FACTS_AS_VARS` still appears and is still tolerated —
      this change must not be read as "warnings are now clean".
- [ ] 5.2 Confirm the dry-run integration test is untouched, and add a comment
      there recording **why** it cannot catch this class (the offending tasks are
      `when: not ansible_check_mode`). The next reader will reach for that test
      first.

## 6. Verification

- [ ] 6.1 `make gates` exit 0, including the new lint.
- [ ] 6.2 `make gates-ci` exit 0.
- [ ] 6.3 The provisioning test suite unchanged and green.
- [ ] 6.4 One full `dotfiles-provision verify` on the live machine: exit 0,
      `failed=0`, and **no embedded-template warning**. This is the acceptance
      criterion — everything else is support.
