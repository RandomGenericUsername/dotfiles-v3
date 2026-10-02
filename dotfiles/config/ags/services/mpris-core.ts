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
  //: Tidal's root `Identity` is "Tidal Hi-Fi" while its bus name is
  //: `tidal-hifi`; without folding, the two interfaces of the one app would not
  //: share a canonical key (they still collapse by PID, but the alias keeps
  //: identity-based matching honest).
  "tidal-hi-fi": "tidal-hifi",
  tidal: "tidal-hifi",
  "brave-browser": "brave-browser",
  firefox: "firefox",
  //: Measured live: Firefox's MPRIS root `Identity` is "Mozilla firefox" while
  //: its PipeWire stream reports `application.name = "Firefox"` /
  //: `application.process.binary = "firefox"`. Without this fold the two sides
  //: canonicalise to DIFFERENT keys (`firefox` vs `mozilla-firefox`), so the
  //: Applications list showed the same playback twice — one row with the
  //: volume/routing controls and no transport, one with the transport and a
  //: dead `—` volume line. Folding them is what makes Tidal's single clean row
  //: the rule for every app, not just the ones already in this table.
  "mozilla-firefox": "firefox",
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
  /** `xesam:url` — the media's own locator. Firefox/YouTube report it, and it is
   *  the only STABLE per-track identity available: `mpris:trackid` is a dummy
   *  (`/org/mpris/MediaPlayer2/firefox`, identical for every track a tab plays),
   *  so it cannot tell two videos apart. Carried so a duration can be remembered
   *  against the track it belongs to. */
  url: string
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
  const length = normaliseLength(rawGet(raw, "mpris:length"))
  return {
    title: asString(rawGet(raw, "xesam:title")),
    artist: asArtist(rawGet(raw, "xesam:artist")),
    album: asString(rawGet(raw, "xesam:album")),
    lengthUs: length,
    url: asString(rawGet(raw, "xesam:url")),
  }
}

/**
 * Do two metadata snapshots describe the same track?
 *
 * `mpris:trackid` cannot answer this (it is a per-PLAYER dummy on Firefox and on
 * Chromium alike), so the media's own locator is the primary key: `xesam:url` is
 * exact when the app publishes it. A title is a weak fallback — good enough to
 * keep a duration while an app re-announces the same track, never strong enough
 * to carry one across genuinely different media.
 */
export function isSameTrack(a: TrackMeta, b: TrackMeta): boolean {
  if (a.url !== "" && b.url !== "") return a.url === b.url
  if (a.title !== "" && b.title !== "") return a.title === b.title
  return false
}

/**
 * Keep a known duration when a re-announcement drops it.
 *
 * Apps publish `mpris:length` once and then re-announce `Metadata` without it —
 * measured on this machine: Firefox reported `mpris:length = 1043000000` for a
 * YouTube track, then emitted the SAME track (identical `xesam:url` and title)
 * with the key simply absent. Taking that at face value dropped the duration to
 * "unknown", which is what made the seek slider disappear from under the user
 * after one seek — the only way back was pausing and resuming the app.
 *
 * A duration is a property of the TRACK, not of the announcement, so a dropped
 * one is carried forward for as long as the re-announcement still names the same
 * track. A genuinely new track (different url, or a different title when no url
 * is published) is never given the old duration — inheriting one would put the
 * seek slider on a timeline that belongs to different media, which is the exact
 * failure this guards against.
 */
export function carryDuration(next: TrackMeta, previous: TrackMeta | null | undefined): TrackMeta {
  if (next.lengthUs > 0 || previous === null || previous === undefined) return next
  if (previous.lengthUs <= 0) return next
  if (!isSameTrack(next, previous)) return next
  return { ...next, lengthUs: previous.lengthUs }
}

