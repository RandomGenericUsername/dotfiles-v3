import { Gtk } from "ags/gtk4"

// ---------------------------------------------------------------------------
// Shared group/selection helpers (A7, design.md §3.6).
//
// `select`/`applyGroup` drive the "exactly one member of a pill group is
// selected" state that both the recording controls and the settings page use;
// they are extracted (rather than left inline) so a second layout cannot
// invent a subtly different selected-state rule. `clearChildren` is the
// rebuild primitive every "render this page again" path uses.
// ---------------------------------------------------------------------------

export function select(button: Gtk.Button, group: Gtk.Button[]) {
  for (const item of group) item.remove_css_class("selected")
  button.add_css_class("selected")
}

export function applyGroup<T>(group: Array<{ value: T; button: Gtk.Button }>, value: T) {
  for (const entry of group) {
    if (entry.value === value) entry.button.add_css_class("selected")
    else entry.button.remove_css_class("selected")
  }
}

export function clearChildren(container: Gtk.Box) {
  let child = container.get_first_child()
  while (child !== null) {
    const next = child.get_next_sibling()
    container.remove(child)
    child = next
  }
}