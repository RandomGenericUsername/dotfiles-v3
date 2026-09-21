import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { Accessor, createComputed, createState } from "ags"
import { execAsync } from "ags/process"
import {
  MPRIS_EXCLUDED,
  MPRIS_PREFIX,
  TrackMeta,
  interpolatePosition,
  parseBusName,
  parseMetadata,
  pickActivePlayer,
} from "./mpris-core"

/**
 * MPRIS transport service (WP-B).
 *
 * `org.mpris.MediaPlayer2.*` on the SESSION bus is the single source of truth
 * for playback state. MPRIS is NOT reachable through AstalWp (and AstalMpris is
 * not installed on this machine), so this service speaks D-Bus directly.
 *
 * Invariants honoured here:
 *  - I1: state changes arrive only from signals (`PropertiesChanged`, `Seeked`,
 *    `NameOwnerChanged`) plus a subscribe-before-read hydration. There is no
 *    polling timer; a render tick may interpolate the *display* position from
 *    `positionUs`/`positionSyncedAtMs` locally.
 *  - I2: `playerctl` is used for actions only — never to read state into the UI.
 *
 * Structure mirrors `bluetooth-service.ts`: one module-level bootstrap guarded
 * by a `started` flag, a mutable cache behind exported `createState` accessors.
 */

const PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
const PLAYER_PATH = "/org/mpris/MediaPlayer2"
const DBUS = "org.freedesktop.DBus"
const DBUS_PATH = "/org/freedesktop/DBus"
const DBUS_PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
const NAME_OWNER_CHANGED = "NameOwnerChanged"

//: Session-bus seam (new here — `nm-client.ts` owns the system bus). Connected
//: once at module init; every later interaction is async (no blocking call on
//: the GTK main loop).
let sessionConnection: Gio.DBusConnection | null = null
try {
  sessionConnection = Gio.bus_get_sync(Gio.BusType.SESSION, null)
} catch (error) {
  console.error(`mpris-service: session bus unavailable: ${error}`)
}

function sessionBus(): Gio.DBusConnection {
  if (sessionConnection === null) throw new Error("session bus unavailable")
  return sessionConnection
}

export interface MprisPlayer {
  busName: string
  identity: string
  instance: string | null
  status: "Playing" | "Paused" | "Stopped"
  metadata: TrackMeta
  canSeek: boolean
  canGoNext: boolean
  canGoPrevious: boolean
  canPause: boolean
  positionUs: number
  positionSyncedAtMs: number
  lastPlayingAt: number
}

const [mprisPlayers, setMprisPlayers] = createState<MprisPlayer[]>([])

/** Every discovered player, minus `MPRIS_EXCLUDED` (never a row). */
export { mprisPlayers }

/** The master-button target: `pickActivePlayer(mprisPlayers())` (D1). */
export const activePlayer: Accessor<MprisPlayer | null> = createComputed(() =>
  pickActivePlayer(mprisPlayers()),
)

// ── Mutable service state ────────────────────────────────────────────────

const playerCache = new Map<string, MprisPlayer>()
const unwatchers = new Map<string, Array<() => void>>()

// ── Helpers ──────────────────────────────────────────────────────────────

//: Monotonic milliseconds: immune to wall-clock jumps, and the same clock
//: `interpolatePosition` is fed, so a paused display freezes exactly.
function nowMs(): number {
  return GLib.get_monotonic_time() / 1000
}

function asStatus(value: unknown): MprisPlayer["status"] {
  return value === "Playing" || value === "Paused" || value === "Stopped"
    ? value
    : "Stopped"
}

