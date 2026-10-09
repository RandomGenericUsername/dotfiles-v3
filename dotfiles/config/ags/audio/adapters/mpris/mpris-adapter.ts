import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { execAsync } from "ags/process"
import {
  canonicalIdentity, carryDuration, MPRIS_EXCLUDED, MPRIS_PREFIX, normalisePosition, parseBusName, parseMetadata,
  type TrackMeta,
} from "../../../services/mpris-core"
import type { AudioPlayer, PlayerId, PlayerMedia } from "../../domain/audio-model.ts"
import type { MprisObservation, MprisObservationPort, MprisPort, Unsubscribe } from "../../application/ports.ts"

const DBUS = "org.freedesktop.DBus"
const DBUS_PATH = "/org/freedesktop/DBus"
const DBUS_PROPERTIES = "org.freedesktop.DBus.Properties"
const PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
const ROOT_IFACE = "org.mpris.MediaPlayer2"
const PLAYER_PATH = "/org/mpris/MediaPlayer2"
const MAX_TRACK_LENGTH_US = 24 * 60 * 60 * 1_000_000

type Listener = (event: MprisObservation) => void
type RawProps = Record<string, unknown>

interface PlayerRecord {
  id: string
  busName: string
  appId: string
  playback: AudioPlayer["playback"]
  capabilities: AudioPlayer["capabilities"]
  trackMeta: TrackMeta
  media: PlayerMedia
  positionSyncedAtMs: number
}

function unpack(value: unknown): unknown {
  if (value !== null && typeof value === "object" && "recursiveUnpack" in value) {
    try { return (value as { recursiveUnpack(): unknown }).recursiveUnpack() } catch { return value }
  }
  return value
}
function dict(value: unknown): RawProps {
  const plain = unpack(value)
  return plain !== null && typeof plain === "object" && !Array.isArray(plain) ? plain as RawProps : {}
}
function stringValue(value: unknown): string {
  const raw = unpack(value)
  return typeof raw === "string" ? raw : ""
}
function booleanValue(value: unknown): boolean { return unpack(value) === true }
function statusValue(value: unknown): AudioPlayer["playback"] {
  switch (unpack(value)) {
    case "Playing": return "playing"
    case "Paused": return "paused"
    case "Stopped": return "stopped"
    default: return "unknown"
  }
}
function position(value: unknown): number | null {
  const raw = Number(unpack(value))
  if (!Number.isFinite(raw) || raw < 0 || raw > MAX_TRACK_LENGTH_US) return null
  return normalisePosition(raw, 0)
}
function metadata(props: RawProps, previous?: PlayerRecord): { track: TrackMeta; media: PlayerMedia } {
  const raw = dict(props.Metadata)
  const track = carryDuration(parseMetadata(raw), previous?.trackMeta)
  return { track, media: {
    title: track.title,
    artist: track.artist,
    album: track.album,
    artworkUri: stringValue(raw["mpris:artUrl"]) || null,
    lengthUs: track.lengthUs > 0 ? track.lengthUs : null,
    positionUs: previous?.media.positionUs ?? null,
  } }
}
function toPlayer(record: PlayerRecord): AudioPlayer {
  return { id: record.id, appId: record.appId, current: true, playback: record.playback,
    capabilities: { ...record.capabilities }, media: { ...record.media } }
}

/** Signal-driven MPRIS adapter. PlayerId includes the bus name and owner generation. */
export class MprisAdapter implements MprisObservationPort, MprisPort {
  private readonly connection: Gio.DBusConnection
  private readonly records = new Map<string, PlayerRecord>()
  private readonly listeners = new Set<Listener>()
  private readonly playerSignals = new Map<string, number[]>()
  private readonly generations = new Map<string, number>()
  private ownerSignal = 0
  private startPromise: Promise<void> | null = null
  private readonly hydration = new Map<string, Promise<void>>()

  constructor(connection?: Gio.DBusConnection) {
    this.connection = connection ?? Gio.bus_get_sync(Gio.BusType.SESSION, null)
  }

