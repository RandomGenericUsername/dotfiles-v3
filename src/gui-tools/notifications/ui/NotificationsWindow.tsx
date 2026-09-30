import { Astal, Gdk, Gtk } from "ags/gtk4"
import Notifd from "gi://AstalNotifd?version=0.1"
import Pango from "gi://Pango?version=1.0"
import GLib from "gi://GLib?version=2.0"
import app from "ags/gtk4/app"
import { refreshPaletteCss } from "../lib/theme"
import { subscribeWallpaperEvents, type WallpaperPayload, type WallpaperEventSource } from "../lib/wallpaper-events"
import { subscribeSpeedTestEvents, type SpeedTestPayload, type SpeedTestEventSource } from "../lib/speedtest-events"
import { resolveIcon } from "../lib/icon-registry"

// AstalNotifd.Urgency wire values (GIR-verified against
// /usr/share/gir-1.0/AstalNotifd-0.1.gir): LOW=0, NORMAL=1, CRITICAL=2.
// Compared numerically so a namespace-enum rename can never break the
// urgency mapping at runtime.
const URGENCY_CRITICAL = 2

// Oldest-overflow discipline (mirrors the old dunst `notification_limit`).
const MAX_VISIBLE = 5

// Fixed card width (the mockup `.toast-stack` measure). A fixed request makes
// long bodies wrap instead of letting the card grow, and guarantees no
// notification can ever expand past a toast-sized box.
const CARD_WIDTH = 380

// Icon size inside the 56px tile.
const TILE_ICON = 24

// Auto-expiry. AstalNotifd does not reliably resolve notifications on their
// own (verified live: a capture toast sent with an 8s timeout stayed on screen
// until dismissed), so the stack owns the timer. Critical cards persist until
// dismissed — the mockup's "Capture failed" card. A sender's 0 ("never") or
// -1 ("server default") is treated as the default so nothing sticks forever.
const DEFAULT_TIMEOUT_MS = 8000
const WALLPAPER_STEPS = [
  "Wallpaper is on screen",
  "Color palette generated",
  "Effects and icons processed",
  "Desktop consumers updated",
]

// The speed test's four steps, in the order `speedtest-cli` actually performs
// them (latency, then download, then upload) — not invented progress. The bar
// pulses while they run because the CLI returns ONE JSON blob at the end and
// the producer has no intermediate fraction to publish; a determinate
// percentage here would be a number the system made up.
const SPEEDTEST_STEPS = [
  "Test scheduled",
  "Latency measured",
  "Download measured",
  "Upload measured",
]

// Auto-dismiss delay after a SUCCESSFUL run (the shipped wallpaper completion
// delay, so the two progress cards behave alike). A failure is sticky.
const SPEEDTEST_COMPLETE_MS = 5000

// Pulse period while a run is in flight. Matches the wallpaper card's 100ms.
const SPEEDTEST_PULSE_MS = 100

// One-line failure reasons are written for the card's ~44 wrapped characters.
const SPEEDTEST_REASON_MAX_CHARS = 44
const SPEEDTEST_NETWORK_MAX_CHARS = 30

const WINDOW_NAME = "notifications-window"

interface CardEntry {
  id: number
  notification: InstanceType<typeof Notifd.Notification>
  widget: Gtk.Widget
}

function hideWindow(): void {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = false
}

/**
 * Map the stack window before a card lands. An empty layer-shell surface stays
 * mapped and the compositor keeps re-presenting its LAST PAINTED BUFFER, so a
 * card removed from the box would otherwise stay on screen forever (verified
 * live: removeCard ran, the widget was gone, the pixels were not).
 */
function showWindow(): void {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = true
}

/** A finite payload number, or null — never a coerced NaN on screen. */
function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function mbpsLabel(value: number | undefined): string {
  return value === undefined ? "—" : `${value.toFixed(1)} Mbps`
}

function msLabel(value: number | undefined): string {
  return value === undefined ? "—" : `${Math.round(value)} ms`
}

/** Absolute on-disk image for the notification, or null (fallback tile). */
function notificationImagePath(
  notification: InstanceType<typeof Notifd.Notification>,
): string | null {
  const candidates: Array<string | null> = [
    notification.get_image(),
    notification.get_app_icon(),
  ]
  for (const candidate of candidates) {
    if (candidate === null || candidate.length === 0) continue
    // Only absolute paths are usable as files; icon NAMES (e.g. from plain
    // `notify-send` traffic) fall through to the letter tile.
    if (!candidate.startsWith("/")) continue
    try {
      if (GLib.file_test(candidate, GLib.FileTest.EXISTS)) return candidate
    } catch {
      continue
    }
  }
  return null
}

