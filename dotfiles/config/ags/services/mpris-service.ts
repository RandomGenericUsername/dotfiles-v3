import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { Accessor, createComputed, createState } from "ags"
import { execAsync } from "ags/process"
import {
  MPRIS_EXCLUDED,
  MPRIS_PREFIX,
  TrackMeta,
  canonicalIdentity,
  interpolatePosition,
  normalisePosition,
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
  /** The MPRIS root-interface `Identity` property — the REAL app name.
   *  The bus-name suffix is NOT trustworthy: an Electron app registers one
   *  interface as `<app>` and a second as `chromium.instance<pid>`, so the
   *  suffix `chromium` may belong to Tidal (measured: `chromium.instance95550`
   *  reports Identity "tidal-hifi", same PID as the `tidal-hifi` interface). */
  identity: string
  /** Canonical identity (ALIAS-folded) — the app key for matching and rows. */
  canonical: string
  /** Owning process id, the reliable join between two interfaces of one app
   *  (both interfaces of an Electron app share the PID). 0 when unknown. */
  pid: number
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

/** One player per APP: two MPRIS interfaces of the same process (an Electron
 *  app registers `<app>` and `chromium.instance<pid>`) collapse to the single
 *  most recently active one, resolved by PID then canonical identity. Without
 *  this the popup showed the same playback twice (once as "tidal-hifi", once as
 *  "chromium") and stopping either appeared to stop both. */
export function playersByApp(): MprisPlayer[] {
  const groups = new Map<string, MprisPlayer[]>()
  for (const player of mprisPlayers()) {
    const key = player.pid > 0 ? `pid:${player.pid}` : `id:${player.canonical}`
    const group = groups.get(key)
    if (group) group.push(player)
    else groups.set(key, [player])
  }
  const out: MprisPlayer[] = []
  for (const group of groups.values()) {
    const representative = pickActivePlayer(group)
    if (representative) out.push(representative)
  }
  return out
}

/** The master-button target (D1): the most recently active app. */
export const activePlayer: Accessor<MprisPlayer | null> = createComputed(() =>
  pickActivePlayer(playersByApp()),
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

/** Read the MPRIS root-interface `Identity` — the app's REAL name.
 *
 *  This is the authoritative identity; the bus-name suffix is not (an Electron
 *  app publishes `<app>` AND `chromium.instance<pid>`, so the suffix `chromium`
 *  can belong to Tidal — measured live). */
async function readIdentity(busName: string): Promise<string> {
  try {
    const value = await getPropertyOn(
      busName,
      "/org/mpris/MediaPlayer2",
      "org.mpris.MediaPlayer2",
      "Identity",
    )
    return typeof value === "string" && value !== "" ? value : ""
  } catch {
    return ""
  }
}

/** Resolve the owning process id. The bus name's `instance<N>` suffix IS the
 *  PID for Electron/Chromium apps; otherwise ask the bus daemon. The PID is the
 *  reliable join between two interfaces of one app. */
async function readPid(busName: string, instance: string | null): Promise<number> {
  const fromSuffix = instance !== null ? Number(instance) : NaN
  if (Number.isFinite(fromSuffix) && fromSuffix > 0) return fromSuffix
  try {
    const reply = await call(
      DBUS,
      DBUS_PATH,
      DBUS,
      "GetConnectionUnixProcessID",
      new GLib.Variant("(s)", [busName]),
    )
    const [pid] = reply.recursiveUnpack() as [number]
    return Number.isFinite(pid) && pid > 0 ? pid : 0
  } catch {
    return 0
  }
}

/** `playerFromProps` builds a player from already-resolved identity/pid (both
 *  are async D-Bus reads, so they are hydrated once instead of on every
 *  PropertiesChanged). */
function playerFromProps(
  busName: string,
  props: Record<string, unknown>,
  identity: string,
  pid: number,
  previous: MprisPlayer | null = null,
): MprisPlayer {
  const { instance } = parseBusName(busName)
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
  return {
    busName,
    identity,
    canonical: canonicalIdentity(identity),
    pid,
    instance,
    status,
    metadata: parseMetadata((props.Metadata ?? {}) as Record<string, unknown>),
    canSeek: Boolean(props.CanSeek),
    canGoNext: Boolean(props.CanGoNext),
    canGoPrevious: Boolean(props.CanGoPrevious),
    canPause: Boolean(props.CanPause),
    positionUs: normalisePosition(props.Position, 0),
    positionSyncedAtMs: nowMs(),
    lastPlayingAt,
  }
}

function playerSuffix(busName: string): string {
  return busName.startsWith(MPRIS_PREFIX)
    ? busName.slice(MPRIS_PREFIX.length)
    : busName
}

let applyScheduled = false

/**
 * Flush the player cache into the reactive accessor — always deferred to idle.
 *
 * A synchronous flush inside a user gesture is fatal: `seekPlayer` runs inside
 * the scale's drag-end handler, and a sync `setMprisPlayers` re-fires
 * `applicationRows()` → gnim's `For` unparents every row — including the very
 * slider being dragged, which still holds an active gesture grab. GTK aborts:
 * `gtk_widget_unparent` → `gtk_widget_real_unrealize: assertion failed
 * (!priv->mapped)`. Deferring to idle lets the gesture emission complete first;
 * the flush always reads the CURRENT cache, so coalesced calls lose nothing.
 */
function applyPlayers(): void {
  if (applyScheduled) return
  applyScheduled = true
  GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
    applyScheduled = false
    setMprisPlayers([...playerCache.values()])
    return false
  })
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

/** `Get` on an arbitrary interface/path (the root `Identity` lives on
 *  `org.mpris.MediaPlayer2`, not on the Player interface at PLAYER_PATH's
 *  player iface). */
async function getPropertyOn(
  dest: string,
  path: string,
  iface: string,
  name: string,
): Promise<unknown> {
  const reply = await call(
    dest,
    path,
    DBUS_PROPERTIES_IFACE,
    "Get",
    new GLib.Variant("(ss)", [iface, name]),
  )
  const unpacked = reply.recursiveUnpack() as [unknown]
  return unpacked[0]
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
    playerCache.set(busName, {
      ...player,
      positionUs: normalisePosition(value, player.positionUs),
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
  playerCache.set(busName, {
    ...player,
    positionUs: normalisePosition(position, player.positionUs),
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
//: Identity + PID are read once here (they never change for a bus name).
async function hydratePlayer(busName: string): Promise<void> {
  installSignals(busName)
  try {
    const { instance } = parseBusName(busName)
    const [props, rootIdentity, pid] = await Promise.all([
      getAll(busName, PLAYER_IFACE),
      readIdentity(busName),
      readPid(busName, instance),
    ])
    //: Fall back to the bus-name suffix only when the root `Identity` is
    //: absent (a minimal MPRIS implementation); otherwise trust Identity.
    const fallback = parseBusName(busName).identity
    const identity = rootIdentity || fallback
    playerCache.set(busName, playerFromProps(busName, props, identity, pid))
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
    playerCache.set(
      busName,
      playerFromProps(busName, props, previous.identity, previous.pid, previous),
    )
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