function playerFromProps(
  busName: string,
  props: Record<string, unknown>,
  previous: MprisPlayer | null = null,
): MprisPlayer {
  const { identity, instance } = parseBusName(busName)
  const status = asStatus(props.PlaybackStatus)
  //: Preserve the ordering signal across a re-read: a player already Playing
  //: keeps its original `lastPlayingAt` (resync must not re-rank the master).
  //: A Stopped player resets to 0 so a stale timestamp can never let it outrank
  //: a live (paused) player in `pickActivePlayer`'s fallback (found live, WP-F:
  //: a stopped Chromium instance was chosen over the playing tidal-hifi).
  const lastPlayingAt =
    status === "Playing"
      ? previous !== null && previous.status === "Playing"
        ? previous.lastPlayingAt
        : nowMs()
      : status === "Paused"
        ? (previous?.lastPlayingAt ?? 0)
        : 0
  const position = Number(props.Position ?? 0)
  return {
    busName,
    identity,
    instance,
    status,
    metadata: parseMetadata((props.Metadata ?? {}) as Record<string, unknown>),
    canSeek: Boolean(props.CanSeek),
    canGoNext: Boolean(props.CanGoNext),
    canGoPrevious: Boolean(props.CanGoPrevious),
    canPause: Boolean(props.CanPause),
    positionUs: Number.isFinite(position) && position >= 0 ? position : 0,
    positionSyncedAtMs: nowMs(),
    lastPlayingAt,
  }
}

function playerSuffix(busName: string): string {
  return busName.startsWith(MPRIS_PREFIX)
    ? busName.slice(MPRIS_PREFIX.length)
    : busName
}

function applyPlayers(): void {
  setMprisPlayers([...playerCache.values()])
}

// ── Bus plumbing (async `call` + `signal_subscribe`, mirroring nm-client) ──

function call(
  dest: string,
  path: string,
  iface: string,
  method: string,
  params: GLib.Variant | null,
  timeoutMs = 25000,
): Promise<GLib.Variant> {
  return new Promise((resolve, reject) => {
    sessionBus().call(
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
          reject(error)
        }
      },
    )
  })
}

function subscribe(
  sender: string | null,
  path: string,
  iface: string,
  signal: string,
  cb: (parameters: GLib.Variant) => void,
): () => void {
  const connection = sessionBus()
  const id = connection.signal_subscribe(
    sender,
    iface,
    signal,
    path,
    null,
    Gio.DBusSignalFlags.NONE,
    (_connection, _sender, _path, _iface, _signal, parameters) => cb(parameters),
  )
  return () => {
    try {
      connection.signal_unsubscribe(id)
    } catch {
      /* bus gone */
    }
  }
}

async function getProperty(
  dest: string,
  iface: string,
  name: string,
): Promise<unknown> {
  const reply = await call(
    dest,
    PLAYER_PATH,
    DBUS_PROPERTIES_IFACE,
    "Get",
    new GLib.Variant("(ss)", [iface, name]),
  )
  const unpacked = reply.recursiveUnpack() as [unknown]
  return unpacked[0]
}

async function getAll(
  dest: string,
  iface: string,
): Promise<Record<string, unknown>> {
  const reply = await call(
    dest,
    PLAYER_PATH,
    DBUS_PROPERTIES_IFACE,
    "GetAll",
    new GLib.Variant("(s)", [iface]),
  )
  const unpacked = reply.recursiveUnpack() as [Record<string, unknown>]
  return unpacked[0] ?? {}
}

// ── Position synchronisation ─────────────────────────────────────────────
//: `Position` is read-only and NOT part of `PropertiesChanged` (MPRIS spec), so
//: it is only read at the WP-B sync points: hydration, `Seeked` (value carried
//: by the signal), transition to Playing, and Metadata change.

async function syncPosition(busName: string): Promise<void> {
  try {
    const value = await getProperty(busName, PLAYER_IFACE, "Position")
    const player = playerCache.get(busName)
    if (player === undefined) return
    const position = Number(value)
    playerCache.set(busName, {
      ...player,
      positionUs:
        Number.isFinite(position) && position >= 0 ? position : player.positionUs,
      positionSyncedAtMs: nowMs(),
    })
    applyPlayers()
  } catch (error) {
    console.error(`mpris-service: reading Position for ${busName} failed: ${error}`)
  }
}

// ── Signal handlers ──────────────────────────────────────────────────────

