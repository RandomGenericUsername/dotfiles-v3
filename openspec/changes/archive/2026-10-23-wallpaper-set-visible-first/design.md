## Context

Today `_run_wallpaper_set` (`runtime/cli/main.py:442-538`) composes
`ApplyWallpaperUseCase.run` (validate → import wallpaper → ensure palette
[hard] → ensure effects/icons [graceful] → save `current.json`) then
`ReconcileDesktopStateUseCase.run(trigger="set")` (repoint `current/`
symlinks incl. `wallpaper*.png` → history → reload Hyprland/AGS/Hyprpaper/
terminal). The screen changes at the END (hyprpaper reload). `current.json`
requires only `wallpaper` (+monitors/applied_at); palette/effects/icons are
nullable (`contracts/schemas/current.schema.json`) — a wallpaper-only state
is schema-valid. GUI progress arrives via `wallpaper.state`
(`applying` → `done`/`error`); the GUI's `doApply` already collapses on
success and gates re-entry on a local `applying()` flag.

## Goals / Non-Goals

**Goals**

- Pixels change in well under a second; theming follows without blocking.
- Exactly one new additive event state; `done`/`error` semantics unchanged.
- No new concurrency model: the existing `.seed.lock` mutex serializes
  sets; a set arriving mid-flight fails fast with a clear busy error
  (CLI) and is unclickable (GUI busy gate).

**Non-Goals**

- See proposal. Additionally: no daemon/Phase-5 reactive-converge
  redesign — converge keeps composing the same pipeline (it must observe
  the same event sequence).

## Decisions

### D1. Split `wallpaper set` into visible-swap + themed-converge, same process

New application orchestration (composition root stays in `main.py`, no
application-layer orchestrator per AD-12):

1. **Visible swap (fast, synchronous):** validate input → import wallpaper
   bytes to cache → save `current.json` with the new wallpaper layer and
   `palette/effects/icons: null` (monitors preserved, AD-18) → repoint ONLY
   wallpaper symlinks → hyprpaper reload → emit `visible`.
2. **Themed converge (same process, still holding the mutex):** ensure
   palette/effects/icons via `DerivationPipeline` (unchanged) → save full
   `current.json` → full repoint → history append (`trigger="set"`) →
   reload all consumers → emit `done`.

The mutex is held across BOTH phases (a second set fails busy instead of
racing a half-themed state). Total wall-time is unchanged; *perceived*
time collapses to phase 1.

### D2. `visible` is additive on the existing topic, `done` still unlocks

`wallpaper.state` payload gains `state="visible"` (with `wallpaper_hash`)
between `applying` and `done`. Per `event-contract.json` versioning, an
additive state on `org.dotfiles.Events1` is non-breaking; old consumers
ignore unknown states (GUI treats any non-`done`/`error` as busy — verify
in implementation). `error` before `visible` = swap failed (old behavior);
`error` after `visible` = theming failed with the new wallpaper already on
screen (state reflects exactly that; GUI shows wallpaper LIVE + theming
warning instead of a failure banner).

### D3. Busy gate is event-driven, browse stays live

GUI extends its existing `applying()` gate to the event stream: Apply
buttons/pills disabled while last observed state is `applying` or
`visible`; grid/search/drill/checkbox unaffected. Phase-5 reactive
consumers (`GetTopicState`) see the same sequence — no special-casing.

### D4. Cache-hit fast path is preserved, not bypassed

When all three layers hit cache, phase 2 is milliseconds (entry-dir
existence checks, zero tool invocations) — behaviorally identical to today
plus the early `visible`. No separate code path for hits; one pipeline.

### D5. Rollback on swap failure only

If phase 1 fails (bad input, import error, hyprpaper reload error), nothing
changed on screen: propagate loudly as today (non-zero exit, `error`
event). If phase 2 fails, the guardrails of each layer apply (palette hard
⇒ `error` with wallpaper live; effects/icons graceful ⇒ `done` degraded) —
never revert the visible wallpaper (reverting would steal back a change the
user already saw and approved implicitly).
