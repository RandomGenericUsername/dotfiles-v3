// MPRIS pure-core tests (WP-B).
//
// Cross-package note: the AGS bar has no node test runner of its own, so its
// pure MPRIS core (`dotfiles/config/ags/services/mpris-core.ts`) is imported
// here and executed by the existing ICME node runner, exactly as
// `event-contract-drift.mjs` imports `lib/event-bus-core.ts`.
//
//   node tests/mpris-core.test.mjs   (from the tool directory)

import * as mpris from "../../../../dotfiles/config/ags/services/mpris-core.ts";

let failures = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    failures += 1;
    console.error(`FAIL ${name}\n  expected: ${e}\n  actual:   ${a}`);
  } else {
    console.log(`ok ${name}`);
  }
}

// ── Bus-name parsing ─────────────────────────────────────────────────────

check("mpris prefix", mpris.MPRIS_PREFIX, "org.mpris.MediaPlayer2.");
check("excluded list", mpris.MPRIS_EXCLUDED, ["playerctld"]);
check(
  "parse with instance",
  mpris.parseBusName("org.mpris.MediaPlayer2.chromium.instance4925"),
  { identity: "chromium", instance: "4925" },
);
check(
  "parse without instance",
  mpris.parseBusName("org.mpris.MediaPlayer2.tidal-hifi"),
  { identity: "tidal-hifi", instance: null },
);
check(
  "parse lowercases identity",
  mpris.parseBusName("org.mpris.MediaPlayer2.Firefox.instance7"),
  { identity: "firefox", instance: "7" },
);
check(
  "parse excluded playerctld",
  mpris.parseBusName("org.mpris.MediaPlayer2.playerctld"),
  { identity: "playerctld", instance: null },
);

// ── Alias mapping ────────────────────────────────────────────────────────

check("alias chromium", mpris.ALIAS.chromium, "google-chrome");
check("alias chrome", mpris.ALIAS.chrome, "google-chrome");
check("alias google-chrome", mpris.ALIAS["google-chrome"], "google-chrome");
check("alias tidal-hifi", mpris.ALIAS["tidal-hifi"], "tidal-hifi");
check("alias brave-browser", mpris.ALIAS["brave-browser"], "brave-browser");
check("alias firefox", mpris.ALIAS.firefox, "firefox");
//: Measured live: the stream says "Firefox", the MPRIS root Identity says
//: "Mozilla firefox". Unfolded, the popup listed the same playback twice.
check("alias mozilla-firefox → firefox", mpris.ALIAS["mozilla-firefox"], "firefox");
check("alias spotify", mpris.ALIAS.spotify, "spotify");
check("alias youtube-music", mpris.ALIAS["youtube-music"], "youtube-music");

// ── Metadata parsing ─────────────────────────────────────────────────────

check("metadata missing keys default", mpris.parseMetadata({}), {
  title: "",
  artist: "",
  album: "",
  lengthUs: 0,
  url: "",
});
check(
  "metadata full values",
  mpris.parseMetadata({
    "xesam:title": "Song",
    "xesam:artist": ["A", "B"],
    "xesam:album": "Album",
    "mpris:length": 4_020_000,
    "xesam:url": "https://example.test/watch?v=1",
  }),
  {
    title: "Song",
    artist: "A, B",
    album: "Album",
    lengthUs: 4_020_000,
    url: "https://example.test/watch?v=1",
  },
);
check(
  "metadata artist string tolerated",
  mpris.parseMetadata({ "xesam:artist": "Solo" }).artist,
  "Solo",
);
check(
  "metadata non-positive length clamped",
  mpris.parseMetadata({ "mpris:length": -5 }).lengthUs,
  0,
);

// ── formatClock ──────────────────────────────────────────────────────────

check("clock zero", mpris.formatClock(0), "");
check("clock negative", mpris.formatClock(-1), "");
check("clock under a minute", mpris.formatClock(30_000_000), "0:30");
check("clock mm:ss", mpris.formatClock(84_000_000), "1:24");
check("clock over ten minutes", mpris.formatClock(605_000_000), "10:05");
check("clock floors sub-second", mpris.formatClock(999_999), "0:00");

