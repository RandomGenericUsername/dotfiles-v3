// AGS v2 minimal bar skeleton (Story 1.14, AGS-for-Waybar swap 2026-08-18).
//
// The SIMPLEST AGS project that proves the provisioned AGS (aylurs-gtk-shell-git)
// works end-to-end: a single window per monitor with a label, styled from the
// runtime palette fragment.
//
// Runtime-independence (config-in-spine): this app.tsx is COPIED into the spine
// by the compositor_configs role and its `~/.config/ags` is a symlink into the
// spine. The palette fragment colors.css is also copied into the spine
// (colors.gtk.css renamed) and is applied AT RUNTIME via app.apply_css() — NOT
// bundled at build time — so the Phase 2 runtime can repoint
// ~/.config/ags/colors.css -> current/colors.gtk.css and the swap takes effect
// on the next `ags run` (process restart — AGS has no native hot-reload).
//
// This is the seed the Phase 2 runtime culture is wired against; keep it
// minimal — do not gold-plate.
import app from "ags/gtk4/app"
import { Astal, Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"

export default function Bar(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

  return (
    <window
      visible
      name="bar"
      class="bar"
      gdkmonitor={gdkmonitor}
      exclusivity={Astal.Exclusivity.EXCLUSIVE}
      anchor={TOP | LEFT | RIGHT}
      application={app}
    >
      <centerbox cssName="centerbox">
        <box $type="start">
          <label label="dotfiles" />
        </box>
        <box $type="end">
          <label label="✨" />
        </box>
      </centerbox>
    </window>
  )
}

app.start({
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    app.get_monitors().map(Bar)
  },
})