import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"

/**
 * Async NetworkManager D-Bus plumbing (design §1).
 *
 * The system bus is connected exactly once at module init; every later bus
 * interaction is asynchronous (`Gio.DBusConnection.call` + `call_finish`).
 * There is deliberately no synchronous call past that one connect — the
 * service layer must never block the GTK main loop.
 */

export const NM = "org.freedesktop.NetworkManager"
export const NM_MANAGER_PATH = "/org/freedesktop/NetworkManager"
export const NM_DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
export const NM_WIRELESS_IFACE = "org.freedesktop.NetworkManager.Device.Wireless"
export const NM_ACCESS_POINT_IFACE = "org.freedesktop.NetworkManager.AccessPoint"
export const NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
export const NM_SETTINGS_IFACE = "org.freedesktop.NetworkManager.Settings"
export const NM_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Settings.Connection"
export const DBUS_PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

/** D-Bus failure carrying the remote error name for the service to classify. */
export class NMBusError extends Error {
  readonly dbusName: string

  constructor(dbusName: string, message: string) {
    super(message)
    this.name = "NMBusError"
    this.dbusName = dbusName
  }
}

let systemConnection: Gio.DBusConnection | null = null
try {
  systemConnection = Gio.bus_get_sync(Gio.BusType.SYSTEM, null)
} catch (error) {
  console.error(`nm-client: system bus unavailable: ${error}`)
}

export function systemBus(): Gio.DBusConnection {
  if (systemConnection === null) {
    throw new NMBusError(
      "org.freedesktop.DBus.Error.NotSupported",
      "system bus unavailable",
    )
  }
  return systemConnection
}

function messageOf(error: unknown): string {
  if (error !== null && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message)
  }
  return String(error)
}

function remoteNameOf(error: unknown): string {
  if (error instanceof NMBusError) return error.dbusName
  if (error !== null && typeof error === "object" && "matches" in error) {
    try {
      const remote = Gio.DBusError.get_remote_error(error as GLib.Error)
      if (remote) return remote
    } catch {
      /* fall through to message parsing */
    }
  }
  const prefix = messageOf(error).match(/GDBus\.Error:([A-Za-z0-9_.]+):/)
  return prefix ? prefix[1] : "org.freedesktop.DBus.Error.Failed"
}

/** Coerce any thrown value into an `NMBusError` with its D-Bus error name. */
export function asBusError(error: unknown): NMBusError {
  if (error instanceof NMBusError) return error
  return new NMBusError(remoteNameOf(error), messageOf(error))
}

/**
 * Promisified `Gio.DBusConnection.call`. `params` is the full parameter tuple
 * (e.g. `new GLib.Variant("(s)", [iface])`), or null for a no-argument method.
 */
export function call(
  dest: string,
  path: string,
  iface: string,
  method: string,
  params: GLib.Variant | null,
  timeoutMs = 25000,
): Promise<GLib.Variant> {
  return new Promise((resolve, reject) => {
    systemBus().call(
      dest,
      path,
      iface,
      method,
      params,
      null,
      Gio.DBusCallFlags.NONE,
      timeoutMs,
      null,
      (connection, result) => {
        try {
          resolve(connection.call_finish(result))
        } catch (error) {
          reject(asBusError(error))
        }
      },
    )
  })
}

/**
 * `org.freedesktop.DBus.Properties.GetAll` unpacked into a plain object.
 * `dest` defaults to NetworkManager; other services (e.g. BlueZ) pass theirs.
 */
export async function getAll(
  path: string,
  iface: string,
  dest: string = NM,
): Promise<Record<string, unknown>> {
  const reply = await call(
    dest,
    path,
    DBUS_PROPERTIES_IFACE,
    "GetAll",
    new GLib.Variant("(s)", [iface]),
  )
  const unpacked = reply.recursiveUnpack() as [Record<string, unknown>]
  return unpacked[0] ?? {}
}

/** `org.freedesktop.DBus.Properties.Get`, returning the contained variant. */
export async function getProperty(
  path: string,
  iface: string,
  name: string,
  dest: string = NM,
): Promise<GLib.Variant> {
  const reply = await call(
    dest,
    path,
    DBUS_PROPERTIES_IFACE,
    "Get",
    new GLib.Variant("(ss)", [iface, name]),
  )
  return reply.get_child_value(0).get_variant()
}

/** Subscribe to a signal; returns an unsubscribe closure. */
export function subscribe(
  sender: string | null,
  path: string | null,
  iface: string | null,
  signal: string | null,
  cb: (parameters: GLib.Variant) => void,
): () => void {
  const connection = systemBus()
  const id = connection.signal_subscribe(
    sender,
    iface,
    signal,
    path,
    null,
    Gio.DBusSignalFlags.NONE,
    (_connection, _sender, _path, _iface, _signal, parameters) =>
      cb(parameters),
  )
  return () => {
    try {
      connection.signal_unsubscribe(id)
    } catch {
      /* bus gone */
    }
  }
}

/**
 * Watch `PropertiesChanged` for one `(path, iface)` pair, delivering the
 * changed-properties dict (the `invalidated` list is not delivered). `sender`
 * defaults to NetworkManager; other services (e.g. BlueZ) pass theirs.
 */
export function watchProperties(
  path: string,
  iface: string,
  cb: (changed: Record<string, unknown>) => void,
  sender: string = NM,
): () => void {
  return subscribe(
    sender,
    path,
    DBUS_PROPERTIES_IFACE,
    "PropertiesChanged",
    (parameters) => {
      const unpacked = parameters.recursiveUnpack() as [
        string,
        Record<string, unknown>,
        string[],
      ]
      if (unpacked[0] !== iface) return
      cb(unpacked[1] ?? {})
    },
  )
}

/** Fully unpack a variant into native JS values. */
export function variantToJs(value: GLib.Variant): unknown {
  return value.recursiveUnpack()
}
