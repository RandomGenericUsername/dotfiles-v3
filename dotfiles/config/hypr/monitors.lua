-- Monitor configuration
-- Single monitor, auto-detect preferred resolution and scale (Lua API)
--
-- scale = 1 (pinned, was "auto" -> 1.5): at 1.5 the logical desktop was
-- 1280x720 — everything drawn oversized and GTK3 apps (Thunderbird) rendered
-- overlapping text at the fractional scale (owner decision 2026-09-02 after
-- live comparison on the host).

hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
})
