import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"

const BUS_NAME = "org.dotfiles.Events"
const OBJECT_PATH = "/org/dotfiles/Events"
const INTERFACE = "org.dotfiles.Events1"
const TOPIC = "wallpaper.state"
const DBUS_NAME = "org.freedesktop.DBus"
const DBUS_PATH = "/org/freedesktop/DBus"
const DBUS_INTERFACE = "org.freedesktop.DBus"

export type WallpaperEventSource = "signal" | "startup-state"
export type WallpaperPayload = Record<string, unknown>
export type WallpaperEventHandler = (
  payload: WallpaperPayload,
  source: WallpaperEventSource,
) => void

let connection: Gio.DBusConnection | null = null
let started = false
let lastEpoch = 0
let lastSeq = 0
let handler: WallpaperEventHandler | null = null

function ensureConnection(): Gio.DBusConnection {
  if (connection === null) connection = Gio.bus_get_sync(Gio.BusType.SESSION, null)
  return connection
}

function asCounter(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0
}

function dispatch(
  epoch: number,
  seq: number,
  payload: unknown,
  source: WallpaperEventSource,
): void {
  if (payload === null || typeof payload !== "object") return
  if (epoch < lastEpoch || (epoch === lastEpoch && seq <= lastSeq)) return
  if (epoch > lastEpoch) {
    lastEpoch = epoch
    lastSeq = 0
  }
  lastSeq = seq
  handler?.(payload as WallpaperPayload, source)
}

/**
 * Subscribe to wallpaper events, then read the current event state once.
 * The read closes the startup/restart race; there is no timer or polling.
 */
export function subscribeWallpaperEvents(nextHandler: WallpaperEventHandler): void {
  handler = nextHandler
  if (started) return
  started = true

  const bus = ensureConnection()
  bus.signal_subscribe(
    null,
    INTERFACE,
    "DomainEvent",
    OBJECT_PATH,
    null,
    Gio.DBusSignalFlags.NONE,
    (_connection, _sender, _path, _interface, _signal, parameters) => {
      const values = parameters.recursiveUnpack() as unknown[]
      if (values.length < 5 || values[0] !== TOPIC) return
      dispatch(asCounter(values[3]), asCounter(values[2]), values[4], "signal")
    },
  )

  // If the hub starts after this app, hydrate when its bus name appears.
  bus.signal_subscribe(
    DBUS_NAME,
    DBUS_INTERFACE,
    "NameOwnerChanged",
    DBUS_PATH,
    BUS_NAME,
    Gio.DBusSignalFlags.NONE,
    (_connection, _sender, _path, _interface, _signal, parameters) => {
      const values = parameters.recursiveUnpack() as string[]
      if (values.length === 3 && values[2]) hydrate()
    },
  )

  hydrate()
}

function hydrate(): void {
  try {
    const reply = ensureConnection().call_sync(
      BUS_NAME,
      OBJECT_PATH,
      INTERFACE,
      "GetTopicState",
      new GLib.Variant("(s)", [TOPIC]),
      null,
      Gio.DBusCallFlags.NONE,
      2000,
      null,
    )
    const values = reply.recursiveUnpack() as unknown[]
    const raw = values[0]
    if (raw === null || typeof raw !== "object") return
    const state = raw as Record<string, unknown>
    dispatch(
      asCounter(state["_epoch"]),
      asCounter(state["_seq"]),
      state,
      "startup-state",
    )
  } catch (error) {
    // The wallpaper command is allowed to run when the hub is absent; a
    // later NameOwnerChanged signal retries the one-shot hydration.
    console.debug(`notifications: wallpaper state unavailable: ${error}`)
  }
}
