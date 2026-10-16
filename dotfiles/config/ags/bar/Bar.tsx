import { Astal, Gdk } from "ags/gtk4"
import { BarWidget } from "../kit/widget"
import type { BarContext } from "../kit/widget"
import { resolveLayout, type BarEntry } from "../kit/layout"
import { repoDefaultLayout } from "./layout.default"
import { BAR_MANIFEST } from "./bar-manifest"
import { sanitizeLayout } from "./validate"
import { createBarContext, createWidgetRegistry } from "./registry"
import { readBarBackdrop } from "../lib/bar-backdrop"
import type { AudioPanelBinding } from "../audio/AudioPopup"

/**
 * The bar.
 *
 * The composition is DATA now (spine AD-9): the layout is resolved through the
 * user › runtime › repo-default chain (only the repo default exists today, and it
 * is always non-null), and each section's entries are rendered through the one
 * shape dispatcher (AD-8), keyed by entry id. `Bar.tsx` no longer names a single
 * widget component — adding, removing or reordering a widget is a layout edit.
 *
 * The resolved layout runs through the SAME validators provisioning enforces
 * strictly (spine AD-15; task 2.2) — but leniently: `sanitizeLayout` skips an
 * unknown widget, drops a duplicate single-instance repeat, and strips unknown
 * params (declared defaults apply), warning per decision instead of failing.
 * A missing glyph blanks at resolve time (`resolveIcon` returns null and
 * `applyIconSource` clears the image). The bar therefore starts against a
 * deliberately broken layout; only provisioning refuses to install one.
 */
export default function Bar(gdkmonitor: Gdk.Monitor, audio: AudioPanelBinding) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor
  const backdrop = readBarBackdrop(gdkmonitor.get_connector())

  const { layout, warnings } = sanitizeLayout(
    resolveLayout([], repoDefaultLayout),
    BAR_MANIFEST.capabilities,
  )
  for (const warning of warnings) console.warn(`[bar] layout: ${warning}`)
  const widgets = createWidgetRegistry({ audio, backdrop })
  const ctx: BarContext = createBarContext()

  const renderSection = (entries: readonly BarEntry[] | undefined) =>
    (entries ?? []).flatMap((entry) => {
      const spec = widgets.get(entry.id)
      // Belt-and-braces behind `sanitizeLayout` above: if the registry ever
      // lags the manifest, the entry still renders nothing, never a crash.
      return spec ? [<BarWidget spec={spec} ctx={ctx} />] : []
    })

  return (
    <window
      visible
      name="bar"
      class="bar"
      gdkmonitor={gdkmonitor}
      exclusivity={Astal.Exclusivity.EXCLUSIVE}
      anchor={TOP | LEFT | RIGHT}
    >
      <centerbox cssName="centerbox">
        <box $type="start">{renderSection(layout.sections.start)}</box>
        <box $type="center">{renderSection(layout.sections.center)}</box>
        <box $type="end" spacing={8}>{renderSection(layout.sections.end)}</box>
      </centerbox>
    </window>
  )
}
