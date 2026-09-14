// Clipboard item model + pure parsing/preview helpers (no GJS imports), so
// the node test runner can exercise them alongside the event-bus core.

export type ItemKind = "text" | "image" | "link" | "code" | "color" | "emoji";

export interface ClipboardItem {
  hash: string;
  kind: ItemKind;
  timestamp: number;
  favorite: boolean;
  text: string | null;
  path: string | null;
}

const KNOWN_KINDS: ReadonlySet<string> = new Set([
  "text",
  "image",
  "link",
  "code",
  "color",
  "emoji",
]);

//: Payload of a `clipboard.update` DomainEvent (contract `topics`).
export interface ClipboardUpdatePayload {
  type: string;
  hash: string;
  path: string;
  preview: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function asKind(value: unknown): ItemKind {
  return typeof value === "string" && KNOWN_KINDS.has(value) ? (value as ItemKind) : "text";
}

/** Parse the history document tolerantly; malformed records are skipped. */
export function parseHistory(raw: string): ClipboardItem[] {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!isRecord(data) || !Array.isArray(data.items)) return [];
  const items: ClipboardItem[] = [];
  for (const record of data.items) {
    if (!isRecord(record)) continue;
    const hash = record.hash;
    const timestamp = record.timestamp;
    if (typeof hash !== "string" || typeof timestamp !== "number") continue;
    items.push({
      hash,
      kind: asKind(record.kind),
      timestamp,
      favorite: record.favorite === true,
      text: typeof record.text === "string" ? record.text : null,
      path: typeof record.path === "string" ? record.path : null,
    });
  }
  items.sort((a, b) => b.timestamp - a.timestamp);
  return items;
}

/** Build a live item from a `clipboard.update` payload. */
export function itemFromPayload(payload: ClipboardUpdatePayload): ClipboardItem {
  const kind = asKind(payload.type);
  return {
    hash: payload.hash,
    kind,
    timestamp: Date.now() / 1000,
    favorite: false,
    text: kind === "image" ? null : payload.preview,
    path: kind === "image" ? payload.path : null,
  };
}

/** Stable key for deduping live updates against hydrated history. */
export function itemKey(item: ClipboardItem): string {
  return `${item.kind}:${item.hash}`;
}

/** Symbolic icon name per kind. */
export function kindIcon(kind: ItemKind): string {
  switch (kind) {
    case "image":
      return "image-x-generic-symbolic";
    case "link":
      return "insert-link-symbolic";
    case "code":
      return "text-x-script-symbolic";
    case "color":
      return "applications-graphics-symbolic";
    case "emoji":
      return "face-smile-symbolic";
    default:
      return "text-x-generic-symbolic";
  }
}

/** One-line card title: a color swatch label, a link, or the preview text. */
export function itemTitle(item: ClipboardItem): string {
  if (item.kind === "image") return "Image";
  const text = (item.text ?? "").trim();
  if (text.length === 0) return "(empty)";
  const firstLine = text.split("\n")[0];
  return firstLine.length > 120 ? `${firstLine.slice(0, 119)}\u2026` : firstLine;
}

/** Case-insensitive substring filter over text-like items. */
export function matchesQuery(item: ClipboardItem, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return true;
  if (item.kind === "image") return "image".includes(needle);
  return (item.text ?? "").toLowerCase().includes(needle);
}