// ── interpolatePosition ──────────────────────────────────────────────────

check(
  "interpolate playing",
  mpris.interpolatePosition(1_000_000, 1000, true, 3000),
  3_000_000,
);
check(
  "interpolate paused freezes",
  mpris.interpolatePosition(1_000_000, 1000, false, 3000),
  1_000_000,
);
check(
  "interpolate zero elapsed",
  mpris.interpolatePosition(2_000_000, 5000, true, 5000),
  2_000_000,
);
check(
  "interpolate clamps negative elapsed",
  mpris.interpolatePosition(2_000_000, 5000, true, 4000),
  2_000_000,
);

// ── length/position sentinels (INT64_MAX = "unknown") ────────────────────

//: Chrome reports mpris:length = INT64_MAX when the duration is unknown; it
//: otherwise renders as `153722867280:54` and trips a GJS int64 warning.
check("length INT64_MAX → unknown", mpris.normaliseLength(9223372036854775807), 0);
check("length real value kept", mpris.normaliseLength(292385000), 292385000);
check("length zero → unknown", mpris.normaliseLength(0), 0);
check("length negative → unknown", mpris.normaliseLength(-5), 0);
check("length undefined → unknown", mpris.normaliseLength(undefined), 0);
check("position INT64_MAX → fallback", mpris.normalisePosition(9223372036854775807, 7), 7);
check("position negative → fallback", mpris.normalisePosition(-1, 7), 7);
check("position real value kept", mpris.normalisePosition(1000, 7), 1000);

// ── canonicalIdentity (apps-row collapsing) ──────────────────────────────

//: Two Chrome windows expose two MPRIS players that are indistinguishable
//: (`identity === "chromium"`); the UI collapses them by this key so the user
//: never sees a duplicate Chrome row. Framework/brand spellings all fold here.
check("canonical chromium → google-chrome", mpris.canonicalIdentity("chromium"), "google-chrome");
check("canonical chrome → google-chrome", mpris.canonicalIdentity("chrome"), "google-chrome");
check("canonical google-chrome stays", mpris.canonicalIdentity("google-chrome"), "google-chrome");
check("canonical tidal-hifi stays", mpris.canonicalIdentity("tidal-hifi"), "tidal-hifi");
check("canonical Tidal Hi-Fi folds", mpris.canonicalIdentity("Tidal Hi-Fi"), "tidal-hifi");
check("canonical empty is empty", mpris.canonicalIdentity(""), "");

// ── identityMatches ──────────────────────────────────────────────────────

check(
  "identity chromium links google-chrome",
  mpris.identityMatches("chromium", ["google-chrome"]),
  true,
);
//: The graph snapshot supplies BOTH `application.name` (Google Chrome) and
//: `application.process.binary` (chrome); a candidate must match through ALIAS
//: on either side, so `chromium` links a lone binary candidate too.
check(
  "identity chromium links process binary chrome",
  mpris.identityMatches("chromium", ["chrome"]),
  true,
);
check(
  "identity chromium links either candidate field",
  mpris.identityMatches("chromium", ["chrome", "google-chrome"]),
  true,
);
check(
  "identity chrome links google-chrome",
  mpris.identityMatches("chrome", ["google-chrome"]),
  true,
);
check(
  "identity case/punctuation",
  mpris.identityMatches("Google Chrome", ["google-chrome"]),
  true,
);
check(
  "identity candidate punctuation",
  mpris.identityMatches("google-chrome", ["Google_Chrome"]),
  true,
);
check(
  "identity no match",
  mpris.identityMatches("chromium", ["spotify"]),
  false,
);
check("identity empty candidates", mpris.identityMatches("chromium", []), false);

// ── pickActivePlayer ─────────────────────────────────────────────────────

