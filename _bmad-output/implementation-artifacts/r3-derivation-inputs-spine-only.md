# R‑3: Derivation Inputs Resolve From the Spine Only

Status: done

baseline_commit: 01a5e94

Gate 1: approved (env var; typed error; tripwire in `doctor` only). Gate 2: applied — Items 1–7 + ratified the `find_*`/`require_input` split. Key corrections from the panel: `verify` find is now `recurse: true` (nested icon-templates) + sibling mappings pinned + fixture seeds content; dev-override repo candidates repointed at the real `dotfiles/assets/icon-templates/` and `dotfiles/config/icon-template-color-scheme-mappings/`; repo-sourced provenance now dirties `doctor`; the dead repo-ancestor fallback in `itr_adapter.py` removed; resolver hardening (enumerate candidates, warn-once, docstring, test isolation).

Epic: Phase 5 prerequisite remediation (see `epics-dotfiles-runtime-phase5.md`; AD‑43).

## Story

As an operator relying on a provisioned machine,
I want the runtime to read its derivation inputs from the install spine only,
so a missing input fails loudly instead of being silently satisfied from a repo checkout
(and the "works without the repo" guarantee actually holds).

## Context (the caveat, grounded)

`derive.find_*` resolve **spine first, then walk repo ancestors** (`application/derive.py:73,103,157,214`). On a real install the repo walk is inert, but on a dev/test machine it silently reads the repo when the spine lacks an input — **masking a provisioning gap** that only bites end users. `verify` today asserts the input **containers** (dirs) exist, and only the weg-effects **file** (`verify_install_spine_dirs` / `verify_install_spine_files`) — not that `icon-mappings/icons.yaml` exists or that the template dirs are non‑empty.

## Acceptance Criteria

1. In production (no dev override set), `derive.find_*` resolve the **install spine only**: the repo‑ancestor walk is removed/disabled. A missing input raises a **loud typed error naming the input and the spine path** (never a silent repo read, never a bare `None` that fails far away). (AC 1)
2. A single **explicit opt‑in dev override** (env var, e.g. `DOTFILES_DEV_INPUTS_ROOT`) restores repo resolution for development; its use is **logged/surfaced**, never implicit. (AC 2)
3. Provisioning `verify` asserts input **content**, not just containers: `icon-mappings/icons.yaml` (plus sibling mappings), a non‑empty `icon-templates/`, a non‑empty `config/color-scheme-generator/templates/`, and the existing `config/weg/effects.yaml`. (AC 3)
4. A runtime **provenance tripwire** (`doctor` and/or `check-inputs`) detects an input resolved from the repo (not the spine) and surfaces it loudly in production. (AC 4)

## Tasks / Subtasks

- [ ] `application/derive.py`: resolve spine‑only; drop the implicit ancestor walk behind the explicit override; raise a typed error naming the missing input + spine path (AC: 1, 2)
- [ ] Document + wire the override env var (composition root / `_resolve_install_spine` seam) (AC: 2)
- [ ] `provisioning/ansible/roles/verify`: add content assertions for the four inputs (AC: 3)
- [ ] Provenance tripwire in `doctor`/`check-inputs` (record each input's source; fail/warn when repo‑sourced in production) (AC: 4)
- [ ] Tests: spine‑only resolution; missing input → loud typed error; override restores repo resolution (and is logged); provenance tripwire flags a repo‑sourced input (AC: 1–4)
- [ ] Run `uv run --directory src/runtime pytest` + `ruff` + `mypy` + `test_layering.py`

## Dev Notes

- **Layering:** path resolution is I/O — `find_*` already live in `application/derive.py` (existing seam). If a new port is warranted, keep the domain pure.
- **AD‑11:** inputs are read‑only; this story only *narrows where they are read from*. It does not change read semantics.
- **AD‑43/AD‑44:** the "input set" is part of the derivation contract; where it resolves from is an invariant, not an implementation detail.
- **Interaction:** enabling the dev override must not weaken the provenance tripwire — a repo‑sourced input is flagged even in dev (as informational) and is an error in production.

## Gate‑1 sub‑decisions

1. **Override mechanism:** a single env var (e.g. `DOTFILES_DEV_INPUTS_ROOT` pointing at the repo), recommended — or keep the ancestor walk behind a boolean flag? (Recommend: explicit root var; kill the implicit walk.)
2. **Provenance tripwire home:** `doctor` (health surface), `check-inputs` (stale surface), or both? (Recommend: record source in the resolver; surface in both.)
3. **Missing input error type:** a new typed error (e.g. `MissingDerivationInput`) vs an existing `RuntimeError`? (Recommend: typed, naming the input + spine path.)