  subscribe(listener: Listener): Unsubscribe {
    this.listeners.add(listener)
    void this.start().catch(() => {})
    return () => { this.listeners.delete(listener) }
  }

  async hydrate(): Promise<MprisObservation> {
    await this.start()
    return { kind: "snapshot", players: [...this.records.values()].map(toPlayer) }
  }

  private emit(event: MprisObservation): void {
    for (const listener of [...this.listeners]) {
      try { listener(event) } catch (error) { console.error("audio mpris listener failed:", error) }
    }
  }

  private start(): Promise<void> {
    if (this.startPromise !== null) return this.startPromise
    // Subscribe synchronously before ListNames; per-player watches precede GetAll.
    this.ownerSignal = this.connection.signal_subscribe(
      DBUS, DBUS, "NameOwnerChanged", DBUS_PATH, null, Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, params) => this.onNameOwnerChanged(params),
    )
    this.startPromise = this.listNames().then(async (names) => {
      await Promise.all(names.filter(isPlayerName).map((name) => this.hydratePlayer(name)))
    }).catch((error) => {
      console.error("audio mpris discovery failed:", error)
      throw error
    })
    return this.startPromise
  }

  private async call(destination: string, path: string, iface: string, method: string,
    parameters: GLib.Variant | null): Promise<GLib.Variant> {
    return new Promise((resolve, reject) => {
      this.connection.call(destination, path, iface, method, parameters, null, Gio.DBusCallFlags.NONE,
        10000, null, (connection, result) => {
          try {
            if (!connection) throw new Error("D-Bus call delivered no connection")
            resolve(connection.call_finish(result)) } catch (error) { reject(error) }
        })
    })
  }

  private async listNames(): Promise<string[]> {
    const reply = await this.call(DBUS, DBUS_PATH, DBUS, "ListNames", null)
    const tuple = reply.deepUnpack() as unknown[]
    return Array.isArray(tuple[0]) ? tuple[0] as string[] : []
  }
  private async getAll(busName: string): Promise<RawProps> {
    const reply = await this.call(busName, PLAYER_PATH, DBUS_PROPERTIES, "GetAll",
      new GLib.Variant("(s)", [PLAYER_IFACE]))
    return dict((reply.deepUnpack() as unknown[])[0])
  }
  private async getIdentity(busName: string): Promise<string> {
    try {
      const reply = await this.call(busName, "/org/mpris/MediaPlayer2", DBUS_PROPERTIES, "Get",
        new GLib.Variant("(ss)", [ROOT_IFACE, "Identity"]))
      return stringValue((reply.deepUnpack() as unknown[])[0])
    } catch { return "" }
  }

  private installPlayerSignals(busName: string): void {
    if (this.playerSignals.has(busName)) return
    this.generations.set(busName, (this.generations.get(busName) ?? 0) + 1)
    const generation = this.generations.get(busName)!
    const properties = this.connection.signal_subscribe(busName, DBUS_PROPERTIES, "PropertiesChanged",
      PLAYER_PATH, null, Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, params) => this.onPropertiesChanged(busName, generation, params))
    const seeked = this.connection.signal_subscribe(busName, PLAYER_IFACE, "Seeked", PLAYER_PATH,
      null, Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, params) => this.onSeeked(busName, generation, params))
    this.playerSignals.set(busName, [properties, seeked])
  }

  private hydratePlayer(busName: string): Promise<void> {
    const inFlight = this.hydration.get(busName)
    if (inFlight !== undefined) return inFlight
    this.installPlayerSignals(busName)
    const installedSignals = this.playerSignals.get(busName)
    const generation = this.generations.get(busName)
    let task!: Promise<void>
    task = (async () => {
      try {
        const [props, identity] = await Promise.all([this.getAll(busName), this.getIdentity(busName)])
        if (this.playerSignals.get(busName) !== installedSignals || this.generations.get(busName) !== generation)
          return // owner changed during reads
        const record = this.fromProps(busName, identity, props)
        this.records.set(busName, record)
        this.emit({ kind: "player-changed", player: toPlayer(record) })
      } catch (error) {
        if (this.playerSignals.get(busName) === installedSignals) this.unwatchPlayer(busName)
        console.error(`audio mpris hydration failed for ${busName}:`, error)
      } finally {
        if (this.hydration.get(busName) === task) this.hydration.delete(busName)
      }
    })()
    this.hydration.set(busName, task)
    return task
  }

  private fromProps(busName: string, identity: string, props: RawProps): PlayerRecord {
    const previous = this.records.get(busName)
    const { track: trackMeta, media } = metadata(props, previous)
    const reportedPosition = position(props.Position)
    if (reportedPosition !== null) media.positionUs = reportedPosition
    const canPlay = booleanValue(props.CanPlay)
    const canPause = booleanValue(props.CanPause)
    return {
      id: `${busName}#${this.generations.get(busName) ?? 0}`,
      busName,
      appId: canonicalIdentity(identity || parseBusName(busName).identity),
      playback: statusValue(props.PlaybackStatus),
      capabilities: { canPlay, canPause, canPlayPause: canPlay || canPause,
        canGoNext: booleanValue(props.CanGoNext), canGoPrevious: booleanValue(props.CanGoPrevious),
        canSeek: booleanValue(props.CanSeek) },
      trackMeta,
      media,
      positionSyncedAtMs: GLib.get_monotonic_time() / 1000,
    }
  }

  private onPropertiesChanged(busName: string, generation: number, params: GLib.Variant): void {
    const [iface, changedRaw, invalidatedRaw] = params.deepUnpack() as [string, unknown, string[]]
    if (iface !== PLAYER_IFACE) return
    const current = this.records.get(busName)
    // Signals can precede GetAll; the hydration snapshot will contain state.
    if (current === undefined || this.generations.get(busName) !== generation || current.id !== `${busName}#${generation}`) return
    const changed = dict(changedRaw)
    const invalidated = Array.isArray(invalidatedRaw) ? invalidatedRaw : []
    const next: PlayerRecord = { ...current, capabilities: { ...current.capabilities }, media: { ...current.media } }
    if ("PlaybackStatus" in changed) next.playback = statusValue(changed.PlaybackStatus)
    if ("Metadata" in changed) {
      const updated = metadata({ Metadata: changed.Metadata }, current)
      next.trackMeta = updated.track
      next.media = updated.media
    }
    for (const [key, field] of [
      ["CanPlay", "canPlay"], ["CanPause", "canPause"], ["CanGoNext", "canGoNext"],
      ["CanGoPrevious", "canGoPrevious"], ["CanSeek", "canSeek"],
    ] as const) if (key in changed) next.capabilities[field] = booleanValue(changed[key])
    next.capabilities.canPlayPause = next.capabilities.canPlay || next.capabilities.canPause
    if (invalidated.length > 0) {
      // Invalidated values have no payload; do a bounded property read, never poll.
      void this.refreshPlayer(busName)
      return
    }
    next.positionSyncedAtMs = GLib.get_monotonic_time() / 1000
    this.records.set(busName, next)
    this.emit({ kind: "player-changed", player: toPlayer(next) })
  }

  private async refreshPlayer(busName: string): Promise<void> {
    const expected = this.records.get(busName)
    if (expected === undefined) return
    try {
      const props = await this.getAll(busName)
      const old = this.records.get(busName)
      if (old === undefined || old.id !== expected.id) return
      const record = this.fromProps(busName, old.appId, props)
      // Identity is already canonical here; avoid changing app key on refresh.
      record.appId = old.appId
      this.records.set(busName, record)
      this.emit({ kind: "player-changed", player: toPlayer(record) })
    } catch (error) { console.debug(`audio mpris refresh failed for ${busName}:`, error) }
  }

  private onSeeked(busName: string, generation: number, params: GLib.Variant): void {
    const current = this.records.get(busName)
    if (current === undefined || this.generations.get(busName) !== generation || current.id !== `${busName}#${generation}`) return
    const next = position((params.deepUnpack() as unknown[])[0])
    if (next === null) return
    current.media.positionUs = next
    current.positionSyncedAtMs = GLib.get_monotonic_time() / 1000
    this.emit({ kind: "player-changed", player: toPlayer(current) })
  }

  private onNameOwnerChanged(params: GLib.Variant): void {
    const [name, _oldOwner, newOwner] = params.deepUnpack() as [string, string, string]
    if (!isPlayerName(name)) return
    this.remove(name)
    if (newOwner !== "") void this.hydratePlayer(name)
  }
  private unwatchPlayer(busName: string): void {
    const ids = this.playerSignals.get(busName)
    if (ids !== undefined) {
      for (const id of ids) this.connection.signal_unsubscribe(id)
      this.playerSignals.delete(busName)
    }
  }
  private remove(busName: string): void {
    this.generations.set(busName, (this.generations.get(busName) ?? 0) + 1)
    this.unwatchPlayer(busName)
    this.hydration.delete(busName)
    const previous = this.records.get(busName)
    if (this.records.delete(busName) && previous) this.emit({ kind: "player-removed", playerId: previous.id })
  }

  private async action(id: PlayerId, verb: string, seconds?: number): Promise<void> {
    const requestedId = String(id)
    const record = [...this.records.values()].find((candidate) => candidate.id === requestedId)
    if (record === undefined || this.records.get(record.busName)?.id !== requestedId)
      throw new Error(`MPRIS player is no longer current: ${requestedId}`)
    const suffix = record.busName.startsWith(MPRIS_PREFIX)
      ? record.busName.slice(MPRIS_PREFIX.length)
      : record.busName
    const args = ["playerctl", "-p", suffix, verb]
    if (seconds !== undefined) args.push(String(seconds))
    await execAsync(args)
  }
  play(id: PlayerId): Promise<void> { return this.action(id, "play") }
  pause(id: PlayerId): Promise<void> { return this.action(id, "pause") }
  playPause(id: PlayerId): Promise<void> { return this.action(id, "play-pause") }
  next(id: PlayerId): Promise<void> { return this.action(id, "next") }
  previous(id: PlayerId): Promise<void> { return this.action(id, "previous") }
  seek(id: PlayerId, positionUs: number): Promise<void> {
    if (!Number.isFinite(positionUs) || positionUs < 0) return Promise.reject(new Error("invalid MPRIS position"))
    return this.action(id, "position", positionUs / 1_000_000)
  }
}

