// Pure unified-diff presentation for the pending-changes pane.
//
// Parses `difflib`-style unified diffs into styled rows (Pango markup).
// Dependency-free with erasable types only so plain node can run it
// (see tests/diff.mjs).

export type DiffLineKind = "file" | "hunk" | "del" | "add" | "ctx";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

export function escapeMarkup(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function parseDiffLines(diff: string): DiffLine[] {
  return diff.split("\n").map((line) => {
    if (line.startsWith("--- ") || line.startsWith("+++ ")) {
      return { kind: "file", text: line } as DiffLine;
    }
    if (line.startsWith("@@")) {
      return { kind: "hunk", text: line } as DiffLine;
    }
    if (line.startsWith("+")) {
      return { kind: "add", text: line } as DiffLine;
    }
    if (line.startsWith("-")) {
      return { kind: "del", text: line } as DiffLine;
    }
    return { kind: "ctx", text: line } as DiffLine;
  });
}

const KIND_COLORS: Record<DiffLineKind, string | null> = {
  file: "#6ea8fe",
  hunk: "#8b93a1",
  del: "#e08585",
  add: "#7bc47f",
  ctx: null,
};

/** Render a unified diff as Pango markup (empty string stays empty). */
export function renderDiffMarkup(diff: string): string {
  if (diff === "") return "";
  return parseDiffLines(diff)
    .map((line) => {
      const color = KIND_COLORS[line.kind];
      const escaped = escapeMarkup(line.text);
      return color ? `<span foreground="${color}">${escaped}</span>` : escaped;
    })
    .join("\n");
}
