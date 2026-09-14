import { Astal, Gdk, Gtk } from "ags/gtk4"
import app from "ags/gtk4/app"
import {
  CLIPBOARD_STATE_TOPIC,
  CLIPBOARD_UPDATE_TOPIC,
  domainEvents,
  type DomainPayload,
} from "../lib/event-bus"
import {
  itemFromPayload,
  itemKey,
  matchesQuery,
  type ClipboardItem,
  type ClipboardUpdatePayload,
} from "../lib/clipboard-types"
import { copyItem, deleteItem, readHistory, toggleFavorite } from "../lib/history"
import { ItemCard } from "./ItemCard"

const WINDOW_NAME = "hypr-pano-window"

function hideWindow(): void {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = false
}

/** The bottom layer-shell clipboard overlay (design D7). */
export function PanoWindow(gdkmonitor: Gdk.Monitor) {
  let items: ClipboardItem[] = []
  let query = ""
  let selected = 0
  let paused = false
  let jobId: string | null = null

  const search = new Gtk.SearchEntry({
    placeholder_text: "Search clipboard\u2026",
    hexpand: true,
  })
  search.add_css_class("pano-search")
  const incognito = new Gtk.Button({ label: "Incognito: off" })
  incognito.add_css_class("pano-incognito")

  const list = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 12,
    css_classes: ["pano-list"],
  })
  const empty = new Gtk.Label({ label: "No clipboard history yet" })
  empty.add_css_class("pano-empty")

  const scroll = new Gtk.ScrolledWindow({
    hexpand: true,
    vexpand: true,
    hscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    vscrollbar_policy: Gtk.PolicyType.NEVER,
  })
  scroll.set_child(list)

  function visibleItems(): ClipboardItem[] {
    return items.filter((item) => matchesQuery(item, query))
  }

  function refresh(): void {
    let child = list.get_first_child()
    while (child) {
      const next = child.get_next_sibling()
      list.remove(child)
      child = next
    }
    const shown = visibleItems()
    empty.set_visible(shown.length === 0)
    list.set_visible(shown.length > 0)
    if (shown.length === 0) return
    if (selected >= shown.length) selected = shown.length - 1
    if (selected < 0) selected = 0
    shown.forEach((item, index) => {
      const card = ItemCard(item, index + 1, select)
      if (index === selected) card.add_css_class("selected")
      list.append(card)
    })
  }

  function reload(): void {
    items = readHistory()
    selected = 0
    refresh()
  }

  function select(item: ClipboardItem): void {
    copyItem(item)
      .then(() => hideWindow())
      .catch((error: unknown) => console.error(`hypr-pano: copy failed: ${error}`))
  }

  function onKey(keyval: number, state: Gdk.ModifierType): boolean {
    const shown = visibleItems()
    if (keyval === Gdk.KEY_Escape) {
      hideWindow()
      return true
    }
    if (keyval === Gdk.KEY_Left) {
      selected = Math.max(0, selected - 1)
      refresh()
      return true
    }
    if (keyval === Gdk.KEY_Right) {
      selected = Math.min(shown.length - 1, selected + 1)
      refresh()
      return true
    }
    if (keyval === Gdk.KEY_Return || keyval === Gdk.KEY_KP_Enter) {
      const item = shown[selected]
      if (item) select(item)
      return true
    }
    if (keyval === Gdk.KEY_Delete) {
      const item = shown[selected]
      if (item) {
        deleteItem(item.hash)
        reload()
      }
      return true
    }
    if (keyval === Gdk.KEY_f && (state & Gdk.ModifierType.CONTROL_MASK) !== 0) {
      const item = shown[selected]
      if (item) {
        toggleFavorite(item.hash)
        reload()
      }
      return true
    }
    if ((state & Gdk.ModifierType.CONTROL_MASK) !== 0) {
      const index = keyval - Gdk.KEY_1
      if (index >= 0 && index <= 8 && index < shown.length) {
        select(shown[index])
        return true
      }
    }
    return false
  }

  // Live updates: the daemon pushes clipboard.update per capture and
  // clipboard.state on transitions (subscribe-before-read; see event-bus).
  domainEvents.subscribe(CLIPBOARD_UPDATE_TOPIC, (_topic: string, payload: DomainPayload) => {
    const item = itemFromPayload(payload as unknown as ClipboardUpdatePayload)
    const key = itemKey(item)
    items = [item, ...items.filter((existing) => itemKey(existing) !== key)]
    selected = 0
    refresh()
  })
  domainEvents.subscribe(CLIPBOARD_STATE_TOPIC, (_topic: string, payload: DomainPayload) => {
    paused = payload.state === "paused"
    jobId = typeof payload.job_id === "string" && payload.job_id.length > 0 ? payload.job_id : null
    incognito.set_label(paused ? "Incognito: on" : "Incognito: off")
  })
  domainEvents.onRestart(reload)

  incognito.connect("clicked", () => {
    if (jobId === null) return
    domainEvents.control(jobId, paused ? "resume" : "pause")
  })

  search.connect("search-changed", () => {
    query = search.get_text()
    selected = 0
    refresh()
  })

  return (
    <window
      visible={false}
      name={WINDOW_NAME}
      class="pano-window"
      gdkmonitor={gdkmonitor}
      anchor={
        Astal.WindowAnchor.BOTTOM | Astal.WindowAnchor.LEFT | Astal.WindowAnchor.RIGHT
      }
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      margin_bottom={24}
      margin_left={12}
      margin_right={12}
      $={(self) => {
        // Capture phase: navigation keys (arrows/Enter/Ctrl+digits/Delete)
        // must be seen BEFORE the focused SearchEntry consumes them.
        const keys = new Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", (_controller, keyval, _keycode, state) =>
          onKey(keyval, state),
        )
        self.add_controller(keys)
        // Hydrate from disk on every open so the overlay reflects captures
        // that happened while it was hidden, even with no hub signal.
        self.connect("map", () => {
          reload()
          // ON_DEMAND (like the capture tool and ICME) so the overlay never
          // grabs the keyboard from other AGS windows; present() asks the
          // compositor to focus the surface on show.
          self.present()
          search.grab_focus()
        })
      }}
    >
      <box
        orientation={Gtk.Orientation.VERTICAL}
        spacing={8}
        css_classes={["pano-panel"]}
        $={(self) => {
          const header = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
          header.append(search)
          header.append(incognito)
          self.append(header)
          self.append(scroll)
          self.append(empty)
        }}
      />
    </window>
  )
}
