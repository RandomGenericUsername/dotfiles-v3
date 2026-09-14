// Unit tests for lib/model.ts. Run with plain node:
// `node tests/model.mjs` from the tool directory.
import {
  buildModel,
  filterWallpapers,
  isImageFile,
  mapSpineHashes,
  needsRealHash,
  stemOf,
  unappliedPlaceholder,
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

// helpers
check("image exts", ["a.png", "b.JPG", "c.webp", "d.jpeg", "e.gif"].every(isImageFile), true);
check("non-image exts", ["a.txt", "a", "a.svg"].some(isImageFile), false);
check("stem", [stemOf("blur-brightness80.png"), stemOf("noext")], ["blur-brightness80", "noext"]);

if (failures > 0) {
  console.error(`${failures} failure(s)`);
  process.exit(1);
}
console.log("model: all green");
