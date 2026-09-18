// Unit tests for lib/model.ts. Run with plain node:
// `node tests/model.mjs` from the tool directory.
import {
  buildModel,
  cachedContrastPref,
  contrastScopeLabel,
  DEFAULT_CONTRAST_ENABLED,
  filterWallpapers,
  isImageFile,
  isRealHash,
  isWallpaperLive,
  mapSpineHashes,
  needsRealHash,
  pinTargetHash,
  resolvePlaceholders,
  stemOf,
  unappliedPlaceholder,
  UNAPPLIED_PREFIX,
  variantsFor,
} from "../lib/model.ts";

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

const SPINE = [
  { name: "shani.png", path: "/spine/shani.png", hash: "s".repeat(64) },
  { name: "imperial_eagle.jpg", path: "/spine/imperial_eagle.jpg", hash: "i".repeat(64) },
  { name: "test.txt", path: "/spine/test.txt", hash: "t".repeat(64) },
  { name: "black_dragon.webp", path: "/spine/black_dragon.webp", hash: "b".repeat(64) },
];

const EFFECTS = [
  {
    sourceHash: "i".repeat(64),
    variants: [
      { name: "sepia", group: "effect", path: "/cache/e1/imperial/effect/sepia.jpg" },
      { name: "blur", group: "effect", path: "/cache/e1/imperial/effect/blur.jpg" },
      { name: "blur", group: "preset", path: "/cache/e1/imperial/preset/blur.jpg" },
    ],
  },
];

const CURRENT_WALL = { wallpaperHash: "i".repeat(64), wallpaperPath: "/spine/imperial_eagle.jpg" };
const CURRENT_VAR = {
  wallpaperHash: "v".repeat(64),
  wallpaperPath: "/cache/e1/imperial/effect/sepia.jpg",
};

// image filtering + name sorting
{
  const m = buildModel(SPINE, [], null);
  check("non-images excluded", m.wallpapers.map((w) => w.name), [
    "black_dragon.webp",
    "imperial_eagle.jpg",
    "shani.png",
  ]);
}

// variant grouping + counts + sort (group, name)
{
  const m = buildModel(SPINE, EFFECTS, CURRENT_WALL);
  const imp = m.wallpapers.find((w) => w.name === "imperial_eagle.jpg");
  check("variant count", imp.variantCount, 3);
  check(
    "variants sorted",
    variantsFor(m, "i".repeat(64)).map((v) => `${v.group}/${v.name}`),
    ["effect/blur", "effect/sepia", "preset/blur"],
  );
  const shani = m.wallpapers.find((w) => w.name === "shani.png");
  check("variantless count", shani.variantCount, 0);
  check("variantless list", variantsFor(m, "s".repeat(64)), []);
}

// live wallpaper
{
  const m = buildModel(SPINE, EFFECTS, CURRENT_WALL);
  check(
    "live wallpaper",
    m.wallpapers.filter((w) => w.live).map((w) => w.name),
    ["imperial_eagle.jpg"],
  );
  check("no live variant", variantsFor(m, "i".repeat(64)).some((v) => v.live), false);
  check("live hash", m.liveWallpaperHash, "i".repeat(64));
}

// live variant (promoted): parent not live, variant live by source path
{
  const m = buildModel(SPINE, EFFECTS, CURRENT_VAR);
  check("parent not live", m.wallpapers.some((w) => w.live), false);
  const live = variantsFor(m, "i".repeat(64)).filter((v) => v.live);
  check("variant live by path", live.map((v) => v.name), ["sepia"]);
  check("live variant path", m.liveVariantPath, "/cache/e1/imperial/effect/sepia.jpg");
}

// no current state: nothing live
{
  const m = buildModel(SPINE, EFFECTS, null);
  check("nothing live without current", m.wallpapers.some((w) => w.live), false);
  check("empty live hash", m.liveWallpaperHash, "");
}

// filtering
{
  const m = buildModel(SPINE, EFFECTS, null);
  check("empty query returns all", filterWallpapers(m.wallpapers, "").length, 3);
  check("case-insensitive", filterWallpapers(m.wallpapers, "EAGLE").map((w) => w.name), [
    "imperial_eagle.jpg",
  ]);
  check("no match", filterWallpapers(m.wallpapers, "zzz"), []);
  check("trims", filterWallpapers(m.wallpapers, "  shani ").map((w) => w.name), ["shani.png"]);
}

