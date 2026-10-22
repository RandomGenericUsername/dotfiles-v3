#!/usr/bin/env python3
"""Embedded-template lint for the Ansible tree.

ansible-core emits, on every ``verify`` run, this warning:

    [WARNING]: Jinja constant strings should not contain embedded templates.
    This feature will be disabled by default in ansible-core 2.23.

The construct is exactly this: a ``{{ }}`` template placed INSIDE a Jinja
string literal of an expression-context value, for example

    that: >-
      stdout is search('save_config_on_exit\\s*=\\s*{{ the_var }}')

Today Ansible resolves the inner ``{{ }}`` before evaluating the outer
expression, so the regex is built correctly -- but the resolution is the
feature ansible-core 2.23 disables. After 2.23 the braces stay literal and the
regex never matches, so the assertion fails against a value that is in fact
correct. The durable form joins the parts with ``~``:

    that: >-
      stdout is search('save_config_on_exit\\s*=\\s*' ~ the_var)

WHY THIS IS A LINT AND NOT THE DRY-RUN TEST. ``ansible-playbook --check``
SKIPS the affected tasks (they are ``when: not ansible_check_mode``), so the
warning is unreachable from ``tests/integration/test_ansible_dryrun.py``. That
reason is recorded as a comment at that suite, because it is the first guard a
reviewer reaches for.

WHY IT PARSES YAML AND DOES NOT GREP. Both real offenders are folded ``>-``
block scalars spanning two lines, so the literal and the template land on
different lines and a line-oriented ``grep "'[^']*{{"`` sees neither. Parsing
also lets the scan be restricted to EXPRESSION contexts -- ``assert.that``
(including list items), ``when``, ``changed_when``, ``failed_when``, ``until``
-- where the value *is* a Jinja expression and a nested template is the defect.

The restriction is the whole difference between a gate and noise. The tree
contains ``'...{{ ... }}...'`` inside ``fail_msg`` text (where the quotes are
literal characters and the template is correctly top-level) at
``packages.yaml``, ``roles/verify/tasks/main.yml``, ``roles/cli_tools/tasks/
main.yml`` and others; a naive quote grep flags all of them. Those are correct
code and are deliberately not in scope: only expression contexts are scanned.

Usage: ``python3 scripts/ansible-embedded-template-lint.py [--root REPO_ROOT]``
Exit 0 = no nested template in any expression-context value.
Exit 1 = at least one finding; each names file, line and the offending literal.

Needs PyYAML. Run it through an ephemeral uv environment (the provisioning
package is external now):

    uv run --no-project --with pyyaml python scripts/ansible-embedded-template-lint.py

The Ansible tree is read from the PINNED external engine checkout
(`dotfiles/provisioning/installer.pin`, cached at
`.dev/dotfiles-provision-<tag>/`), not from this repo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from engine_checkout import EngineCheckoutError, engine_checkout, read_engine_pin

#: Keys whose value IS a Jinja expression (not a template string). ``that`` is
#: the assert module's expression key; the others are the standard condition
#: expressions. A nested template in any of these is the defect.
EXPR_KEYS = frozenset({"that", "when", "changed_when", "failed_when", "until"})

#: Relative to the pinned ENGINE checkout root. Scoped to its Ansible tree.
ANSIBLE_SUBTREE = Path("ansible")


def _scalar_values(node: Node) -> list[ScalarNode]:
    """Return the scalar leaves of a value node (a scalar, or a list of them).

    ``assert.that`` and ``when`` both accept a list, so each item must be
    checked; anything deeper is not a valid expression value and is ignored.
    """
    if isinstance(node, ScalarNode):
        return [node]
    if isinstance(node, SequenceNode):
        leaves: list[ScalarNode] = []
        for item in node.value:
            leaves.extend(_scalar_values(item))
        return leaves
    return []


def _quoted_regions(text: str) -> list[str]:
    """Return the ``'...'`` / ``"..."`` regions of a Jinja expression string.

    Handles the two escape forms a Jinja (Python-like) literal can carry:
    a backslash escape (``\\'``) and a doubled delimiter (``''``). Both are
    treated as "stay inside the literal", so a region is never split at a
    quote that is part of the literal's own syntax. That is what keeps the
    load-bearing ``["'']`` in the btop regex a single region rather than two.
    """
    regions: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch not in ("'", '"'):
            i += 1
            continue
        quote = ch
        start = i
        i += 1
        while i < n:
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if c == quote:
                if i + 1 < n and text[i + 1] == quote:
                    i += 2
                    continue
                i += 1
                break
            i += 1
        regions.append(text[start:i])
    return regions


def _walk(node: Node, visit) -> None:
    """Visit every expression-context scalar under a composed YAML node."""
    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode) and key_node.value in EXPR_KEYS:
                for scalar in _scalar_values(value_node):
                    visit(key_node.value, scalar)
            _walk(value_node, visit)
    elif isinstance(node, SequenceNode):
        for item in node.value:
            _walk(item, visit)


def _findings_in_file(path: Path, display: str) -> list[str]:
    findings: list[str] = []
    try:
        documents = list(yaml.compose_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as exc:
        # A file the lint cannot parse is itself a finding: silently skipping it
        # would make the gate blind to exactly the files it cannot read.
        findings.append(f"{display}: YAML parse error: {exc}")
        return findings

    def visit(key: str, scalar: ScalarNode) -> None:
        for region in _quoted_regions(scalar.value):
            if "{{" in region:
                line = scalar.start_mark.line + 1
                literal = " ".join(region.split())
                if len(literal) > 120:
                    literal = literal[:117] + "..."
                findings.append(
                    f"{display}:{line}: '{key}' nests a template inside a Jinja "
                    f"string literal: {literal}"
                )

    for document in documents:
        if document is not None:
            _walk(document, visit)
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Ansible embedded-template lint")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    try:
        pin = read_engine_pin(root)
        engine_root = engine_checkout(root)
    except EngineCheckoutError as exc:
        print(f"FAIL {exc}")
        return 1
    ansible_root = engine_root / ANSIBLE_SUBTREE
    if not ansible_root.is_dir():
        print(f"FAIL: Ansible tree not found at {ansible_root} (lint cannot run)")
        return 1

    files = sorted(
        [p for p in ansible_root.rglob("*.yml")] + [p for p in ansible_root.rglob("*.yaml")]
    )

    findings: list[str] = []
    for path in files:
        findings.extend(_findings_in_file(path, str(path.relative_to(engine_root))))

    print(
        f"CHECK embedded templates in expression contexts "
        f"({len(files)} file(s) scanned under engine {pin} {ANSIBLE_SUBTREE})"
    )

    if findings:
        for finding in findings:
            print(f"FAIL {finding}")
        print(
            f"ansible-embedded-template-lint: {len(findings)} finding(s) — join "
            f"the parts with `~` instead of nesting `{{{{ }}}}` in a literal"
        )
        return 1

    print("ansible-embedded-template-lint: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
