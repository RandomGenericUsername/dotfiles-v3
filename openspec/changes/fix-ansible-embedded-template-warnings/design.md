# Design: fix-ansible-embedded-template-warnings

## §1 The mechanism, measured

Reproduced directly, with the venv's `ansible-playbook` on `PATH`:

```bash
cd src/provisioning
PATH="$PWD/.venv/bin:$PATH" .venv/bin/dotfiles-provision verify
```

Exit **0**, `failed=0`, and on stderr:

```
TASK [verify : Assert btop.conf disables save_config_on_exit]
[WARNING]: Jinja constant strings should not contain embedded templates.
This feature will be disabled by default in ansible-core 2.23.
Origin: .../roles/verify/tasks/main.yml:1289:11

1287 - name: Assert btop.conf disables save_config_on_exit
1288   ansible.builtin.assert:
1289     that: >-
                 ^ column 11
```

The warning is emitted from
`ansible/_internal/_templating/_jinja_plugins.py:321`
(`_jinja_const_template_warning`), whose own help text names the two shapes:

```
Use inline expressions, for example:
  `when: "{{ a_var }}" == 42` becomes `when: a_var == 42`
  `msg: "{{ lookup('env', '{{ a_var }}') }}"` becomes `msg: "{{ lookup('env', a_var) }}"`
```

i.e. **a template nested inside a Jinja string literal**.

### The trigger, pinned by probe

A four-case playbook was run to separate the shape from ordinary templating
(`/tmp/opencode/jinja-probe/probe.yml`):

| case | construct | warning? |
|---|---|---|
| **A** | `'x' is search('save\\s*=\\s*{{ ver }}')` — template inside a Jinja string literal | **YES** |
| **B** | `'x' is search('save\\s*=\\s*' ~ ver)` — inline concatenation | no |
| C | top-level template in a `fail_msg` | no |
| D | `lookup('env', 'HOME')` — plain literal argument | no |

So the rule is narrow: `{{ }}` **inside a quoted literal of a Jinja expression**.
A top-level `{{ }}` in any string is untouched, which is why the rest of the
tree's ~100 templated strings are fine and only two sites warn.

Ansible dedupes warnings by message, so A and the two real sites produce one
line — the origin shown is whichever fires first. The count below is from
reading the tree, not from counting warning lines.

## §2 The two sites

`roles/verify/tasks/main.yml`, both `ansible.builtin.assert` tasks that grep the
rendered `btop.conf`:

```yaml
# :1273-1277  Assert btop.conf selects the minimal theme
that: >-
  verify_btop_conf_grep.stdout is search(
    'color_theme\s*=\s*["'']{{ verify_btop_theme_selected }}["'']')

# :1287-1291  Assert btop.conf disables save_config_on_exit
that: >-
  verify_btop_conf_grep.stdout is search(
    'save_config_on_exit\s*=\s*{{ verify_btop_save_config_on_exit }}')
```

Both are `when: not ansible_check_mode`, which is why the dry-run integration
suite passes clean and never reports them.

## §3 The fix

Inline concatenation, which **the same file already uses** at
`:283` (`'(?m)^' ~ verify_bluetooth_rfkill_type ~ '\s+unblocked'`) and
`:1162` (`verify_xdg_config_home | trim ~ '/zsh'`). The two btop sites are the
only ones that did not follow the house style.

```yaml
that: >-
  verify_btop_conf_grep.stdout is search(
    'color_theme\s*=\s*["'']' ~ verify_btop_theme_selected ~ '["'']')
```

and

```yaml
that: >-
  verify_btop_conf_grep.stdout is search(
    'save_config_on_exit\s*=\s*' ~ verify_btop_save_config_on_exit)
```

Probe case B is the proof that this is not merely *a* rewrite but an equivalent
one: it warns not, and the assertion passes.

> The quote class `["'']` is load-bearing and must be preserved exactly. It is a
> Jinja single-quoted literal in which `''` is an escaped quote, so the value is
> the regex class `["']` — match a double *or* single quote. Splitting the
> literal around the variable must not disturb that escaping.

## §4 The gate, and why it is not the dry-run test

**The obvious guard does not work.** `tests/integration/test_ansible_dryrun.py`
already shells `ansible-playbook --check` and asserts a clean recap — but
`--check` **skips** both offending tasks (`when: not ansible_check_mode`), so the
warning is unreachable from that suite. Any guard built on it would be green
forever while the defect survives. This is recorded because it is the first
thing a reviewer will reach for.

Nor can the guard be "assert stderr carries no warnings": the dry-run test
already documents that `INJECT_FACTS_AS_VARS` on `ansible-core >= 2.21` is an
expected warning, so a blanket assertion would fail on a known-good warning and
need an allowlist anyway.

**Chosen: a static lint** over the Ansible tree. It is precise because the
context is known:

- Scan only value contexts where the string *is* a Jinja expression:
  `assert.that` (including list items), `when`, `changed_when`, `failed_when`,
  `until`.
- Within those values, find quoted regions (`'…'` and `"…"`) and flag any that
  contain `{{`.

Parsing the YAML (rather than grepping lines) is what makes this correct for
**folded block scalars**: both offending `that:` values span two lines, so a
line-oriented grep sees `is search(` and the template on separate lines.

The context restriction is what removes the false positives a naive
`grep "'[^']*{{"` produces — `packages.yaml:26-27`, `verify:607-608`, and
`cli_tools:177` all contain `'…{{ … }}…'` inside `fail_msg` text, where the
quotes are literal characters and the template is top-level. Those are correct
code and must not be flagged.

**Dependency**: PyYAML, already present in the provisioning environment and
already used by `scripts/icons-json-drift.py`, which runs through
`uv run --directory src/provisioning`.

## §5 Scope boundaries

This change touches **no runtime behaviour and no provisioning outcome**. The
two assertions keep asserting the same thing about the same file; only the way
the regex is assembled changes, and probe B shows the assembly is equivalent.

The `~` concatenation produces a *string*, and `is search()` accepts one — the
existing sites at `:283` and `:1162` are the precedent that this is the
supported form rather than a workaround.

## §6 Out of scope (recorded)

- **`INJECT_FACTS_AS_VARS`.** A separate, expected deprecation warning already
  documented in the dry-run test as non-fatal. Not this change's business, and
  deliberately not swept into "make warnings clean" — the two have different
  fixes and different owners.
- **A blanket "no warnings" policy for `verify`.** Attractive and wrong for the
  same reason: it would fail on the known-good warning and force an allowlist
  that hides the next real one.
- **`ansible-lint`.** Not installed, and the construct has no lint rule today;
  adding a linter to catch one pattern is heavier than the ~40-line lint, and a
  linter's rule set would then be a second thing to keep current.
