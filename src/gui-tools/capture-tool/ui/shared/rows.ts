import { Gtk } from "ags/gtk4"

// ---------------------------------------------------------------------------
// Shared row builders for the capture settings page (A7, design.md §3.6).
//
// These were inline in `ui/CaptureWindow.tsx`. They are already generic and
// already callback-shaped, so extracting them BEFORE a second layout exists is
// what stops that layout from growing its own divergent row builders.
//
// Everything a row needs from its host view arrives through `RowContext`:
// `persistSettings` (write the draft immediately) and `setPathEditor` (let the
// window's key controller see the active inline editor). The builders never
// close over view state, so a layout that does not have a settings draft simply
// passes a no-op.
// ---------------------------------------------------------------------------

/** The inline path editor a `pathRow` exposes while it is open. */
export type PathEditor = { commit: () => void; cancel: () => void }

/** The host-view callbacks the row builders need. */
export interface RowContext {
  /** Persist the settings draft. Called after every committed mutation. */
  persistSettings: () => void
  /**
   * Publish the active inline path editor, or `null` when none is open.
   *
   * The window's key controller reads this so Enter/Escape reach the open
   * `Gtk.Entry` instead of being swallowed by the capture-phase handler.
   */
  setPathEditor: (editor: PathEditor | null) => void
}

export function settingsLabel(text: string, cssClass: string): Gtk.Label {
  const label = new Gtk.Label({ label: text, halign: Gtk.Align.START })
  label.add_css_class(cssClass)
  return label
}

export function settingsItem(name: string, desc: string | null, control: Gtk.Widget): Gtk.Box {
  const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 18 })
  row.add_css_class("settings-item")
  const left = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    spacing: 2,
    hexpand: true,
    valign: Gtk.Align.CENTER,
  })
  left.append(settingsLabel(name, "settings-name"))
  if (desc !== null) left.append(settingsLabel(desc, "settings-desc"))
  row.append(left)
  control.set_valign(Gtk.Align.CENTER)
  row.append(control)
  return row
}

export function settingsGroup(title: string, rows: Gtk.Widget[]): Gtk.Box {
  const box = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 })
  box.add_css_class("settings-group")
  box.append(settingsLabel(title, "settings-group-title"))
  for (const row of rows) box.append(row)
  return box
}

export function pathRow(
  name: string,
  desc: string,
  getValue: () => string,
  setValue: (value: string) => void,
  ctx: RowContext,
): Gtk.Box {
  const control = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
  const chip = new Gtk.Button({ label: getValue() })
  chip.add_css_class("path-chip")
  const entry = new Gtk.Entry({ text: getValue() })
  entry.add_css_class("path-entry")
  entry.set_width_chars(24)
  entry.set_visible(false)
  const commit = () => {
    if (!entry.get_visible()) return
    setValue(entry.get_text())
    chip.set_label(getValue())
    entry.set_visible(false)
    chip.set_visible(true)
    ctx.setPathEditor(null)
    ctx.persistSettings()
  }
  const cancel = () => {
    entry.set_text(getValue())
    entry.set_visible(false)
    chip.set_visible(true)
    ctx.setPathEditor(null)
  }
  chip.connect("clicked", () => {
    entry.set_text(getValue())
    chip.set_visible(false)
    entry.set_visible(true)
    entry.grab_focus()
    entry.select_region(0, -1)
    ctx.setPathEditor({ commit, cancel })
  })
  entry.connect("activate", commit)
  const focus = new Gtk.EventControllerFocus()
  focus.connect("leave", commit)
  entry.add_controller(focus)
  control.append(chip)
  control.append(entry)
  return settingsItem(name, desc, control)
}

export function toggleRow(
  name: string,
  desc: string | null,
  getValue: () => boolean,
  setValue: (value: boolean) => void,
  ctx: RowContext,
): Gtk.Box {
  // Gtk.Switch, not a hand-rolled track+knob: a GtkBox ignores a child's
  // main-axis alignment, so the old knob's halign START/END never moved it and
  // both states looked identical (you could not tell whether the cursor
  // toggle was on). The native switch owns the knob, its position and its
  // transition; the palette styling lives in style.css.
  const control = new Gtk.Switch()
  control.add_css_class("palette-switch")
  control.set_active(getValue())
  control.set_halign(Gtk.Align.END)
  control.set_valign(Gtk.Align.CENTER)
  control.connect("state-set", (_self, state: boolean) => {
    setValue(state)
    ctx.persistSettings()
    return false // let the switch animate to the new state
  })
  return settingsItem(name, desc, control)
}

export function pillRow<T>(
  name: string,
  options: Array<{ label: string; value: T }>,
  getValue: () => T,
  setValue: (value: T) => void,
  ctx: RowContext,
): Gtk.Box {
  const segments = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 })
  segments.add_css_class("segments")
  const buttons: Array<{ value: T; button: Gtk.Button }> = []
  for (const option of options) {
    const button = new Gtk.Button({ label: option.label })
    button.add_css_class("segment")
    button.add_css_class("compact")
    if (option.value === getValue()) button.add_css_class("selected")
    button.connect("clicked", () => {
      setValue(option.value)
      ctx.persistSettings()
      for (const item of buttons) {
        if (item.value === option.value) item.button.add_css_class("selected")
        else item.button.remove_css_class("selected")
      }
    })
    buttons.push({ value: option.value, button })
    segments.append(button)
  }
  return settingsItem(name, null, segments)
}