check("pick empty", mpris.pickActivePlayer([]), null);
check(
  "pick most recent playing over newer paused",
  mpris.pickActivePlayer([
    { identity: "chromium", status: "Paused", lastPlayingAt: 500 },
    { identity: "tidal-hifi", status: "Playing", lastPlayingAt: 100 },
  ]),
  { identity: "tidal-hifi", status: "Playing", lastPlayingAt: 100 },
);
check(
  "pick highest lastPlayingAt among playing",
  mpris.pickActivePlayer([
    { identity: "a", status: "Playing", lastPlayingAt: 100 },
    { identity: "b", status: "Playing", lastPlayingAt: 200 },
  ]).identity,
  "b",
);
check(
  "pick falls back to newest non-playing",
  mpris.pickActivePlayer([
    { identity: "a", status: "Paused", lastPlayingAt: 100 },
    { identity: "b", status: "Paused", lastPlayingAt: 200 },
  ]).identity,
  "b",
);
//: Regression (found live, WP-F): a STOPPED player must never outrank a live
//: (paused) one merely because it carries a stale `lastPlayingAt` — the stopped
//: Chromium instance was selected over the playing tidal, so `next`/`previous`
//: were sent to a player that could not handle them.
check(
  "pick prefers paused over stopped despite stale timestamp",
  mpris.pickActivePlayer([
    { identity: "tidal-hifi", status: "Paused", lastPlayingAt: 100 },
    { identity: "chromium", status: "Stopped", lastPlayingAt: 999 },
  ]).identity,
  "tidal-hifi",
);
check(
  "pick falls back to stopped only when all are stopped",
  mpris.pickActivePlayer([
    { identity: "a", status: "Stopped", lastPlayingAt: 100 },
    { identity: "b", status: "Stopped", lastPlayingAt: 200 },
  ]).identity,
  "b",
);
//: Two Chrome windows can both be Paused with no play history; the empty one
//: must not hide the one showing a track (the reported duplicate-Chrome row
//: showed an empty title because the first instance won the tie).
check(
  "pick prefers the tied player with metadata",
  mpris.pickActivePlayer([
    { identity: "chromium", status: "Paused", lastPlayingAt: 0, metadata: { title: "" } },
    { identity: "chromium", status: "Paused", lastPlayingAt: 0, metadata: { title: "Air" } },
  ]).metadata.title,
  "Air",
);
check(
  "pick tie keeps first",
  mpris.pickActivePlayer([
    { identity: "a", status: "Paused", lastPlayingAt: 100 },
    { identity: "b", status: "Paused", lastPlayingAt: 100 },
  ]).identity,
  "a",
);

// ── resolveAppIdentities / keyForPlayer (one row per real app) ───────────
//
// The reported duplicate row: one playback, two names. The stream claims
// `firefox`; the player's root Identity is "Mozilla firefox". Without
// resolution the Applications list unioned both keys into two rows — one with
// the volume/routing controls and no transport, one with the transport and a
// dead `—` volume line.

const firefoxPlayer = { identity: "Mozilla firefox", canonical: "mozilla-firefox" };
//: A resolver shaped like the one audio/state.ts installs: given an identity,
//: the canonical app keys of the live streams that claim it (matched through
//: ALIAS against the stream's `application.name` / process binary).
const streamClaims = (claims) => (identity) => {
  const keys = [];
  for (const [key, candidates] of Object.entries(claims)) {
    if (candidates.some((candidate) => mpris.identityMatches(identity, [candidate]))) {
      keys.push(key);
    }
  }
  return keys;
};