// zero-hash spine mapping (sourcePath + size verified via runtime metas)
{
  const spine = [
    { name: "a.png", path: "/s/a.png", size: 100 },
    { name: "b.jpg", path: "/s/b.jpg", size: 200 },
    { name: "twin.png", path: "/s/twin.png", size: 100 },
    { name: "fresh.png", path: "/s/fresh.png", size: 999 },
  ];
  const metas = [
    { hash: "h1", sourcePath: "/s/a.png", size: 100 },
    { hash: "h1", sourcePath: "/s/old-name.png", size: 100 },
    { hash: "h2", sourcePath: "/s/b.jpg", size: 150 },
  ];
  const m = mapSpineHashes(spine, metas);
  const sources = new Set(metas.map((x) => x.sourcePath));
  const sizes = new Set(metas.map((x) => x.size));
  check("exact path+size maps", m.get("/s/a.png"), "h1");
  check("size mismatch does not map", m.has("/s/b.jpg"), false);
  check("twin needs real hash (size match)", needsRealHash(
    { name: "twin.png", path: "/s/twin.png", size: 100 }, m, sources, sizes,
  ), true);
  check("edited file needs real hash (known source)", needsRealHash(
    { name: "b.jpg", path: "/s/b.jpg", size: 200 }, m, sources, sizes,
  ), true);
  check("mapped file needs no hash", needsRealHash(
    { name: "a.png", path: "/s/a.png", size: 100 }, m, sources, sizes,
  ), false);
  check("unknown file needs no hash", needsRealHash(
    { name: "fresh.png", path: "/s/fresh.png", size: 999 }, m, sources, sizes,
  ), false);
  check("placeholder shape", unappliedPlaceholder("/s/fresh.png"), "unapplied:/s/fresh.png");
  check("empty metas", [...mapSpineHashes(spine, []).entries()], []);
  check("empty spine", [...mapSpineHashes([], metas).entries()], []);
}

// placeholder re-resolution (an apply creates runtime metas without
// touching spine stats, so cached `unapplied:` hashes must resolve against
// fresh metas or the gallery stays empty forever)
{
  const cached = [
    { name: "new.png", path: "/s/new.png", hash: `${UNAPPLIED_PREFIX}/s/new.png`, mtime: "t", size: 100 },
    { name: "never.png", path: "/s/never.png", hash: `${UNAPPLIED_PREFIX}/s/never.png`, mtime: "t", size: 200 },
    { name: "old.png", path: "/s/old.png", hash: "o".repeat(64), mtime: "t", size: 300 },
  ];
  const mapping = new Map([["/s/new.png", "n".repeat(64)]]);
  const fixed = resolvePlaceholders(cached, mapping);
  check("placeholder resolves to fresh hash", fixed[0].hash, "n".repeat(64));
  check("resolved entry keeps fields", [fixed[0].name, fixed[0].path, fixed[0].mtime, fixed[0].size], ["new.png", "/s/new.png", "t", 100]);
  check("unmapped placeholder pins", fixed[1].hash, `${UNAPPLIED_PREFIX}/s/never.png`);
  check("real hash untouched", fixed[2].hash, "o".repeat(64));
  check("input not mutated", cached[0].hash, `${UNAPPLIED_PREFIX}/s/new.png`);
  check("empty mapping pins all", resolvePlaceholders(cached, new Map())[0].hash, `${UNAPPLIED_PREFIX}/s/new.png`);
}

// gallery link restored once the placeholder resolves
{
  const entry = [{ sourceHash: "n".repeat(64), variants: [{ name: "blur", group: "effect", path: "/cache/e/new/effect/blur.png" }] }];
  const before = buildModel(
    [{ name: "new.png", path: "/s/new.png", hash: `${UNAPPLIED_PREFIX}/s/new.png` }],
    entry, null,
  );
  check("placeholder shows zero variants", before.wallpapers[0].variantCount, 0);
  const after = buildModel(
    [{ name: "new.png", path: "/s/new.png", hash: "n".repeat(64) }],
    entry, null,
  );
  check("resolved hash shows variants", after.wallpapers[0].variantCount, 1);
  check("variants listed", variantsFor(after, "n".repeat(64)).map((v) => v.name), ["blur"]);
}