function tileContent(
  notification: InstanceType<typeof Notifd.Notification>,
  critical: boolean,
): Gtk.Widget {
  const path = notificationImagePath(notification)
  if (path !== null) {
    try {
      // Gtk.Image + pixel_size (bar precedent): forces the SVG to rasterize at
      // exactly TILE_ICON px. Gtk.Picture + set_size_request is NOT equivalent
      // — the request is only a minimum, so a 1024px icon (the capture-tool
      // set) measured at natural size and blew the card up to full screen.
      const image = Gtk.Image.new_from_file(path)
      image.set_pixel_size(TILE_ICON)
      image.set_halign(Gtk.Align.CENTER)
      image.set_valign(Gtk.Align.CENTER)
      return image
    } catch (error) {
      console.error(`notifications: cannot load image ${path}: ${error}`)
    }
  }
  // Fallback tile: the app's initial (or "!" for critical) so icon-less
  // traffic (e.g. toggle-touchpad notify-send) still renders a tidy card.
  const appName = notification.get_app_name() ?? ""
  const glyph = critical ? "!" : (appName.charAt(0).toUpperCase() || "?")
  const label = new Gtk.Label({ label: glyph })
  label.add_css_class("notif-fallback")
  label.set_halign(Gtk.Align.CENTER)
  label.set_valign(Gtk.Align.CENTER)
  return label
}

/** One mockup `.toast` card for a daemon notification. */
function NotificationCard(
  notification: InstanceType<typeof Notifd.Notification>,
  onDismiss: () => void,
): Gtk.Box {
  const critical = notification.get_urgency() === URGENCY_CRITICAL

  // CenterBox, not Box: a Gtk.Box packs a non-expanding child at the START of
  // its main axis, so the 24px glyph sat at the TOP of the 56px tile. The
  // box's own valign/align cannot fix that (measured: tile 58x58, valign
  // CENTER, glyph still top-packed) — CenterBox centers its centre widget by
  // construction, which is what the mockup's flex centring does.
  const tile = new Gtk.CenterBox()
  tile.add_css_class("notif-tile")
  if (critical) tile.add_css_class("critical")
  tile.set_halign(Gtk.Align.CENTER)
  tile.set_valign(Gtk.Align.CENTER)
  tile.set_center_widget(tileContent(notification, critical))

  const title = new Gtk.Label({ label: notification.get_summary() ?? "" })
  title.add_css_class("notif-title")
  title.set_halign(Gtk.Align.START)
  title.set_wrap(true)
  // Bound the natural (unwrapped) width so the window sizes to the intended
  // card measure instead of the longest path's single-line width.
  title.set_max_width_chars(38)

  const body = new Gtk.Label({ label: notification.get_body() ?? "" })
  body.add_css_class("notif-body")
  body.set_halign(Gtk.Align.START)
  body.set_wrap(true)
  body.set_max_width_chars(44)
  // Paths must break mid-token (mockup `word-break: break-all`).
  body.set_wrap_mode(Pango.WrapMode.WORD_CHAR)

  const text = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    spacing: 3,
    hexpand: true,
  })
  text.append(title)
  if ((notification.get_body() ?? "").length > 0) text.append(body)

  const actions = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 7,
  })
  actions.add_css_class("notif-actions")
  let hasActions = false
  try {
    for (const action of notification.get_actions() ?? []) {
      hasActions = true
      const chip = new Gtk.Button({ label: action.get_label() ?? action.get_id() })
      chip.add_css_class("notif-chip")
      const current = action
      chip.connect("clicked", () => {
        // Route the invocation back to the emitting client (the capture
        // backend listens on D-Bus for ActionInvoked and executes
        // copy/open/reveal/details). Do NOT dismiss in the same tick: our
        // daemon emits NotificationClosed BEFORE ActionInvoked, and clearing
        // the card immediately raced the action delivery. The daemon closes
        // the notification for these actions, which removes the card through
        // `resolved`; the timeout is only a fallback for a daemon that keeps
        // it open.
        try {
          current.invoke()
        } catch (error) {
          console.error(`notifications: action invoke failed: ${error}`)
        }
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 600, () => {
          onDismiss()
          return GLib.SOURCE_REMOVE
        })
      })
      actions.append(chip)
    }
  } catch (error) {
    console.error(`notifications: cannot read actions: ${error}`)
  }
  if (hasActions) text.append(actions)

  const card = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 13,
  })
  card.add_css_class("notif-card")
  if (critical) card.add_css_class("critical")
  card.set_size_request(CARD_WIDTH, -1)
  card.append(tile)
  card.append(text)

  // Click-to-dismiss is attached to the INFORMATIONAL parts (tile, title,
  // body) and deliberately NOT to the card as a whole. A card-wide
  // GestureClick fires on PRESS, so pressing an action chip closed the
  // notification before the chip's `clicked` (which lands on release) could
  // invoke it — the notification was gone, the invoke was a no-op, and the
  // chip did nothing.
  for (const region of [tile, title, body]) {
    const click = new Gtk.GestureClick()
    click.connect("pressed", () => onDismiss())
    region.add_controller(click)
  }

  return card
}

