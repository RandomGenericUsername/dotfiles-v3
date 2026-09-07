// Pure SVG helpers for the preview: shape extraction, offscreen ID-buffer
// rewriting (design D7), unresolved-hatch injection, highlight overlays, and
// widget-to-pixbuf coordinate mapping.
//
// Kept dependency-free with erasable types only so plain node can run it
// (see tests/svg.mjs). GTK/Rsvg pixbuf rendering lives in ui/Preview.tsx.

export interface ShapeInfo {
  /** 1-based index; 0 is reserved for background/transparent. */
  id: number;
  /** Placeholder from fill/stroke, or null for statically painted shapes. */
  placeholder: string | null;
  /** Painted attribute carrying the placeholder: "fill" or "stroke". */
  paintAttr: "fill" | "stroke";
  /** Source text of the shape element (for highlight overlays). */
  element: string;
  /** Tag name (path, rect, circle, …). */
  tag: string;
}

const SHAPE_RE =
  /<(path|rect|circle|ellipse|line|polyline|polygon)\b((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/>|>([\s\S]*?)<\/\1>)/g;

const ATTR_RE = (name: string): RegExp =>
  new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`, "");

const PLACEHOLDER_VALUE_RE = /\{\{(\w+)\}\}/;

function attrValue(element: string, name: string): string | null {
  const match = ATTR_RE(name).exec(element);
  return match ? match[1] : null;
}

function placeholderOf(value: string | null): string | null {
  if (value === null) return null;
  const match = PLACEHOLDER_VALUE_RE.exec(value);
  return match ? match[1] : null;
}

/** Extract top-level shape elements in document order. */
export function extractShapes(svgBody: string): ShapeInfo[] {
  // Paint attributes inherit from the root <svg> element: icons like the
  // power menu set fill="none" there and paint shapes via stroke, so a
  // shape without its own fill attribute must consult the root before the
  // "missing fill paints black" default applies.
  const rootTag = /<svg\b[^>]*>/.exec(svgBody)?.[0] ?? "";
  const rootFill = attrValue(rootTag, "fill");
  const rootStroke = attrValue(rootTag, "stroke");
  const shapes: ShapeInfo[] = [];
  SHAPE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  let id = 0;
  while ((match = SHAPE_RE.exec(svgBody)) !== null) {
    id += 1;
    const element = match[0];
    const fill = attrValue(element, "fill") ?? rootFill;
    const stroke = attrValue(element, "stroke") ?? rootStroke;
    // Fill wins unless explicitly none (SVG default fill is black, so a
    // missing fill attribute still paints).
    const useStroke = fill === "none";
    const placeholder = useStroke ? placeholderOf(stroke) : placeholderOf(fill);
    shapes.push({
      id,
      placeholder,
      paintAttr: useStroke ? "stroke" : "fill",
      element,
      tag: match[1],
    });
  }
  return shapes;
}

/** Unique flat RGB for a shape id (exact values survive the pixbuf path). */
export function idColorFor(id: number): string {
  const r = id & 0xff;
  const g = (id >> 8) & 0xff;
  const b = (id >> 16) & 0xff;
  const hex = (n: number): string => n.toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

/** Decode an ID color back to a shape id; 0 means background/transparent. */
export function shapeIdFromPixel(r: number, g: number, b: number, a: number): number {
  if (a === 0) return 0;
  return r | (g << 8) | (b << 16);
}

function setAttr(element: string, name: string, value: string): string {
  if (ATTR_RE(name).test(element)) {
    return element.replace(ATTR_RE(name), `${name}="${value}"`);
  }
  return element.replace(/(\/>|>[\s\S]*<\/\w+>\s*)$/, ` ${name}="${value}"$1`);
}

function removeAttr(element: string, name: string): string {
  return element.replace(new RegExp(`\\s*\\b${name}\\s*=\\s*"[^"]*"`, ""), "");
}