// live pinning: live wallpaper (or live variant's parent) sorts first,
// everything else keeps name order
{
  const m = buildModel(SPINE, EFFECTS, CURRENT_WALL);
  check("live wallpaper pinned first", m.wallpapers.map((w) => w.name), [
    "imperial_eagle.jpg",
    "black_dragon.webp",
    "shani.png",
  ]);
  check("pinned keeps live flag", m.wallpapers[0].live, true);
}
{
  const m = buildModel(SPINE, EFFECTS, CURRENT_VAR);
  check("live variant pins its parent", m.wallpapers.map((w) => w.name), [
    "imperial_eagle.jpg",
    "black_dragon.webp",
    "shani.png",
  ]);
  check("parent gains no live flag", m.wallpapers[0].live, false);
}
{
  const m = buildModel(SPINE, EFFECTS, null);
  check("nothing live keeps name order", m.wallpapers.map((w) => w.name), [
    "black_dragon.webp",
    "imperial_eagle.jpg",
    "shani.png",
  ]);
  check("pin target null without current", pinTargetHash(
    ["i".repeat(64)], new Map(), "", "",
  ), null);
}
{
  const vars = new Map([["i".repeat(64), [{ name: "sepia", group: "effect", path: "/cache/sepia.jpg" }]]]);
  check("direct live hash wins", pinTargetHash(
    ["i".repeat(64), "s".repeat(64)], vars, "s".repeat(64), "/cache/sepia.jpg",
  ), "s".repeat(64));
  check("variant path resolves parent", pinTargetHash(
    ["i".repeat(64), "s".repeat(64)], vars, "v".repeat(64), "/cache/sepia.jpg",
  ), "i".repeat(64));
  check("unknown variant path pins nothing", pinTargetHash(
    ["i".repeat(64)], vars, "v".repeat(64), "/cache/gone.jpg",
  ), null);
  check("stale live hash pins nothing", pinTargetHash(
    ["i".repeat(64)], vars, "z".repeat(64), "",
  ), null);
}
{
  // pin survives search filtering (filter preserves model order)
  const m = buildModel(SPINE, EFFECTS, CURRENT_VAR);
  check("filtered pin stays first", filterWallpapers(m.wallpapers, "eagle").map((w) => w.name), [
    "imperial_eagle.jpg",
  ]);
}

// helpers
check("image exts", ["a.png", "b.JPG", "c.webp", "d.jpeg", "e.gif"].every(isImageFile), true);
check("non-image exts", ["a.txt", "a", "a.svg"].some(isImageFile), false);
check("stem", [stemOf("blur-brightness80.png"), stemOf("noext")], ["blur-brightness80", "noext"]);

// contrast-toggle helpers (lib/model additions)
{
  // live wallpaper itself, or the parent of a live promoted variant
  const parent = { name: "p.png", path: "/p", hash: "h", variantCount: 1, live: false };
  const live = { name: "l.png", path: "/l", hash: "l", variantCount: 0, live: true };
  const dead = { name: "d.png", path: "/d", hash: "d", variantCount: 0, live: false };
  check("directly live", isWallpaperLive(live, []), true);
  check("parent of live variant", isWallpaperLive(parent, [
    { name: "v", group: "effect", path: "/c/v", live: true },
  ]), true);
  check("parent of non-live variants", isWallpaperLive(parent, [
    { name: "v", group: "effect", path: "/c/v", live: false },
  ]), false);
  check("neither live", isWallpaperLive(dead, []), false);

  // cached pref lookup → default ON when unqueried
  const prefs = new Map([["h", false]]);
  check("cached off", cachedContrastPref(prefs, "h"), false);
  check("unqueried defaults on", cachedContrastPref(prefs, "missing"), true);
  check("default constant on", DEFAULT_CONTRAST_ENABLED, true);

  // L2 sublabel scope phrase
  check("scope 3 variants", contrastScopeLabel(3), "applies to all 3 variants");
  check("scope 1 variant", contrastScopeLabel(1), "applies to all 1 variant");
  check("scope 0 variants", contrastScopeLabel(0), "no variants yet");

  // isRealHash: the runtime `icons preference` accessor rejects anything
  // that is not 64 lowercase hex, so the GUI must never shell it for a
  // placeholder hash (hover on a never-applied wallpaper).
  check("real hash", isRealHash("a".repeat(64)), true);
  check("real hash (mixed hex)", isRealHash("0123456789abcdef".repeat(4)), true);
  check("placeholder hash", isRealHash(unappliedPlaceholder("/w/x.png")), false);
  check("empty live sentinel", isRealHash(""), false);
  check("short hash", isRealHash("abc123"), false);
  check("uppercase hex rejected", isRealHash("A".repeat(64)), false);
  check("non-hex char rejected", isRealHash(`${"a".repeat(63)}z`), false);
}

if (failures > 0) {
  console.error(`${failures} failure(s)`);
  process.exit(1);
}
console.log("model: all green");
