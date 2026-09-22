// Pure core for the AGS MPRIS transport service (WP-B).
//
// MPRIS lives on the session bus; `mpris-service.ts` owns the Gio transport and
// the reactive state, while everything decidable from a plain value lives here.
// Keeping this module free of GJS imports (invariant I11) lets the existing ICME
// node runner exercise it without a live bus — see
// `src/gui-tools/icon-color-mapping-editor/tests/mpris-core.test.mjs`.
//
// The literals and shapes below are the WP-B contract in
// `_bmad-output/planning-artifacts/ags-audio-mpris-transport-dispatch-contract-2026-09-21.md`
// §5; change them there first.

export const MPRIS_PREFIX = "org.mpris.MediaPlayer2."

//: `playerctld` is an activatable proxy that mirrors whichever player the daemon
//: last saw. It is never a row and never the master player (WP-B contract §5).
export const MPRIS_EXCLUDED = ["playerctld"]

//: MPRIS identities are frequently the *framework* (Chromium hosts Chrome, the
//: YouTube Music PWA, …), while the PipeWire stream carries the brand name. Map
//: the observed identities into the icon-name slug space so `identityMatches`
//: can link a stream row to its player. Unknown identities pass through.
export const ALIAS: Record<string, string> = {
  chromium: "google-chrome",
  chrome: "google-chrome",
  "google-chrome": "google-chrome",
  "tidal-hifi": "tidal-hifi",
  "brave-browser": "brave-browser",
  firefox: "firefox",
  spotify: "spotify",
  "youtube-music": "youtube-music",
}

export interface ParsedBusName {
  identity: string
  instance: string | null
}

//: `org.mpris.MediaPlayer2.chromium.instance4925` → identity `chromium`,
//: instance `4925`; a singleton player carries no `.instanceN` suffix.
export function parseBusName(busName: string): ParsedBusName {
  const suffix = busName.startsWith(MPRIS_PREFIX)
    ? busName.slice(MPRIS_PREFIX.length)
    : busName
  const match = suffix.match(/^(.*)\.instance([0-9]+)$/)
  if (match === null) return { identity: suffix.toLowerCase(), instance: null }
  return { identity: match[1].toLowerCase(), instance: match[2] }
}

export interface TrackMeta {
  title: string
  artist: string
  album: string
  lengthUs: number
}

//: Reader for `a{sv}` dicts: `recursiveUnpack` yields a plain object, but a
//: Map is also accepted so the core stays transport-agnostic.
function rawGet(raw: Record<string, unknown>, key: string): unknown {
  if (raw instanceof Map) return (raw as Map<string, unknown>).get(key)
  return raw[key]
}

function asString(value: unknown): string {
  if (typeof value === "string") return value
  return value === null || value === undefined ? "" : String(value)
}

//: `xesam:artist` is the one MPRIS field carried as an array (`as`); flatten it
//: into the single display string `TrackMeta.artist` promises.
function asArtist(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((entry) => asString(entry))
      .filter((entry) => entry !== "")
      .join(", ")
  }
  return asString(value)
}

//: MPRIS Metadata is `a{sv}`; every key is optional (a player may publish no
//: metadata at all). Missing/ill-typed values degrade to safe empty defaults so
//: the UI never renders `undefined`.
export function parseMetadata(raw: Record<string, unknown>): TrackMeta {
  const length = Number(rawGet(raw, "mpris:length") ?? 0)
  return {
    title: asString(rawGet(raw, "xesam:title")),
    artist: asArtist(rawGet(raw, "xesam:artist")),
    album: asString(rawGet(raw, "xesam:album")),
    lengthUs: Number.isFinite(length) && length > 0 ? length : 0,
  }
}

//: `m:ss`; `""` when there is no known positive duration (WP-B contract §5).
export function formatClock(us: number): string {
  if (!Number.isFinite(us) || us <= 0) return ""
  const totalSeconds = Math.floor(us / 1_000_000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

//: Display-only position extrapolation (invariant I1: a render tick may
//: interpolate locally, never re-read authoritative state). A clock that moved
//: backwards (or a `nowMs` before `baseMs`) clamps to the base so the slider
//: never runs negative.
export function interpolatePosition(
  baseUs: number,
  baseMs: number,
  playing: boolean,
  nowMs: number,
): number {
  if (!playing) return baseUs
  const elapsedMs = Math.max(0, nowMs - baseMs)
  return baseUs + elapsedMs * 1000
}

//: Slug both sides (lowercase, non-alphanumeric runs → `-`) before comparing;
//: BOTH the identity and each candidate pass through `ALIAS`, so a framework
//: identity (`chromium`) links to either the brand stream (`google-chrome`) or
//: the process binary (`chrome`) — the two candidate fields the graph snapshot
//: supplies. This is how a stream row finds its player.
function normaliseToken(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

//: Canonicalise a slug through `ALIAS` so equivalent names collapse
//: (`chromium`/`chrome`/`google-chrome` → `google-chrome`).
function canonicalToken(value: string): string {
  const normalised = normaliseToken(value)
  if (normalised === "") return ""
  return ALIAS[normalised] ?? normalised
}

/** The canonical app key for an MPRIS identity.
 *
 *  Two Chrome windows expose two players that both report `chromium` and are
 *  otherwise indistinguishable, so the UI collapses them by this key rather than
 *  showing a duplicate row. Also folds framework/brand spellings together
 *  (`chromium`/`chrome`/`google-chrome` → `google-chrome`). */
export function canonicalIdentity(identity: string): string {
  return canonicalToken(identity)
}

export function identityMatches(identity: string, candidates: string[]): boolean {
  const base = canonicalToken(identity)
  if (base === "") return false
  return candidates.some((candidate) => canonicalToken(candidate) === base)
}

//: The master-button target (D1): the most recently *playing* player; if none
//: is playing, the most recently active *non-stopped* player (a paused player is
//: still a real target — a stopped one is not, and must never outrank it just
//: because it carries a stale timestamp); otherwise the most recently active
//: overall; otherwise the first. Strict `>` keeps the earliest entry on a tie,
//: so the choice is deterministic.
//
//: Within the chosen tier, a player that carries track metadata outranks one
//: that does not: two Chrome windows can both be Paused with no play history,
//: and the empty one must not hide the one that is actually showing a track.
export function pickActivePlayer<
  T extends { identity: string; status: string; lastPlayingAt: number },
>(players: T[]): T | null {
  if (players.length === 0) return null
  const playing = players.filter((player) => player.status === "Playing")
  const live = players.filter((player) => player.status !== "Stopped")
  const pool = playing.length > 0 ? playing : live.length > 0 ? live : players
  const hasTrack = (player: T): boolean => {
    const title = (player as { metadata?: { title?: string } }).metadata?.title
    return typeof title === "string" && title !== ""
  }
  let best = pool[0]
  for (const player of pool) {
    if (player.lastPlayingAt > best.lastPlayingAt) best = player
    else if (player.lastPlayingAt === best.lastPlayingAt && hasTrack(player) && !hasTrack(best)) {
      best = player
    }
  }
  return best
}
