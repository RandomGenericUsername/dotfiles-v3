/**
 * The Theme port (spine AD-13; doc 101 §11 named the seam, §4 defined no port).
 *
 * A `Theme` adapter applies the palette (`colors.gtk.css`) and every app routes
 * theming through it, so the direct `app.apply_css` calls and the three
 * duplicated `theme.ts` copies stop drifting. This module holds the port and the
 * injected CSS sink; the adapter supplies the display and the stable artifact
 * path.
 *
 * WHY THE SINK IS INJECTED. Applying CSS needs the GTK display (a `gi://`
 * import); deciding WHICH artifact to apply is policy that should be pinned by a
 * test. The core takes the stable palette path once and hands it to the sink, so
 * a fake sink proves the adapter applies the stable pointer — never a generation
 * path, which would cache a stale palette after `wallpaper.state` repoints the
 * symlink (review F9).
 *
 * PURE: no `ags`, no `gi://*`, no I/O.
 */

export interface Theme {
  /** Apply the palette to the display. */
  apply(): void;
}

/** The one thing the port needs from the host: put a CSS file on the display. */
export interface CssSink {
  apply(path: string): void;
}

/**
 * `palettePath` is the STABLE pointer (`colors.css`), not the runtime's
 * generation path (`current/colors.gtk.css`): the stable pointer is repointed
 * when the palette changes, so re-applying it is never stale (F9).
 */
export function createTheme(palettePath: string, sink: CssSink): Theme {
  return {
    apply(): void {
      sink.apply(palettePath);
    },
  };
}