/**
 * Rewrite every shape's paint in its unique ID color for the offscreen
 * hit-test pass. Structural twin of the visible pass: same geometry,
 * flat opaque colors. Shapes explicitly filled "none" keep no fill and
 * paint their stroke instead; elements with no stroke attribute get
 * stroke="none" so no hairline bleeds into neighboring ids.
 */
export function rewriteWithIdColors(svgBody: string): string {
  const shapes = extractShapes(svgBody);
  let out = svgBody;
  for (const shape of shapes) {
    const color = idColorFor(shape.id);
    let element = shape.element;
    if (shape.paintAttr === "stroke") {
      element = setAttr(element, "stroke", color);
      element = setAttr(element, "stroke-opacity", "1");
    } else {
      element = setAttr(element, "fill", color);
      element = setAttr(element, "fill-opacity", "1");
      if (attrValue(shape.element, "stroke") === null) {
        element = setAttr(element, "stroke", "none");
      } else {
        element = setAttr(element, "stroke", color);
      }
    }
    out = out.replace(shape.element, () => element);
  }
  return out;
}

const HATCH_DEFS =
  `<defs><pattern id="icme-unresolved" width="12" height="12" ` +
  `patternTransform="rotate(45)" patternUnits="userSpaceOnUse">` +
  `<rect width="12" height="12" fill="#3a3f47"/>` +
  `<line x1="0" y1="0" x2="0" y2="12" stroke="#e0a45e" stroke-width="3"/>` +
  `</pattern></defs>`;

/** Inject the hatch pattern backing UNRESOLVED_FILL into a substituted body. */
export function withHatchDefs(substitutedSvg: string): string {
  return substitutedSvg.replace(/<svg\b[^>]*>/, (open) => `${open}${HATCH_DEFS}`);
}

/**
 * Append an outline duplicate of one shape for hover/selection highlight.
 * Keeps the shape's geometry, drops its paint, strokes in the given color.
 */
export function withHighlight(
  substitutedSvg: string,
  shape: ShapeInfo,
  color: string,
  strokeWidth: number,
): string {
  let element = removeAttr(shape.element, "fill");
  element = removeAttr(element, "stroke");
  element = removeAttr(element, "fill-opacity");
  element = removeAttr(element, "stroke-opacity");
  element = setAttr(element, "fill", "none");
  element = setAttr(element, "stroke", color);
  element = setAttr(element, "stroke-width", String(strokeWidth));
  return substitutedSvg.replace(/<\/svg\s*>\s*$/, () => `${element}</svg>`);
}

export interface PixbufPoint {
  px: number;
  py: number;
}

/**
 * Map a widget click to pixbuf pixels for a CONTAIN-fit picture
 * (aspect-preserving, centered). Returns null when the click lands on
 * letterbox bars.
 */
export function mapClickToPixbuf(
  x: number,
  y: number,
  allocWidth: number,
  allocHeight: number,
  bufWidth: number,
  bufHeight: number,
): PixbufPoint | null {
  if (allocWidth <= 0 || allocHeight <= 0 || bufWidth <= 0 || bufHeight <= 0) {
    return null;
  }
  const scale = Math.min(allocWidth / bufWidth, allocHeight / bufHeight);
  const contentWidth = bufWidth * scale;
  const contentHeight = bufHeight * scale;
  const offsetX = (allocWidth - contentWidth) / 2;
  const offsetY = (allocHeight - contentHeight) / 2;
  const px = Math.floor((x - offsetX) / scale);
  const py = Math.floor((y - offsetY) / scale);
  if (px < 0 || py < 0 || px >= bufWidth || py >= bufHeight) return null;
  return { px, py };
}

export interface UsageCount {
  shapes: number;
  variants: number;
}

/**
 * Count shapes using a placeholder across variant bodies: total shapes and
 * the number of variants containing at least one such shape.
 */
export function usageCount(svgBodies: string[], placeholder: string): UsageCount {
  let shapes = 0;
  let variants = 0;
  for (const body of svgBodies) {
    const hits = extractShapes(body).filter((shape) => shape.placeholder === placeholder);
    if (hits.length > 0) variants += 1;
    shapes += hits.length;
  }
  return { shapes, variants };
}
