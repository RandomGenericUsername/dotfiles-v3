-- General configuration (Lua API)
--
-- gaps_out pinned (owner decision 2026-09-02): the 20px default created a
-- large visual gap between the AGS bar and windows. Per-side values: small
-- top gap so windows hug the bar, modest 8px on the other edges.
-- gaps_in keeps the default spacing between tiled windows.

hl.config({
    general = {
        gaps_in  = 5,
        gaps_out = {
            top    = 4,
            right  = 8,
            bottom = 8,
            left   = 8,
        },
    },
})
