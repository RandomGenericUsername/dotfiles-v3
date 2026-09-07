// Unit tests for lib/svg.ts. Run with plain node:
// `node tests/svg.mjs` from the tool directory.
import {
  extractShapes,
  idColorFor,
  mapClickToPixbuf,
  rewriteWithIdColors,
  shapeIdFromPixel,
  usageCount,
  withHatchDefs,
  withHighlight,
} from "../lib/svg.ts";

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

const BODY =
  '<svg viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/2000/svg">' +
  '<rect x="1" y="2" width="3" height="4" fill="{{COLOR_FOREGROUND}}"/>' +
  '<path d="M0 0H10" stroke="{{COLOR_ACCENT}}" fill="none"/>' +
  '<circle cx="5" cy="5" r="2" fill="#123456"/>' +
  "</svg>";

// extraction
const shapes = extractShapes(BODY);
check("extracts three shapes", shapes.length, 3);
check("shape ids sequential", shapes.map((s) => s.id), [1, 2, 3]);
check("fill placeholder", shapes[0].placeholder, "COLOR_FOREGROUND");
check("fill paintAttr", shapes[0].paintAttr, "fill");
check("stroke placeholder with fill none", shapes[1].placeholder, "COLOR_ACCENT");
check("stroke paintAttr", shapes[1].paintAttr, "stroke");
check("static shape has null placeholder", shapes[2].placeholder, null);

// id colors round-trip
for (const shape of shapes) {
  const color = idColorFor(shape.id);
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/.exec(color);
  const back = shapeIdFromPixel(parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16), 255);
  check(`id ${shape.id} round-trips`, back, shape.id);
}
check("transparent decodes to 0", shapeIdFromPixel(200, 100, 50, 0), 0);
check("id colors unique", new Set(shapes.map((s) => idColorFor(s.id))).size, 3);

// id rewriting preserves structure, paints flat ids
const idSvg = rewriteWithIdColors(BODY);
check("no placeholders survive id pass", /\{\{/.test(idSvg), false);
check("no hatch needed: no url( refs", /url\(#/.test(idSvg), false);
const reshapes = extractShapes(idSvg);
check("id pass keeps shape count", reshapes.length, 3);
check("id pass keeps tags", reshapes.map((s) => s.tag), ["rect", "path", "circle"]);

// hatch injection
const hatched = withHatchDefs('<svg viewBox="0 0 1 1"><rect width="1" height="1"/></svg>');
check("hatch defs injected", hatched.includes('id="icme-unresolved"'), true);

// highlight appends an outline duplicate
const highlighted = withHighlight('<svg viewBox="0 0 1 1"></svg>', shapes[0], "#6ea8fe", 24);
check("highlight strokes accent", highlighted.includes('stroke="#6ea8fe"'), true);
check("highlight has no fill", highlighted.includes('fill="none"'), true);
check("highlight keeps geometry", highlighted.includes('x="1"'), true);
check("highlight leaks no placeholders", /\{\{/.test(highlighted), false);

// click mapping: 200x100 alloc, 100x100 pixbuf -> contain centers, side bars
check("center maps", mapClickToPixbuf(100, 50, 200, 100, 100, 100), { px: 50, py: 50 });
check("side bar is null", mapClickToPixbuf(10, 50, 200, 100, 100, 100), null);
check("outside is null", mapClickToPixbuf(500, 500, 200, 200, 100, 100), null);
check("degenerate is null", mapClickToPixbuf(10, 10, 0, 100, 100, 100), null);

// usage counts span bodies but only variants using the placeholder
const OTHER =
  '<svg viewBox="0 0 1 1"><path d="M0 0H1" fill="{{COLOR_ACCENT}}"/>' +
  '<rect x="0" y="0" width="1" height="1" fill="{{COLOR_ACCENT}}"/></svg>';
check(
  "usage counts shapes and variants",
  usageCount([BODY, OTHER], "COLOR_ACCENT"),
  { shapes: 3, variants: 2 },
);
check(
  "unused placeholder counts zero",
  usageCount([BODY, OTHER], "NOPE"),
  { shapes: 0, variants: 0 },
);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("svg cases agree");
}
