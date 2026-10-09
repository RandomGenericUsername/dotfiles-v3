# Sally UX review — live media metadata findings

**Date:** 2026-10-02  
**Scope:** Review of the approved audio-row UX contract against the live Chrome, Firefox, and Tidal MPRIS/AGS comparison.

## Verdict

The approved row concept remains sound. The app identity must remain persistent, with the current track title and artist shown as separate media metadata. The live defect is in how the current implementation selects row text, not in the approved information hierarchy.

## Findings

1. **Use available track metadata while the stream is live.** MPRIS supplied title/artist for all three active players. AGS also held those values, but Chrome and Tidal rendered an empty subtitle and Firefox rendered `AudioStream`. The visible media line should prefer MPRIS title/artist whenever present.
2. **Treat generic PipeWire labels as unavailable media metadata.** `Playback` and `AudioStream` describe stream/backend state, not the track. If MPRIS has no title, keep the app name visible and leave the media subtitle absent or use a verified track-specific PipeWire name. Never show a generic stream label as a song title.
3. **Preserve the row through seek updates.** The app label, route, volume, mute, player association, and focus should remain attached to the same logical row while position changes. The reported Firefox blink still needs an instrumented seek capture to identify whether the cause is row replacement, label write, or another GTK redraw.
4. **Do not treat this as a control or routing redesign.** The owner has validated those functions. Keep the known work focused on metadata precedence and stable rendering.

## Acceptance examples

- Chrome Playing `Cowboy Bebop | Lofi Hiphop & Jazzhop Mix` by Ambition shows that title/artist without requiring pause or popup reopen.
- Tidal Playing `Opus Pocus` by Jason Becker shows its MPRIS title/artist rather than an empty media line.
- Firefox Playing `Cowboy Bebop Study Music and Chillout` by Musically Chill shows its MPRIS metadata rather than `AudioStream`.
- Seeking in Firefox changes only the position display; it does not visibly blink or reset the row.

The OpenSpec scenarios now encode these behaviors. No visual hierarchy changes are needed; implementation should correct the data priority and preserve row identity.
