# Design: interval as ms entry + config migration

## Entry behavior (`WifiContent.tsx`)

- `Gtk.Entry`: `inputPurpose=NUMBER`-ish (numeric input mode), right-aligned
  tabular numerals, text = raw ms. Local `createState` holds the *draft*
  text; the service config holds the *committed* value (draft ≠ committed
  is what makes revert-on-junk possible).
- `humanize(ms)`: `0`→`Off`, `<1000`→`N ms`, `<60000`→`N s`, else `N min`
  (1 decimal). Shown in `.settings-stc-value`-class hint next to the entry.
- `commit(raw)`: strip non-digits → `NaN`/≤0 → `0` (Off); `<1000` → `1000`;
  else round. Write via `setConfigValue({ interval_ms })`; chips set the
  entry text + commit immediately.
- CSS: `.settings-stc-entry` (field surface per GUI-family "fields are
  surfaces"), `.settings-stc-hint`, `.settings-stc-caption`, `.settings-chip`
  (+ `.active`) per `state-2-stc-expanded`.

## Migration (`speedtest-service.ts`, `wifi-speedtest.json`)

- Type: `{ interval_ms: number; run_on_connect: boolean; server_mode: "auto" }`;
  default `interval_ms: 900000` (== old 15 min).
- `loadConfig()`: if parsed has `interval_min` and no `interval_ms`,
  `interval_ms = interval_min * 60000`, delete legacy key, `saveConfig`.
- Scheduler: `timeout = c.interval_ms` directly (drop `* 60 * 1000`).
- Skeleton `wifi-speedtest.json` updated to the new shape (already deployed
  by `compositor_configs` — no new skeleton entry needed).

## Contract table

| Mock element (`state-2-stc-expanded`) | Code owner |
|---|---|
| ms entry + suffix + hint | entry + `humanize` + hint label |
| Caption + chips | static caption + chip buttons |
| Scheduler honors value | `interval_ms` plumbing + migration |

## Verification

- Parity gate → 0. Type `500` → commits `1000`; type junk → reverts;
  chips set exact values; legacy `interval_min` file migrates once and
  the scheduler fires on the converted cadence (short test value, then restore).