function handlePropertiesChanged(busName: string, parameters: GLib.Variant): void {
  const [iface, changed, invalidated] = parameters.recursiveUnpack() as [
    string,
    Record<string, unknown>,
    string[],
  ]
  if (iface !== PLAYER_IFACE) return
  const player = playerCache.get(busName)
  if (player === undefined) return

  //: MPRIS is allowed to announce a property in `invalidated` with NO value in
  //: `changed` (common for `Metadata`/`Position` on some players). Treat an
  //: invalidated property exactly like a changed one so the update is not lost.
  const invalid = Array.isArray(invalidated) ? invalidated : []
  const saw = (name: string): boolean => name in changed || invalid.includes(name)

  const next: MprisPlayer = { ...player }
  let synchronise = false

  if (saw("PlaybackStatus")) {
    const status = asStatus("PlaybackStatus" in changed ? changed.PlaybackStatus : player.status)
    const wasPlaying = player.status === "Playing"
    //: Leaving Playing must freeze the interpolated position into the base,
    //: otherwise a later paused render snaps back to the last bus sync.
    if (wasPlaying && status !== "Playing") {
      next.positionUs = interpolatePosition(
        player.positionUs,
        player.positionSyncedAtMs,
        true,
        nowMs(),
      )
      next.positionSyncedAtMs = nowMs()
    }
    next.status = status
    if (status === "Playing") {
      next.lastPlayingAt = nowMs()
      if (!wasPlaying) {
        next.positionSyncedAtMs = nowMs()
        synchronise = true
      }
    } else if (status === "Stopped") {
      //: A stopped player must not keep a stale rank (see playerFromProps).
      next.lastPlayingAt = 0
    }
  }
  if (saw("Metadata")) {
    if ("Metadata" in changed) {
      next.metadata = parseMetadata(
        (changed.Metadata ?? {}) as Record<string, unknown>,
      )
    }
    synchronise = true
  }
  if (saw("CanSeek")) next.canSeek = Boolean("CanSeek" in changed ? changed.CanSeek : player.canSeek)
  if (saw("CanGoNext")) {
    next.canGoNext = Boolean("CanGoNext" in changed ? changed.CanGoNext : player.canGoNext)
  }
  if (saw("CanGoPrevious")) {
    next.canGoPrevious = Boolean(
      "CanGoPrevious" in changed ? changed.CanGoPrevious : player.canGoPrevious,
    )
  }
  if (saw("CanPause")) {
    next.canPause = Boolean("CanPause" in changed ? changed.CanPause : player.canPause)
  }

  playerCache.set(busName, next)
  if (synchronise) void syncPosition(busName)
  else if (invalid.includes("Position")) void syncPosition(busName)
  applyPlayers()
}

function handleSeeked(busName: string, parameters: GLib.Variant): void {
  const [position] = parameters.recursiveUnpack() as [number]
  const player = playerCache.get(busName)
  if (player === undefined) return
  const value = Number(position)
  playerCache.set(busName, {
    ...player,
    positionUs: Number.isFinite(value) && value >= 0 ? value : player.positionUs,
    positionSyncedAtMs: nowMs(),
  })
  applyPlayers()
}

// ── Discovery / hydration ────────────────────────────────────────────────

function isMprisPlayer(busName: string): boolean {
  if (!busName.startsWith(MPRIS_PREFIX)) return false
  return !MPRIS_EXCLUDED.includes(parseBusName(busName).identity)
}

function installSignals(busName: string): void {
  if (unwatchers.has(busName)) return
  unwatchers.set(busName, [
    subscribe(busName, PLAYER_PATH, DBUS_PROPERTIES_IFACE, "PropertiesChanged", (params) =>
      handlePropertiesChanged(busName, params),
    ),
    subscribe(busName, PLAYER_PATH, PLAYER_IFACE, "Seeked", (params) =>
      handleSeeked(busName, params),
    ),
  ])
}

function removePlayer(busName: string): void {
  const offs = unwatchers.get(busName)
  if (offs !== undefined) {
    for (const off of offs) off()
    unwatchers.delete(busName)
  }
  if (playerCache.delete(busName)) applyPlayers()
}

