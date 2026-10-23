## Why

`dotfiles-runtime wallpaper set` currently derives everything (CSG palette in
a container, WEG effects, ITR icons) BEFORE the screen changes: apply derives
the three layers, persists `current.json`, and only then does reconcile
repoint symlinks and reload hyprpaper. The user stares at the old wallpaper
for the whole derivation with no benefit — the wallpaper bytes are already
on disk from the start.

## What Changes

- `wallpaper set` performs a **visible-first swap**: import the wallpaper
  into the cache, persist the wallpaper layer in `current.json`, repoint the
  wallpaper symlinks and set hyprpaper **immediately**, then derive
  palette/effects/icons and reload the themed consumers (Hyprland, AGS,
  terminal) as derivation completes.
- A new additive `visible` state on the `wallpaper.state` domain event
  (contract versioning: additive signal on `org.dotfiles.Events1`, non-breaking)
  tells consumers the screen changed while theming is still in flight;
  `done`/`error` keep their exact meaning (pipeline finished → UI unlocks).
- While `applying` (now spanning visible → done), consumers MUST NOT issue a
  new set: the wallpaper-selector disables Apply controls but stays fully
  browsable (grid, search, drill-down all live; only set/apply is gated).
- Failure policy: a derivation failure after the swap keeps the new
  wallpaper on screen, degrades the failed layer gracefully (existing
  per-layer policy: palette hard-fails the theming pass but never reverts
  the visible wallpaper), surfaces a warning, and still emits `done` with
  the degraded state (or `error` only if the swap itself failed).

## Non-goals

- No change to derivation inputs, cache layout, hashing, or per-layer
  failure policy beyond ordering.
- No queueing and no last-write-wins: concurrent sets are rejected by the
  existing state mutex (second caller gets a clear busy error), and the GUI
  prevents them via the busy gate. True background cancellation is future work.
- No change to the contrast guard's behavior (see `icon-contrast-opt-out`);
  the guard runs in the post-visible derive pass and reads the same inputs.