/** Top-right freedesktop notification stack (the session daemon). */
export function NotificationsWindow(gdkmonitor: Gdk.Monitor) {
  const notifd = Notifd.get_default()
  let stack: Gtk.Box | null = null
  let cards: CardEntry[] = []
  let wallpaperCard: Gtk.Box | null = null
  let wallpaperHash: string | null = null
  let wallpaperTerminal = false
  let wallpaperProgress: Gtk.ProgressBar | null = null
  let wallpaperTitle: Gtk.Label | null = null
  let wallpaperDetail: Gtk.Label | null = null
  let wallpaperFooter: Gtk.Label | null = null
  let wallpaperIcon: Gtk.Image | null = null
  let wallpaperIconTile: Gtk.CenterBox | null = null
  let wallpaperStepRows: Array<{
    row: Gtk.Box
    marker: Gtk.Stack
    markerGlyph: Gtk.Label
    markerIcon: Gtk.Image
  }> = []
  let wallpaperPulseSource: number | null = null
  let wallpaperExpirySource: number | null = null
  /** id -> pending GLib timeout source for auto-expiry. */
  const timers = new Map<number, number>()

  function hideIfEmpty(): void {
    if (cards.length === 0 && wallpaperCard === null && speedtestCard === null) hideWindow()
  }

  function stopWallpaperTimers(): void {
    if (wallpaperPulseSource !== null) GLib.source_remove(wallpaperPulseSource)
    if (wallpaperExpirySource !== null) GLib.source_remove(wallpaperExpirySource)
    wallpaperPulseSource = null
    wallpaperExpirySource = null
  }

  function dismissWallpaperCard(): void {
    stopWallpaperTimers()
    if (stack !== null && wallpaperCard !== null) stack.remove(wallpaperCard)
    wallpaperCard = null
    wallpaperHash = null
    wallpaperTerminal = false
    wallpaperProgress = null
    wallpaperTitle = null
    wallpaperDetail = null
    wallpaperFooter = null
    wallpaperIcon = null
    wallpaperIconTile = null
    wallpaperStepRows = []
    hideIfEmpty()
  }

  function wallpaperUpdate(payload: WallpaperPayload, source: WallpaperEventSource): void {
    if (payload["trigger"] !== "set") return
    const hash = typeof payload["wallpaper_hash"] === "string" ? payload["wallpaper_hash"] : ""
    const phase = typeof payload["state"] === "string" ? payload["state"] : ""
    const stage = typeof payload["stage"] === "string" ? payload["stage"] : ""

    // Startup hydration restores only an operation that is still running.
    // Live terminal events update a card only when it belongs to that run.
    if (source === "startup-state" && phase !== "applying" && phase !== "visible") return
    if (phase === "applying") {
      if (wallpaperCard !== null && wallpaperHash !== hash) {
        if (!wallpaperTerminal) return
        dismissWallpaperCard()
      }
      if (wallpaperCard === null) createWallpaperCard(hash)
      setWallpaperStatus("Updating wallpaper", "Setting the new wallpaper…", stage, true)
      return
    }
    if (wallpaperCard === null || wallpaperHash !== hash) return
    if (phase === "visible") {
      setWallpaperStatus("Updating wallpaper", statusForStage(stage), stage, true)
    } else if (phase === "done") {
      wallpaperTerminal = true
      try { refreshPaletteCss() } catch (error) {
        console.error(`notifications: palette CSS refresh failed: ${error}`)
      }
      refreshWallpaperIcon()
      const failures = Array.isArray(payload["reload_failures"])
        ? payload["reload_failures"].filter((item): item is string => typeof item === "string")
        : []
      if (failures.length > 0) {
        setWallpaperStatus(
          "Wallpaper updated with issues",
          `Could not update: ${failures.join(", ")}`,
          "reconciling_consumers",
          false,
          false,
          true,
        )
      } else {
        setWallpaperStatus("Wallpaper updated", "All visual settings are up to date.", "finished", false, true)
      }
      wallpaperExpirySource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        wallpaperExpirySource = null
        dismissWallpaperCard()
        return GLib.SOURCE_REMOVE
      })
    } else if (phase === "error") {
      wallpaperTerminal = true
      setWallpaperStatus("Wallpaper update stopped", `The update stopped while ${failureForStage(stage)}.`, stage, false, false, true)
    }
  }

  function createWallpaperCard(hash: string): void {
    if (stack === null) return
    showWindow()
    wallpaperHash = hash
    const card = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 9 })
    card.add_css_class("notif-card")
    card.add_css_class("wallpaper-progress-card")
    card.set_size_request(CARD_WIDTH, -1)
    const heading = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 10 })
    const tile = new Gtk.CenterBox()
    tile.add_css_class("wallpaper-progress-icon")
    tile.set_size_request(44, 44)
    const icon = new Gtk.Image()
    icon.set_pixel_size(25)
    const iconPath = resolveIcon("wallpaper-progress", "picture")
    tile.set_center_widget(icon)
    if (iconPath === null) {
      const fallback = new Gtk.Label({ label: "▧" })
      fallback.add_css_class("notif-fallback")
      tile.set_center_widget(fallback)
    }
    if (iconPath !== null) icon.set_from_file(iconPath)
    wallpaperIcon = icon
    wallpaperIconTile = tile
    const copy = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 3, hexpand: true })
    const title = new Gtk.Label({ label: "Updating wallpaper", xalign: 0 })
    title.add_css_class("notif-title")
    const detail = new Gtk.Label({ label: "", xalign: 0, wrap: true })
    detail.add_css_class("notif-body")
    copy.append(title)
    copy.append(detail)
    const close = new Gtk.Button({ label: "×" })
    close.add_css_class("wallpaper-progress-close")
    close.connect("clicked", dismissWallpaperCard)
    heading.append(tile)
    heading.append(copy)
    heading.append(close)
    const progress = new Gtk.ProgressBar()
    progress.add_css_class("wallpaper-progress-bar")
    progress.set_show_text(false)
    card.append(heading)
    card.append(progress)
    const stepList = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 7 })
    stepList.add_css_class("wallpaper-progress-steps")
    for (const stepText of WALLPAPER_STEPS) {
      const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
      row.add_css_class("wallpaper-progress-step")
      const marker = new Gtk.Stack()
      marker.add_css_class("wallpaper-progress-marker")
      const markerGlyph = new Gtk.Label({ label: "○" })
      const markerIcon = new Gtk.Image()
      markerIcon.set_pixel_size(15)
      const checkCirclePath = resolveIcon("wallpaper-progress", "check-circle")
      if (checkCirclePath !== null) markerIcon.set_from_file(checkCirclePath)
      marker.add_named(markerGlyph, "glyph")
      marker.add_named(markerIcon, "check")
      marker.set_visible_child_name("glyph")
      const label = new Gtk.Label({ label: stepText, xalign: 0, hexpand: true })
      label.add_css_class("wallpaper-progress-step-label")
      row.append(marker)
      row.append(label)
      stepList.append(row)
      wallpaperStepRows.push({ row, marker, markerGlyph, markerIcon })
    }
    card.append(stepList)
    const footer = new Gtk.Label({ label: "The wallpaper is visible while the remaining steps finish.", xalign: 0 })
    footer.add_css_class("wallpaper-progress-footer")
    card.append(footer)
    wallpaperFooter = footer
    stack.prepend(card)
    wallpaperCard = card
    wallpaperProgress = progress
    wallpaperTitle = title
    wallpaperDetail = detail
  }

  function setWallpaperStatus(
    titleText: string,
    detailText: string,
    stage: string,
    busy: boolean,
    complete = false,
    failed = false,
  ): void {
    if (wallpaperCard === null || wallpaperProgress === null) return
    wallpaperTitle?.set_label(titleText)
    wallpaperDetail?.set_label(detailText)
    wallpaperFooter?.set_label(complete
      ? "Finished just now."
      : failed
        ? "You can retry by setting the wallpaper again."
        : "This can take a little longer while desktop apps update.")
    const activeIndex = stageIndex(stage)
    wallpaperStepRows.forEach(({ row, marker, markerGlyph }, index) => {
      row.remove_css_class("done")
      row.remove_css_class("active")
      row.remove_css_class("failed")
      if (complete || index < activeIndex) {
        row.add_css_class("done")
        marker.set_visible_child_name("check")
      } else if (failed && index === activeIndex) {
        row.add_css_class("failed")
        marker.set_visible_child_name("glyph")
        markerGlyph.set_label("!")
      } else if (!failed && index === activeIndex) {
        row.add_css_class("active")
        marker.set_visible_child_name("glyph")
        markerGlyph.set_label("·")
      } else {
        marker.set_visible_child_name("glyph")
        markerGlyph.set_label("○")
      }
    })
    stopWallpaperTimers()
    if (complete) wallpaperProgress.set_fraction(1)
    else if (failed) wallpaperProgress.set_fraction(stageIndex(stage) / WALLPAPER_STEPS.length)
    else if (busy) {
      wallpaperProgress.set_fraction(0)
      wallpaperPulseSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
        wallpaperProgress?.pulse()
        return GLib.SOURCE_CONTINUE
      })
    } else wallpaperProgress.set_fraction(0)
  }

  function statusForStage(stage: string): string {
    switch (stage) {
      case "generating_palette": return "Wallpaper is on screen. Generating the color palette…"
      case "palette_generated": return "Color palette generated. Preparing effects and icons…"
      case "preparing_appearance_assets": return "Color palette generated. Preparing effects and icons…"
      case "appearance_assets_ready": return "Appearance assets prepared. Updating desktop apps…"
      case "reconciling_consumers": return "Appearance assets prepared. Updating desktop apps…"
      case "finished": return "All visual settings are up to date."
      default: return "Setting the new wallpaper…"
    }
  }

  function stageIndex(stage: string): number {
    switch (stage) {
      case "setting_wallpaper": return 0
      case "generating_palette": return 1
      case "palette_generated": return 2
      case "preparing_appearance_assets": return 2
      case "appearance_assets_ready": return 3
      case "reconciling_consumers": return 3
      case "finished": return WALLPAPER_STEPS.length
      default: return 0
    }
  }

  function failureForStage(stage: string): string {
    switch (stage) {
      case "setting_wallpaper": return "setting the wallpaper"
      case "generating_palette": return "generating the color palette"
      case "palette_generated":
      case "preparing_appearance_assets": return "preparing effects and icons"
      case "appearance_assets_ready":
      case "reconciling_consumers": return "updating desktop apps"
      default: return "updating the wallpaper appearance"
    }
  }

  function refreshWallpaperIcon(): void {
    const path = resolveIcon("wallpaper-progress", "picture")
    if (path !== null && wallpaperIcon !== null) {
      wallpaperIcon.set_from_file(path)
      wallpaperIconTile?.set_center_widget(wallpaperIcon)
    }
    const checkCirclePath = resolveIcon("wallpaper-progress", "check-circle")
    if (checkCirclePath !== null) {
      for (const { markerIcon, marker } of wallpaperStepRows) {
        markerIcon.set_from_file(checkCirclePath)
        marker.set_visible_child_name("check")
      }
    }
  }

  // ── Speed test ─────────────────────────────────────────────────────────
  //
  // The wallpaper model, copied: ONE card per run, mutated in place across the
  // run's lifetime. It is never a daemon notification — no `Notify`, no
  // `replaces_id` — because a run is a single logical operation and four
  // separate toasts would each need their own dismissal.
  //
  // COLLISION WITH THE WALLPAPER CARD: the two are independent and may be on
  // screen at once (newest `prepend`ed, on top). Neither dismisses the other:
  // a speed test says nothing about the wallpaper's lifecycle, and dropping the
  // wallpaper card because a measurement started would be a lie about what
  // happened. A *previous speed-test* card IS superseded by a new run, though —
  // its steps and result are about a run that no longer exists.
  let speedtestCard: Gtk.Box | null = null
  let speedtestTerminal = false
  let speedtestProgress: Gtk.ProgressBar | null = null
  let speedtestTitle: Gtk.Label | null = null
  let speedtestDetail: Gtk.Label | null = null
  let speedtestFooter: Gtk.Label | null = null
  let speedtestTile: Gtk.CenterBox | null = null
  let speedtestGrid: Gtk.Box | null = null
  let speedtestCells: Array<{ box: Gtk.Box; value: Gtk.Label }> = []
  let speedtestStepRows: Array<{
    row: Gtk.Box
    marker: Gtk.Stack
    markerGlyph: Gtk.Label
    markerIcon: Gtk.Image
  }> = []
  let speedtestPulseSource: number | null = null
  let speedtestExpirySource: number | null = null

  function stopSpeedtestTimers(): void {
    if (speedtestPulseSource !== null) GLib.source_remove(speedtestPulseSource)
    if (speedtestExpirySource !== null) GLib.source_remove(speedtestExpirySource)
    speedtestPulseSource = null
    speedtestExpirySource = null
  }

  function dismissSpeedtestCard(): void {
    stopSpeedtestTimers()
    if (stack !== null && speedtestCard !== null) stack.remove(speedtestCard)
    speedtestCard = null
    speedtestTerminal = false
    speedtestProgress = null
    speedtestTitle = null
    speedtestDetail = null
    speedtestFooter = null
    speedtestTile = null
    speedtestGrid = null
    speedtestCells = []
    speedtestStepRows = []
    hideIfEmpty()
  }

  function speedtestUpdate(payload: SpeedTestPayload, source: SpeedTestEventSource): void {
    const state = typeof payload["state"] === "string" ? payload["state"] : ""
    // Hydration restores only a run that is still going. A terminal payload read
    // back at startup is a run this process never saw start, so there is no
    // card to settle and no baseline to attribute its measurements to.
    if (source === "startup-state" && state !== "starting") return
    if (state === "starting") {
      // A new run supersedes any card we are still holding for an older one.
      if (speedtestCard !== null) dismissSpeedtestCard()
      createSpeedtestCard()
      setSpeedtestStatus("starting")
      return
    }
    // A terminal event for a run we are not tracking is ignored, never
    // rendered as an orphan card: the notifications app may have started after
    // the run began, or the card may already have been dismissed by the user.
    if (speedtestCard === null) return
    if (state === "done") {
      speedtestTerminal = true
      setSpeedtestStatus("done", {
        down_mbps: asNumber(payload["down_mbps"]),
        up_mbps: asNumber(payload["up_mbps"]),
        latency_ms: asNumber(payload["latency_ms"]),
        trigger: typeof payload["trigger"] === "string" ? payload["trigger"] : "",
      })
      // Success is informational and already visible in the panel, so the card
      // clears itself on the wallpaper card's completion delay.
      speedtestExpirySource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SPEEDTEST_COMPLETE_MS, () => {
        speedtestExpirySource = null
        dismissSpeedtestCard()
        return GLib.SOURCE_REMOVE
      })
    } else if (state === "error") {
      speedtestTerminal = true
      setSpeedtestStatus("error", {
        reason: typeof payload["reason"] === "string" ? payload["reason"] : "Speed test failed.",
        trigger: typeof payload["trigger"] === "string" ? payload["trigger"] : "",
      })
    }
  }

  function createSpeedtestCard(): void {
    if (stack === null) return
    showWindow()
    const card = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 9 })
    card.add_css_class("notif-card")
    card.add_css_class("speedtest-progress-card")
    card.set_size_request(CARD_WIDTH, -1)

    const heading = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 10 })
    const tile = new Gtk.CenterBox()
    tile.add_css_class("speedtest-progress-tile")
    tile.add_css_class("busy")
    tile.set_size_request(44, 44)
    // CenterBox centers its centre widget by construction; a plain Box would
    // pack a non-expanding child at the START of its main axis and top-align the
    // glyph (same reason the wallpaper card uses CenterBox).
    tile.set_center_widget(new Gtk.Label({ label: "⇅" }))
    speedtestTile = tile
    const copy = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 3, hexpand: true })
    const title = new Gtk.Label({ label: "Speed test running", xalign: 0 })
    title.add_css_class("notif-title")
    const detail = new Gtk.Label({ label: "Measuring your connection…", xalign: 0, wrap: true })
    detail.add_css_class("notif-body")
    // Gtk.Label reports its FULL unwrapped text as natural width, so without
    // maxWidthChars a long reason (a spawn failure can be a whole sentence)
    // would grow the card past CARD_WIDTH. Wrap, never ellipsize: the reason
    // carries the only information the card has.
    detail.set_max_width_chars(SPEEDTEST_REASON_MAX_CHARS)
    copy.append(title)
    copy.append(detail)
    const close = new Gtk.Button({ label: "×" })
    close.add_css_class("wallpaper-progress-close")
    close.connect("clicked", dismissSpeedtestCard)
    heading.append(tile)
    heading.append(copy)
    heading.append(close)

    const progress = new Gtk.ProgressBar()
    progress.add_css_class("speedtest-progress-bar")
    // No percentage, ever: the CLI hands back one JSON blob when the run ends,
    // so any fraction shown mid-run would be fabricated. show_text(false) also
    // keeps Gtk from printing its own 0% while the bar pulses.
    progress.set_show_text(false)
    card.append(heading)
    card.append(progress)

    // The three result cells, hidden until a run succeeds. Download / Upload /
    // Ping, matching the panel's own row split so the two read identically.
    const grid = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
    grid.add_css_class("speedtest-progress-grid")
    for (const [key, highlight] of [["Download", true], ["Upload", true], ["Ping", false]] as const) {
      const cell = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 3, hexpand: true })
      cell.add_css_class("speedtest-progress-cell")
      if (highlight) cell.add_css_class("highlight")
      const keyLabel = new Gtk.Label({ label: key, xalign: 0 })
      keyLabel.add_css_class("speedtest-progress-cell-key")
      const value = new Gtk.Label({ label: "—", xalign: 0 })
      value.add_css_class("speedtest-progress-cell-value")
      // Three cells across a 380px card is ~118px each; the value line carries
      // a number and a unit, so it wraps rather than forcing the row wider.
      value.set_max_width_chars(9)
      cell.append(keyLabel)
      cell.append(value)
      grid.append(cell)
      speedtestCells.push({ box: cell, value })
    }
    grid.set_visible(false)
    speedtestGrid = grid
    card.append(grid)

    // The four-step checklist, built exactly as the wallpaper card builds its
    // own (a Gtk.Stack per marker so the done state can swap a glyph for the
    // palette-rendered check icon).
    const stepList = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 7 })
    stepList.add_css_class("speedtest-progress-steps")
    for (const stepText of SPEEDTEST_STEPS) {
      const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 })
      row.add_css_class("speedtest-progress-step")
      const marker = new Gtk.Stack()
      marker.add_css_class("speedtest-progress-marker")
      const markerGlyph = new Gtk.Label({ label: "○" })
      const markerIcon = new Gtk.Image()
      markerIcon.set_pixel_size(15)
      const checkCirclePath = resolveIcon("wallpaper-progress", "check-circle")
      if (checkCirclePath !== null) markerIcon.set_from_file(checkCirclePath)
      marker.add_named(markerGlyph, "glyph")
      marker.add_named(markerIcon, "check")
      marker.set_visible_child_name("glyph")
      const label = new Gtk.Label({ label: stepText, xalign: 0, hexpand: true })
      label.add_css_class("speedtest-progress-step-label")
      row.append(marker)
      row.append(label)
      stepList.append(row)
      speedtestStepRows.push({ row, marker, markerGlyph, markerIcon })
    }
    card.append(stepList)

    const footer = new Gtk.Label({ label: "Runs in the background.", xalign: 0 })
    footer.add_css_class("speedtest-progress-footer")
    card.append(footer)

    stack.prepend(card)
    speedtestCard = card
    speedtestProgress = progress
    speedtestTitle = title
    speedtestDetail = detail
    speedtestFooter = footer
  }

  /**
   * Settle the card into `starting` / `done` / `error`.
   *
   * `activeStep` is the step the run is ON, not a fraction: the producer
   * publishes no intermediate progress, so the checklist's active row is the
   * honest "where are we" signal, and everything before it is genuinely done.
   */
  function setSpeedtestStatus(
    state: "starting" | "done" | "error",
    terminal?: {
      down_mbps?: number
      up_mbps?: number
      latency_ms?: number
      reason?: string
      trigger: string
    },
  ): void {
    if (speedtestCard === null || speedtestProgress === null) return
    stopSpeedtestTimers()
    // A terminal card is never BUSY: the tile keeps its result/failure tint and
    // the bar stops pulsing even though the failure card is sticky.
    speedtestTile?.remove_css_class("busy")

    if (state === "starting") {
      speedtestTerminal = false
      speedtestTitle?.set_label("Speed test running")
      speedtestDetail?.set_label(`${triggerPhrase(terminal?.trigger)} · measuring your connection…`)
      speedtestFooter?.set_label("Runs in the background; the result is in the Wi-Fi panel.")
      setSpeedtestSteps(1, false)
      speedtestProgress.set_fraction(0)
      speedtestPulseSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SPEEDTEST_PULSE_MS, () => {
        speedtestProgress?.pulse()
        return GLib.SOURCE_CONTINUE
      })
      return
    }

    if (state === "done") {
      speedtestTitle?.set_label("Speed test complete")
      speedtestDetail?.set_label(
        `${triggerPhrase(terminal?.trigger)} · also shown in the Wi-Fi panel`,
      )
      speedtestFooter?.set_label("Finished just now.")
      setSpeedtestSteps(SPEEDTEST_STEPS.length, false)
      const [down, up, ping] = speedtestCells
      if (down !== undefined) down.value.set_label(mbpsLabel(terminal?.down_mbps))
      if (up !== undefined) up.value.set_label(mbpsLabel(terminal?.up_mbps))
      if (ping !== undefined) ping.value.set_label(msLabel(terminal?.latency_ms))
      speedtestGrid?.set_visible(true)
      speedtestProgress.set_fraction(1)
      return
    }

    // error: sticky, cautious, and it names the step it stopped at.
    speedtestCard.add_css_class("critical")
    speedtestTile?.add_css_class("failed")
    speedtestTitle?.set_label("Speed test failed")
    speedtestDetail?.set_label(terminal?.reason ?? "Speed test failed.")
    speedtestFooter?.set_label("It will retry on the next interval.")
    // The failure is attributed to the step the run was on. We cannot know
    // WHICH phase the CLI died in — it reports one blob at the end — so the
    // second step ("Latency measured") is the truthful claim: the measurement
    // never completed. Saying "download failed" would be a guess.
    setSpeedtestSteps(1, true)
    // Deliberately NOT fraction(1): the run did not finish. Left at 0 with the
    // bar no longer pulsing, so the card reads "stopped", not "done".
    speedtestProgress.set_fraction(0)
  }

  /** Mark steps `<activeStep` done, `activeStep` active-or-failed, the rest pending. */
  function setSpeedtestSteps(activeStep: number, failed: boolean): void {
    speedtestStepRows.forEach(({ row, marker, markerGlyph }, index) => {
      row.remove_css_class("done")
      row.remove_css_class("active")
      row.remove_css_class("failed")
      if (index < activeStep) {
        row.add_css_class("done")
        marker.set_visible_child_name("check")
      } else if (index === activeStep) {
        row.add_css_class(failed ? "failed" : "active")
        marker.set_visible_child_name("glyph")
        markerGlyph.set_label(failed ? "!" : "·")
      } else {
        marker.set_visible_child_name("glyph")
        markerGlyph.set_label("○")
      }
    })
  }

  function triggerPhrase(trigger: string): string {
    switch (trigger) {
      case "manual": return "Started by you"
      case "connect": return "Run after connecting"
      default: return "Scheduled run"
    }
  }


  function removeCard(id: number): void {
    const index = cards.findIndex((entry) => entry.id === id)
    if (index === -1 || stack === null) return
    clearExpiry(id)
    const [entry] = cards.splice(index, 1)
    if (entry !== undefined) stack.remove(entry.widget)
    // Unmap once the last card leaves: an empty surface would keep showing the
    // previous frame (see showWindow).
    hideIfEmpty()
  }

  /**
   * Remove a card and tell the daemon. The local removal is AUTHORITATIVE:
   * `Notification.dismiss()` does not reliably emit `resolved` (verified live
   * — a card the daemon had already been told to dismiss stayed on screen), so
   * every user/expiry path clears the UI itself and treats `resolved` as a
   * bonus path for daemon-initiated closes.
   */
  function dismissCard(id: number): void {
    const index = cards.findIndex((entry) => entry.id === id)
    if (index === -1) return
    const entry = cards[index]
    removeCard(id)
    try {
      entry?.notification.dismiss()
    } catch (error) {
      console.error(`notifications: dismiss failed: ${error}`)
    }
  }

  /** Cancel a card's pending auto-expiry (called on every removal path). */
  function clearExpiry(id: number): void {
    const source = timers.get(id)
    if (source !== undefined) {
      GLib.source_remove(source)
      timers.delete(id)
    }
  }

  /**
   * Auto-dismiss a normal-urgency card after its timeout. Critical cards are
   * skipped entirely (sticky until the user dismisses them).
   */
  function scheduleExpiry(entry: CardEntry): void {
    if (entry.notification.get_urgency() === URGENCY_CRITICAL) return
    let ms = DEFAULT_TIMEOUT_MS
    try {
      const declared = entry.notification.get_expire_timeout()
      if (declared > 0) ms = declared
    } catch (error) {
      console.error(`notifications: cannot read expire timeout: ${error}`)
    }
    const id = entry.id
    const source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
      timers.delete(id)
      dismissCard(id)
      return GLib.SOURCE_REMOVE
    })
    timers.set(id, source)
  }

  function addCard(
    notification: InstanceType<typeof Notifd.Notification>,
    newestOnTop: boolean,
  ): void {
    if (stack === null) return
    const id = notification.get_id()
    // A replaced notification reuses its id: drop the stale card first.
    removeCard(id)
    showWindow()
    const widget = NotificationCard(notification, () => dismissCard(id))
    cards.push({ id, notification, widget })
    if (newestOnTop) stack.prepend(widget)
    else stack.append(widget)
    scheduleExpiry({ id, notification, widget })
    // Bound the stack: the oldest overflow is dismissed locally (authoritative)
    // and the daemon is told, so the cap holds even for sticky criticals.
    while (cards.length > MAX_VISIBLE) {
      const oldest = cards[0]
      if (oldest === undefined) break
      dismissCard(oldest.id)
    }
  }

  try {
    notifd.connect("notified", (_self, id: number, _replaced: boolean) => {
      try {
        const notification = notifd.get_notification(id)
        if (notification !== null) addCard(notification, true)
      } catch (error) {
        console.error(`notifications: notified handler failed: ${error}`)
      }
    })
    notifd.connect("resolved", (_self, id: number, _reason: number) => {
      removeCard(id)
    })
  } catch (error) {
    console.error(`notifications: cannot subscribe to the daemon: ${error}`)
  }

  function onKey(keyval: number): boolean {
    if (keyval === Gdk.KEY_Escape) {
      // Dismiss the newest card (or hide an empty stack window).
      const newest = cards[cards.length - 1]
      if (newest === undefined) {
        // With no daemon cards left, Escape falls through the two progress
        // cards newest-first, then hides an empty stack. A sticky speed-test
        // failure is dismissible this way even though it never expires.
        if (speedtestCard !== null) {
          dismissSpeedtestCard()
          return true
        }
        if (wallpaperCard !== null) {
          dismissWallpaperCard()
          return true
        }
        hideWindow()
        return true
      }
      dismissCard(newest.id)
      return true
    }
    return false
  }

  return (
    <window
      visible
      name={WINDOW_NAME}
      class="notifications-window"
      gdkmonitor={gdkmonitor}
      anchor={Astal.WindowAnchor.TOP | Astal.WindowAnchor.RIGHT}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      margin_top={12}
      margin_right={12}
      $={(self) => {
        // Capture phase so Escape clears a card even when a chip has focus.
        const keys = new Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", (_controller, keyval, _keycode, _state) =>
          onKey(keyval),
        )
        self.add_controller(keys)
        // NOTE: earlier revisions hydrated the daemon's live notification list
        // on map. Removed deliberately: this process IS the notifd daemon
        // (AstalNotifd), so its list is always empty at startup — a hydrate
        // could only ever re-add cards the stack had already cleared,
        // resurrecting dismissed toasts and duplicating cards whenever the
        // window remapped. Notifications that arrive during startup are
        // covered by the `notified` handler.
      }}
    >
      <box
        orientation={Gtk.Orientation.VERTICAL}
        spacing={12}
        css_classes={["notif-stack"]}
        $={(self) => {
          stack = self
          subscribeWallpaperEvents(wallpaperUpdate)
          subscribeSpeedTestEvents(speedtestUpdate)
        }}
      />
    </window>
  )
}