//: Subscribe-before-read: the per-player `PropertiesChanged`/`Seeked` rules are
//: installed before `GetAll`, so a transition during hydration is never lost.
async function hydratePlayer(busName: string): Promise<void> {
  installSignals(busName)
  try {
    const props = await getAll(busName, PLAYER_IFACE)
    playerCache.set(busName, playerFromProps(busName, props))
    applyPlayers()
  } catch (error) {
    console.error(`mpris-service: hydration of ${busName} failed: ${error}`)
  }
}

//: One-shot re-read (WP-C calls this when the popup opens alongside
//: `refreshStreamTargets`). Not a timer: it is a user-action hydration (I1).
export function resyncMpris(): void {
  for (const busName of [...playerCache.keys()]) void refreshPlayer(busName)
}

async function refreshPlayer(busName: string): Promise<void> {
  try {
    const props = await getAll(busName, PLAYER_IFACE)
    const previous = playerCache.get(busName)
    if (previous === undefined) return
    playerCache.set(busName, playerFromProps(busName, props, previous))
    applyPlayers()
  } catch (error) {
    console.error(`mpris-service: resync of ${busName} failed: ${error}`)
  }
}

async function listNames(): Promise<string[]> {
  const reply = await call(DBUS, DBUS_PATH, DBUS, "ListNames", null)
  const [names] = reply.recursiveUnpack() as [string[]]
  return Array.isArray(names) ? names : []
}

//: Unfiltered `NameOwnerChanged`; the MPRIS prefix and exclusion list are
//: applied here, not in the match rule (WP-B contract §5).
function handleNameOwnerChanged(parameters: GLib.Variant): void {
  const unpacked = parameters.recursiveUnpack() as [string, string, string]
  const name = unpacked[0]
  const newOwner = unpacked[2]
  if (!isMprisPlayer(name)) return
  //: Tear down the old subscription in every case (a name swap without a gap
  //: would otherwise leave the match pinned to the previous owner).
  removePlayer(name)
  if (newOwner !== "") void hydratePlayer(name)
}

// ── Actions (`playerctl` for actions only — I2) ───────────────────────────

function runPlayerctl(busName: string, args: string[]): void {
  execAsync(["playerctl", "-p", playerSuffix(busName), ...args]).catch(console.error)
}

export function playPausePlayer(p: MprisPlayer): void {
  const current = playerCache.get(p.busName) ?? p
  const now = nowMs()
  if (current.status === "Playing") {
    playerCache.set(p.busName, {
      ...current,
      status: "Paused",
      positionUs: interpolatePosition(
        current.positionUs,
        current.positionSyncedAtMs,
        true,
        now,
      ),
      positionSyncedAtMs: now,
    })
  } else {
    playerCache.set(p.busName, {
      ...current,
      status: "Playing",
      lastPlayingAt: now,
      positionSyncedAtMs: now,
    })
  }
  applyPlayers()
  runPlayerctl(p.busName, ["play-pause"])
}

export function nextPlayer(p: MprisPlayer): void {
  runPlayerctl(p.busName, ["next"])
}

export function previousPlayer(p: MprisPlayer): void {
  runPlayerctl(p.busName, ["previous"])
}

export function seekPlayer(p: MprisPlayer, absoluteUs: number): void {
  const current = playerCache.get(p.busName) ?? p
  const positionUs = Math.max(0, absoluteUs)
  playerCache.set(p.busName, { ...current, positionUs, positionSyncedAtMs: nowMs() })
  applyPlayers()
  //: Absolute seek, µs → s (WP-B contract §5).
  runPlayerctl(p.busName, ["position", String(positionUs / 1_000_000)])
}

// ── Bootstrap ────────────────────────────────────────────────────────────

let started = false

async function bootstrap(): Promise<void> {
  subscribe(null, DBUS_PATH, DBUS, NAME_OWNER_CHANGED, handleNameOwnerChanged)
  const names = await listNames()
  for (const name of names) {
    if (isMprisPlayer(name)) await hydratePlayer(name)
  }
}

function start(): void {
  if (started) return
  started = true
  void bootstrap().catch((error) =>
    console.error(`mpris-service: bootstrap failed: ${error}`),
  )
}

start()
