-- Cursor configuration (Lua API)

hl.config({
    cursor = {
        -- Hardware cursors, so the cursor is a KMS plane rather than being
        -- drawn INTO the composited frame. With software cursors every capture
        -- contains the pointer no matter what the client asks for: `grim -c`
        -- and `-c`-less output are byte-identical (measured), so the capture
        -- tool's "Include cursor" toggle was a control that could not work —
        -- screenshots always showed the cursor. With hardware cursors the
        -- cursor is capturable on request, which is what `grim -c` (screenshots)
        -- and `gpu-screen-recorder -cursor yes|no` (recordings) rely on.
        no_hardware_cursors = false,
    },
})
