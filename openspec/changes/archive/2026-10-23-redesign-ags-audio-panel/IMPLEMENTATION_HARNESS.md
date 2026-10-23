# Audio panel agent harness

Use this file together with `proposal.md`, `design.md`, `specs/ags-audio-panel/spec.md`, and `tasks.md` before making changes.

## Worktree boundary

- Repository root: `/home/inumaki/Development/dotfiles-v3-audio-panel`.
- Branch: `codex/audio-panel-redesign`.
- Do not edit `/home/inumaki/Development/dotfiles-v3` (`master`).
- The starting working-tree edits to the audio UI/state and the UX artifacts are preserved inputs. Do not reset, overwrite, or wholesale reformat them.
- Do not edit files owned by another assigned task. Keep each assignment's file boundary and report any required cross-boundary change to the coordinator first.

## Product and architecture invariants

1. There is one preferred system output. Apps follow it unless the user explicitly routes that app elsewhere.
2. Route intent is `FollowPreferred`, `Explicit(endpoint)`, or `Unknown`. Endpoint equality never proves intent. An explicit route matching the old default stays explicit and must be reasserted if WirePlumber moves that same stream after a default change.
3. New streams without an observed override follow the preferred output. Existing streams with unrecoverable history are `Unknown` while still showing their observed endpoint.
4. Output-device gain/mute and each app's stream gain/mute are separate controls. Muting preserves gain. App controls affect only streams belonging to that app; account for more than one stream per app rather than silently selecting the first.
5. MPRIS title, artist, playback state, and artwork are the media source of truth when available. Generic PipeWire labels (`Playback`, `AudioStream`) never replace real MPRIS metadata. Keep app identity visible separately.
6. A row may outlive its PipeWire stream or MPRIS player independently. Stream writes require a current stream; player actions require a current capable player. A transient unlink/relink must not transfer commands to another app.
7. PipeWire and MPRIS are observed through event-driven adapters. Do not put either on the dotfiles domain event hub and do not add periodic state polling.
8. Runtime GTK colors come from generated `colors.css` tokens. Preserve the approved compact layout and Sally/accessibility requirements in the linked UX artifact.
9. Keep Firefox seek-position inconsistency and blink as separate unresolved observations; do not claim either is fixed without live evidence.

## Assignment protocol

- Follow the OpenSpec apply workflow and work only on the task IDs explicitly assigned to you.
- Read all four source-of-truth artifacts plus `validation/current-boundary-review.md` and `validation/README.md` first.
- Use the task acceptance criteria; do not widen product scope or replace them with assumptions.
- Do not run a command that changes live playback/routing unless that exact validation is assigned and the command restores the original state in `finally`.
- Keep tests and prototypes under `openspec/changes/redesign-ags-audio-panel/validation/` or the source module's established test location.
- Do not mark a task complete until its behavior and checks are verified. Do not edit shared task checkboxes; the coordinator owns `tasks.md`.

## Report back

Report:

- assigned task IDs and their outcome;
- files changed;
- checks run and exact pass/fail result;
- assumptions, blockers, or acceptance criteria not met;
- any requested change outside your assigned file boundary.