function isPlayerName(name: string): boolean {
  return name.startsWith(MPRIS_PREFIX) && !MPRIS_EXCLUDED.includes(parseBusName(name).identity)
}

export interface ArtworkCacheOptions {
  directory?: string
  maxEntries?: number
  maxBytes?: number
  maxItemBytes?: number
}
interface CachedArtwork { localPath: string; bytes: number; usedAt: number }
const preparedArtworkDirectories = new Set<string>()

/** URI resolver with per-process LRU metadata and hard entry/byte limits. */
export class MprisArtworkAdapter {
  private readonly directory: Gio.File
  private readonly maxEntries: number
  private readonly maxBytes: number
  private readonly maxItemBytes: number
  private readonly entries = new Map<string, CachedArtwork>()
  private currentBytes = 0

  constructor(options: ArtworkCacheOptions = {}) {
    this.directory = Gio.File.new_for_path(options.directory ??
      GLib.build_filenamev([GLib.get_user_cache_dir(), "ags", "audio-artwork"]))
    this.maxEntries = Math.max(1, options.maxEntries ?? 32)
    this.maxBytes = Math.max(1, options.maxBytes ?? 24 * 1024 * 1024)
    this.maxItemBytes = Math.max(1, options.maxItemBytes ?? 4 * 1024 * 1024)
    this.prepareDirectory()
  }
  private prepareDirectory(): void {
    const path = this.directory.get_path()
    if (path === null || preparedArtworkDirectories.has(path)) return
    try {
      this.directory.make_directory_with_parents(null)
      const children = this.directory.enumerate_children("standard::name", Gio.FileQueryInfoFlags.NONE, null)
      for (let child = children.next_file(null); child !== null; child = children.next_file(null)) {
        const name = child.get_name()
        if (name) try { this.directory.get_child(name).delete(null) } catch { /* concurrently removed */ }
      }
      children.close(null)
      preparedArtworkDirectories.add(path)
    } catch (error) {
      console.debug(`MPRIS artwork cache unavailable: ${error}`)
    }
  }
  async resolve(uri: string): Promise<{ localPath: string } | null> {
    if (!uri || !/^(file|https?):/i.test(uri)) return null
    const hit = this.entries.get(uri)
    if (hit !== undefined) { hit.usedAt = Date.now(); return { localPath: hit.localPath } }
    const source = Gio.File.new_for_uri(uri)
    let target: Gio.File | null = null
    try {
      const info = await queryInfo(source)
      const bytes = info.get_size()
      if (bytes <= 0 || bytes > this.maxItemBytes || bytes > this.maxBytes) return null
      this.directory.make_directory_with_parents(null)
      const name = GLib.compute_checksum_for_string(GLib.ChecksumType.SHA256, uri, -1)
      target = this.directory.get_child(`${name}${artworkExtension(info, source)}`)
      await copyFile(source, target, this.maxItemBytes)
      const copiedInfo = await queryInfo(target)
      const copiedBytes = copiedInfo.get_size()
      if (copiedBytes <= 0 || copiedBytes > this.maxItemBytes || copiedBytes > this.maxBytes) {
        target.delete(null)
        return null
      }
      this.evictFor(copiedBytes)
      const localPath = target.get_path()
      if (!localPath) return null
      this.entries.set(uri, { localPath, bytes: copiedBytes, usedAt: Date.now() })
      this.currentBytes += copiedBytes
      return { localPath }
    } catch (error) {
      if (target !== null) try { target.delete(null) } catch { /* partial file absent */ }
      console.debug(`MPRIS artwork unavailable: ${error}`)
      return null
    }
  }
  private evictFor(bytes: number): void {
    while (this.entries.size >= this.maxEntries || this.currentBytes + bytes > this.maxBytes) {
      const oldest = [...this.entries.entries()].sort((a, b) => a[1].usedAt - b[1].usedAt)[0]
      if (!oldest) return
      this.entries.delete(oldest[0])
      this.currentBytes -= oldest[1].bytes
      try { Gio.File.new_for_path(oldest[1].localPath).delete(null) } catch { /* stale cache file */ }
    }
  }
}

