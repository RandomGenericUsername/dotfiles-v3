/**
 * The bar's `Theme` adapter (spine AD-13; doc 101 §4 named no port, §11 named
 * the seam).
 *
 * The pure port + core live in `../ports/theme`; this file supplies the
 * display. It applies the palette through AGS's `app.apply_css`, which is the
 * same call `app.tsx` made directly — the port only takes ownership of WHICH
 * artifact is applied, not HOW.
 *
 * THE PATH IS THE STABLE POINTER. `colors.css` is the provisioning-owned symlink
 * the runtime repoints at the current `colors.gtk.css` generation. Applying the
 * generation path directly would cache it, so a palette swap after
 * `wallpaper.state` would leave the bar stale (review F9). The stable pointer is
 * always current.
 */

import app from "ags/gtk4/app";
import GLib from "gi://GLib?version=2.0";
import { createTheme, type CssSink } from "../ports/theme";

//: The stable palette artifact: colors.css -> current/colors.gtk.css.
const PALETTE_CSS = `${GLib.get_user_config_dir()}/ags/colors.css`;

const appCssSink: CssSink = {
  apply(path: string): void {
    app.apply_css(path);
  },
};

//: The bar's one Theme; app.tsx calls `theme.apply()` in main().
export const theme = createTheme(PALETTE_CSS, appCssSink);
