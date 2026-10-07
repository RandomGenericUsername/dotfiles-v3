## Why

A clean `dotfiles-provision verify` run (exit 0, `failed=0`) carries a warning
that will become a hard failure:

```
TASK [verify : Assert btop.conf disables save_config_on_exit]
[WARNING]: Jinja constant strings should not contain embedded templates.
This feature will be disabled by default in ansible-core 2.23.
Origin: .../roles/verify/tasks/main.yml:1289:11
```

**Ansible routes warnings to stderr, the run still exits 0, and the warning
scrolled by.** It was only surfaced because the provisioning executor captures
`[WARNING]` header lines into the result — added precisely because *"a green
run's warnings scrolled by unnoticed"*.

### What breaks, and when

`ansible-core 2.23` disables embedded-template resolution by default. The two
offending assertions build a regex by nesting a template **inside a Jinja string
literal**:

```yaml
that: >-
  verify_btop_conf_grep.stdout is search(
    'save_config_on_exit\s*=\s*{{ verify_btop_save_config_on_exit }}')
```

Today Ansible resolves the inner `{{ }}` before the outer expression is
evaluated, so the regex becomes `save_config_on_exit\s*=\s*false`. Once the
feature is disabled, the literal keeps its braces, the regex never matches, and
**`verify` fails** — loudly, but pointing at a btop config that is in fact
correct.

Both offending assertions are guarded by `when: not ansible_check_mode`, so the
dry-run integration suite never reaches them and cannot report it.

## What Changes

- **Two sites** in `roles/verify/tasks/main.yml` (lines 1276-1277 and 1290-1291)
  switch from a nested template to **inline concatenation**, which the same file
  already uses correctly for two other regexes:

  ```yaml
  that: >-
    verify_btop_conf_grep.stdout is search(
      'save_config_on_exit\s*=\s*' ~ verify_btop_save_config_on_exit)
  ```

- **A static gate** so the next one is caught in review rather than in 2.23. It
  scans the Ansible tree for a template nested inside a Jinja string literal
  **in an expression context** (`assert.that`, `when`, `changed_when`,
  `failed_when`, `until`) — the only place the construct is meaningful and,
  measured, the only place it occurs.

## Capabilities

### New Capabilities

- `ansible-embedded-template-lint`: the Ansible tree carries no embedded
  templates inside Jinja string literals, and a gate keeps it that way.

### Modified Capabilities

- `verify` (provisioning): two btop assertions build their regex by
  concatenation rather than by nesting a template, so they survive
  `ansible-core 2.23` unchanged in intent and result.
