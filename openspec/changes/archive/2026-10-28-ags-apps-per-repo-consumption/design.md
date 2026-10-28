# Design: Consume AGS apps as independently pinned repos

## Context

The current composition pins one `ags-apps` monorepo tag and the `ags_apps`
role installs every app from that checkout. The target units, the runtime
manifest contract and the provisioning role are defined by
`ags-apps` EPIC-002 / REQ-008. This change owns the composition-side data and
gates.

See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**

- One `apps.yaml` ownership list and one `program-tuple.yaml`.
- Deploy coverage proves one owner per app and all derived surfaces.
- A reversible per-app cutover recipe.
- No `ags-apps` pin or empty meta repo at completion.

**Non-Goals:**

- The `dotfiles-provision` role implementation.
- The runtime manifest driver or app code.
- Creating app repos or bumping their tags.
- The clipboard rename's app/runtime implementation.

## Decisions

1. **One list with `owner`.** The old and new roles both consume `apps.yaml` and
   filter by owner. A cutover is one composition commit flipping the entry; no
   separate deny-list or duplicate app metadata.
2. **One program tuple record.** Platform/contracts/assets tags are
   composition-owned and single-valued; app entries carry repo/tag only. A tuple
   bump is program-wide and revalidates every app.
3. **Deploy coverage is the composition gate.** It reads `apps.yaml`,
   `program-tuple.yaml` and the installer role shape, then asserts the union and
   all surfaces. The provision verify role mirrors it.
4. **Cutover is quiesce → flip → install/start → verify.** A running link is never
   hot-swapped; the old instance is stopped first and the new identity is
   verified from `ags list`/`/proc` and the links.
5. **No permanent meta repo.** `ags-apps` is the migration workshop only; the
   final state removes its pin/role and archives it.

## Risks / Trade-offs

- **Cross-repo sequencing risk** → the provision/runtime/contracts/app
  prerequisites are separate tickets; no app cutover starts until they are
  pinned and the fake-app fixture is green.
- **One list becomes a single point of drift** → schema validation + deploy
  coverage + verify run the same fixture.
- **Rollback loses user state** → installed tags are immutable and user state
  lives outside them; the app/provision tickets own the state migration tests.
- **Tuple bump fan-out** → one tuple is cheaper than per-app skew but requires a
  program-wide revalidation; documented as a deliberate trade-off.

## Migration Plan

1. Add `apps.yaml` with all seven entries `owner: legacy`, plus
   `program-tuple.yaml`.
2. Add schema/fixture validation and deploy-coverage assertions for the union,
   tuple and surfaces.
3. Add docs and the cutover checklist.
4. Each app cutover flips one entry after its prerequisites; the audit gate runs
   after every flip.
5. After the last app, remove the old role/pin and archive `ags-apps`.

Rollback: reverse the owner flip and reinstall/start the old unit; the audit gate
must pass the same one-owner invariant.

## Open Questions

- Exact tag values in `program-tuple.yaml` are set at the REQ-008 release.
- GitHub archive vs deletion is decided at the final closeout.

## Workflow follow-up

- Archive this OpenSpec change after all tasks and the final composition cutover
  are verified.