check(
  "unclaimed key folds through ALIAS to the stream's key",
  mpris.keyForPlayer(firefoxPlayer, new Set(), streamClaims({ firefox: ["firefox"] })),
  "firefox",
);
check(
  "an already-claimed key is used verbatim (resolver not consulted)",
  mpris.keyForPlayer(
    { identity: "Tidal Hi-Fi", canonical: "tidal-hifi" },
    new Set(["tidal-hifi"]),
    () => {
      throw new Error("resolver must not run for a claimed key");
    },
  ),
  "tidal-hifi",
);
//: A player whose app has no stream at all keeps its own key — a player-only row
//: (D8) must still appear, and must not be folded into an unrelated app.
check(
  "player with no stream keeps its own canonical key",
  mpris.keyForPlayer(
    { identity: "Discord", canonical: "discord" },
    new Set(["firefox"]),
    streamClaims({ firefox: ["firefox"] }),
  ),
  "discord",
);
check(
  "no resolver installed keeps the canonical key",
  mpris.keyForPlayer(firefoxPlayer, new Set()),
  "mozilla-firefox",
);
check(
  "an empty identity never matches",
  mpris.keyForPlayer({ identity: "", canonical: "" }, new Set(), streamClaims({ firefox: ["firefox"] })),
  "",
);
//: Both spellings offered to the resolver: the raw Identity AND the canonical
//: form, so a host matcher may use either. Duplicates collapse, order preserved.
check(
  "resolve returns the stream key first, canonical as fallback",
  mpris.resolveAppIdentities(firefoxPlayer, new Set(), streamClaims({ firefox: ["Firefox", "firefox"] })),
  ["firefox", "mozilla-firefox"],
);
check(
  "resolve dedupes a resolver that answers twice",
  mpris.resolveAppIdentities(
    { identity: "chromium", canonical: "google-chrome" },
    new Set(),
    () => ["google-chrome", "google-chrome"],
  ),
  ["google-chrome"],
);
check("resolve without a resolver is the canonical key", mpris.resolveAppIdentities(firefoxPlayer, new Set()), [
  "mozilla-firefox",
]);

// ── isSameTrack / carryDuration (a duration belongs to the TRACK) ─────────
//
// Measured: Firefox published `mpris:length = 1043000000` for a YouTube track,
// then re-announced the SAME track (identical `xesam:url` and title) with the key
// absent. Read literally that is "duration unknown", which is what removed the
// seek slider from under the user mid-playback.

const track = (over) => ({
  title: "Garuda Linux GNOME came!",
  artist: "",
  album: "",
  lengthUs: 0,
  url: "https://www.youtube.com/watch?v=Wk2rTYhn71I",
  ...over,
});
const known = track({ lengthUs: 1_043_000_000 });

check(
  "same track by url even when the title moved on",
  mpris.isSameTrack(known, track({ title: "renamed by the site" })),
  true,
);
check(
  "different url is a different track",
  mpris.isSameTrack(known, track({ url: "https://www.youtube.com/watch?v=other" })),
  false,
);
check(
  "no url falls back to the title",
  mpris.isSameTrack(
    { title: "Song", artist: "", album: "", lengthUs: 0, url: "" },
    { title: "Song", artist: "", album: "", lengthUs: 0, url: "" },
  ),
  true,
);
check(
  "no url and a different title is a different track",
  mpris.isSameTrack(
    { title: "Song", artist: "", album: "", lengthUs: 0, url: "" },
    { title: "Other", artist: "", album: "", lengthUs: 0, url: "" },
  ),
  false,
);
//: Neither side names the track → no opinion, so nothing is carried across.
check(
  "unidentifiable tracks are never the same",
  mpris.isSameTrack(track({ url: "", title: "" }), track({ url: "", title: "" })),
  false,
);

check(
  "dropped length is carried forward for the same track",
  mpris.carryDuration(track({}), known).lengthUs,
  1_043_000_000,
);
check(
  "a new track inherits nothing",
  mpris.carryDuration(track({ url: "https://www.youtube.com/watch?v=other" }), known).lengthUs,
  0,
);
check(
  "an announced length always wins",
  mpris.carryDuration(track({ lengthUs: 5_000 }), known).lengthUs,
  5_000,
);
check(
  "no previous metadata to carry from",
  mpris.carryDuration(track({}), null).lengthUs,
  0,
);
check(
  "carry is per-track, not global: a second video starts unknown",
  mpris.carryDuration(track({ url: "https://www.youtube.com/watch?v=second" }), track({ lengthUs: 0, url: "https://www.youtube.com/watch?v=second" }))
    .lengthUs,
  0,
);

if (failures > 0) {
  console.error(`${failures} assertion(s) failed`);
  process.exitCode = 1;
} else {
  console.log("mpris core agrees");
}