//: `m:ss`; `""` when there is no known positive duration (WP-B contract §5).
export function formatClock(us: number): string {
  if (!Number.isFinite(us) || us <= 0) return ""
  const totalSeconds = Math.floor(us / 1_000_000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

/** A sane upper bound on a track length (24h, in µs). Players that do not know
 *  the duration report `mpris:length = INT64_MAX` (9223372036854775807 µs ≈
 *  292,471 years), which otherwise renders as `153722867280:54` and also trips
 *  GJS's "cannot be safely stored in a JS Number" warning on unpack. Anything
 *  beyond this bound is treated as "unknown duration". */
export const MAX_TRACK_LENGTH_US = 24 * 60 * 60 * 1_000_000

/** Coerce a raw `mpris:length` (int64 µs) to a usable duration, or 0 when it is
 *  missing, non-positive, or the INT64_MAX "unknown" sentinel. */
export function normaliseLength(value: unknown): number {
  const length = Number(value)
  if (!Number.isFinite(length) || length <= 0) return 0
  if (length > MAX_TRACK_LENGTH_US) return 0
  return length
}

/** Coerce a raw `Position` (int64 µs) to a usable value, or the fallback when it
 *  is missing, negative, or the INT64_MAX "unknown" sentinel. */
export function normalisePosition(value: unknown, fallback: number): number {
  const position = Number(value)
  if (!Number.isFinite(position) || position < 0) return fallback
  if (position > MAX_TRACK_LENGTH_US) return fallback
  return position
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

// ── App identity resolution (one row per real app) ─────────────────────────
//
// The Applications list is built from TWO sources that name the same app
// differently: a PipeWire stream (`application.name` / `application.process.binary`)
// and an MPRIS player (`Identity`). Both sides canonicalise independently, so
// whenever the two spellings differ the union produced by the popup shows the
// SAME playback twice: one row carrying the volume/routing controls and no
// transport, one carrying the transport and a dead `—` volume line. Measured:
// stream `Firefox` → key `firefox`, player `Identity "Mozilla firefox"` → key
// `mozilla-firefox`. Tidal looked fine purely because its spellings already
// fold onto one key.
//
// `resolveAppIdentities` is the seam that makes that impossible: for a player
// whose canonical key is not already claimed by a stream, it asks the host
// which live stream it belongs to and yields the STREAM's key. The row is then
// keyed by that key, and every per-app read (stream lookup, transport, volume,
// routing) resolves through the SAME key — so the row is unified by
// construction rather than by coincidence of a maintained alias table.
//
// Pure by construction: it takes a resolver callback, so the whole rule is
// node-testable here (I11) and the GJS side only supplies the closure.

/** Host seam: does a live stream claim this identity? Supplied by the audio
 *  state, which owns the PipeWire graph; kept as a callback so this core stays
 *  free of GJS imports. */
export type AppIdentityResolver = (identity: string) => string[]

/**
 * Canonical app keys for one MPRIS player, most specific first.
 *
 * `taken` are the keys already claimed by a live playback stream. A player's own
 * canonical key is normally one of them, or folds onto one (`ALIAS`); only when
 * it does not — the spelling genuinely differs — is the resolver consulted.
 * `identity` (the raw root property) is offered to the resolver as well as the
 * canonical form, so a host matcher can use whichever it understands.
 */
export function resolveAppIdentities(
  player: { identity: string; canonical: string },
  taken: Set<string>,
  resolve?: AppIdentityResolver,
): string[] {
  if (taken.has(player.canonical)) return [player.canonical]
  const candidates: string[] = []
  //: Bound to a local so the call site reads as one seam (`ask`) — and so the
  //: repo's symbol checker resolves it as a definition rather than a free
  //: identifier (it only harvests simple `(a, b) =>` params).
  const ask = resolve
  if (ask !== undefined) {
    for (const identity of [player.canonical, player.identity]) {
      if (identity === "") continue
      for (const key of ask(identity) ?? []) {
        if (key !== "" && !candidates.includes(key)) candidates.push(key)
      }
    }
  }
  if (candidates.length === 0) return [player.canonical]
  //: The canonical key stays as a fallback so `playerForApp(<canonical>)` keeps
  //: working for a caller that only knows the player's own spelling — but only
  //: when the resolver did not already hand it back.
  if (!candidates.includes(player.canonical)) candidates.push(player.canonical)
  return candidates
}

/** The row key an app row uses (I1: a stable identity, never an object). */
export function keyForPlayer(
  player: { identity: string; canonical: string },
  taken: Set<string>,
  resolve?: AppIdentityResolver,
): string {
  return resolveAppIdentities(player, taken, resolve)[0]
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
