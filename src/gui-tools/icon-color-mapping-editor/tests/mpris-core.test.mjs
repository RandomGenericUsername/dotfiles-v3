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
check("alias spotify", mpris.ALIAS.spotify, "spotify");
check("alias youtube-music", mpris.ALIAS["youtube-music"], "youtube-music");

// ── Metadata parsing ─────────────────────────────────────────────────────

check("metadata missing keys default", mpris.parseMetadata({}), {
  title: "",
  artist: "",
  album: "",
  lengthUs: 0,
});
check(
  "metadata full values",
  mpris.parseMetadata({
    "xesam:title": "Song",
    "xesam:artist": ["A", "B"],
    "xesam:album": "Album",
    "mpris:length": 4_020_000,
  }),
  { title: "Song", artist: "A, B", album: "Album", lengthUs: 4_020_000 },
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
check(
  "pick tie keeps first",
  mpris.pickActivePlayer([
    { identity: "a", status: "Paused", lastPlayingAt: 100 },
    { identity: "b", status: "Paused", lastPlayingAt: 100 },
  ]).identity,
  "a",
);

if (failures > 0) {
  console.error(`${failures} assertion(s) failed`);
  process.exitCode = 1;
} else {
  console.log("mpris core agrees");
}