function queryInfo(file: Gio.File): Promise<Gio.FileInfo> {
  return new Promise((resolve, reject) => file.query_info_async(
    "standard::size,standard::content-type,standard::name", Gio.FileQueryInfoFlags.NONE,
    GLib.PRIORITY_DEFAULT, null, (source, result) => {
      try {
        if (!source) throw new Error("query_info_async delivered no source object")
        resolve(source.query_info_finish(result)) } catch (error) { reject(error) }
    }))
}
function copyFile(source: Gio.File, target: Gio.File, maxBytes: number): Promise<void> {
  const cancellable = new Gio.Cancellable()
  // copy_async takes SIX arguments. A seventh (a stray `null`) throws
  // TypeError at the call site, so every artwork copy failed and rows silently
  // fell back to the app icon. Caught by the 6.5 typecheck gate, not by any
  // runtime test -- there is no live artwork test in this change.
  return new Promise((resolve, reject) => source.copy_async(
    target, Gio.FileCopyFlags.OVERWRITE, GLib.PRIORITY_DEFAULT, cancellable,
    (currentBytes) => { if (currentBytes > maxBytes) cancellable.cancel() },
    (file, result) => {
      try {
        if (!file) throw new Error("copy_async delivered no source object")
        file.copy_finish(result); resolve() } catch (error) {
        try { target.delete(null) } catch { /* partial target absent */ }
        reject(error)
      }
    }))
}
function artworkExtension(info: Gio.FileInfo, source: Gio.File): string {
  const name = info.get_name() ?? source.get_basename() ?? ""
  return name.match(/\.[a-zA-Z0-9]{1,8}$/)?.[0] ?? ".img"
}
