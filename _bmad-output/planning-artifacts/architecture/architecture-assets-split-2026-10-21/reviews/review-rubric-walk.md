# Reviewer gate — assets-split spine

Run 2026-10-21, headless. Subagent dispatch was unavailable in this session, so the gate ran
sequentially per `references/reviewer-gate.md` line 9 ("If subagents are unavailable, run
sequentially — write the file first, then flush it").

## Deterministic pass

```bash
python3 .agents/skills/bmad-architecture/scripts/lint_spine.py \
  --workspace _bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21
```

```json
{"ok": true, "spine": "ARCHITECTURE-SPINE.md", "total_findings": 0, "by_severity": {}, "findings": []}
```

## Rubric walk (good-spine checklist)

| Criterion | Verdict | Note |
| --- | --- | --- |
| Fixes the real divergence points for the level below | pass | 17 ADs cover entity boundaries, dependency direction, data shape (manifest), versioning (tag + schema), deployment (fetch + spine), operations (rollback, gates, idempotency), and supply chain. |
| Every Rule enforceable and prevents its stated divergence | pass after fix | AD-11 was a convention with no gate; S0 step 6 now carries a mechanical absence check (`icons.json` in-tree → `make validate` fails). |
| Nothing under Deferred lets two units diverge | pass | Every deferred item is a single-owner choice (layout, LFS, hash depth, registry, history, signing). |
| Named tech verified-current | pass after fix | JSON Schema draft 2020-12 confirmed on `json-schema.org/specification` (2026-10-21). Everything else is brownfield-read, not newly bound. |
| Ratifies rather than contradicts the brownfield codebase | pass | Destinations frozen (AD-7); verify's minimum-set semantics match current assets assertions. Eight brief↔repo contradictions are recorded in `EVIDENCE-INDEX.md`, none silently "fixed". |
| Covers the driving spec's capabilities | n/a | No `SPEC.md` drove this run (brief only). Flagged as the next step (`bmad-spec`). |
| No new AD weakens an inherited one | pass after fix | The cli-repos spine's AD-10 is now explicitly listed as **extended** (assets get a pin; `csg-templates` keeps the checkout path; `assets.yaml` stays authoritative). |
| Every dimension the altitude owns decided/deferred/open | pass after fix | The operational envelope gained two missing rows: fetch idempotency (tag-dir guard, one expected `changed`) and user-local files (`local.conf`, `.zshenv`, `active-theme` never pruned). The security/supply-chain envelope gained one: anonymous HTTPS, public corpus, `shellcheck` because scripts deploy 0755. |

## Findings raised and their disposition

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | high | AD-11 ("generated artifacts are never assets") was stated but had no executable gate — the exact "convention nobody runs" failure the precedent's AD-14 warns about. | **Autofixed** — S0 step 6 + a negative gate in S0's acceptance block. |
| 2 | high | The operational envelope was silent on fetch idempotency: stripping `.git` makes a naive re-clone report `changed` forever, which would corrupt the "no state drift" claim every slice makes. | **Autofixed** — Consistency Conventions now pins the `creates:`-style guard and the one expected `changed`. |
| 3 | medium | The operational envelope was silent on user-local files that must survive the new mirror deploys. | **Autofixed** — three named files + their existing guards cited. |
| 4 | medium | No security/supply-chain statement, though the corpus is public and deploys executable scripts. | **Autofixed** — one convention row. |
| 5 | medium | Inherited-invariant reconciliation was implicit: the cli-repos spine AD-10 also governs `assets.yaml`. | **Autofixed** — explicit "extends, does not replace" row. |
| 6 | low | `OPEN-3` (tag cadence) had a default but no statement of what breaks if it is answered differently later. | **Deferred** — it is a per-slice entry criterion (S1), and the default is reversible inside one MINOR. |
| 7 | low | Slice acceptance gates include `dev/vm-fresh.sh`/`dev/vm-verify`, which need incus and are local-only. | **Accepted as labelled** — every such gate is marked `PLANNED` and the reason is in `ARCHITECTURE.md:563`; no slice's mergeability depends on VM evidence alone. |

No finding required a human decision. No AD ID was renumbered; no brief invariant was reopened.
