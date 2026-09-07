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

import type {
  MergedEntry,
  PendingEdit,
  VocabularyPendingEdit,
} from "./model.ts";
import { pendingOldValue } from "./model.ts";

export interface PendingRow {
  header: string | null;
  html: string;
}

export interface ShowView {
  groups: {
    group: string;
    variants: { variant: string; mappings: MergedEntry[] }[];
  }[];
}

function withoutKey<T>(map: ReadonlyMap<string, T>, key: string): Map<string, T> {
  const next = new Map(map);
  next.delete(key);
  return next;
}

function entriesFor(
  show: ShowView,
  group: string,
  variant: string,
): MergedEntry[] {
  return (
    show.groups
      .find((g) => g.group === group)
      ?.variants.find((v) => v.variant === variant)?.mappings ?? []
  );
}

/**
 * Semantic pending rows: one old -> new row per placeholder with the old
 * source named (vocabulary default vs on-disk entry). Never writes.
 */
export function describePending(
  show: ShowView,
  groupName: string,
  activeVariant: string,
  pending: ReadonlyMap<string, PendingEdit>,
  vocabPending: ReadonlyMap<string, VocabularyPendingEdit>,
): PendingRow[] {
  const rows: PendingRow[] = [];
  let lastHeader: string | null = null;
  const emit = (header: string, html: string): void => {
    rows.push({ header: header === lastHeader ? null : header, html });
    lastHeader = header;
  };
  const oldHtml = (
    entries: MergedEntry[],
    group: string,
    variant: string,
    placeholder: string,
    pend: ReadonlyMap<string, PendingEdit>,
    vocab: ReadonlyMap<string, VocabularyPendingEdit>,
  ): string => {
    const old = pendingOldValue(entries, group, variant, placeholder, pend, vocab);
    if (old.token === null) return '<i>unresolved</i>';
    return (
      '<s>' + escapeMarkup(old.token) + '</s>' +
      (old.fromVocabulary ? ' (vocabulary default)' : '')
    );
  };
  for (const [key, edit] of pending) {
    const variant = edit.variant ?? activeVariant;
    const entries = entriesFor(show, edit.group, variant);
    const others = withoutKey(pending, key);
    const header =
      edit.variant === null
        ? edit.group + '.color_mappings'
        : edit.group + '.variants[' + edit.variant + '].color_mappings';
    emit(
      header,
      '  ' + escapeMarkup(edit.placeholder) + ': ' +
        oldHtml(entries, edit.group, variant, edit.placeholder, others, vocabPending) +
        ' → <b>' + escapeMarkup(edit.token) + '</b>',
    );
  }
  for (const [placeholder, edit] of vocabPending) {
    const entries = entriesFor(show, groupName, activeVariant);
    const old = pendingOldValue(
      entries, groupName, activeVariant, placeholder,
      pending, withoutKey(vocabPending, placeholder),
    );
    const oldText =
      old.token === null ? '<i>unresolved</i>' : '<s>' + escapeMarkup(old.token) + '</s>';
    emit(
      'defaults',
      '  ' + escapeMarkup(placeholder) + ': ' + oldText +
        ' → <b>' + escapeMarkup(edit.token) + '</b>',
    );
  }
  return rows;
}

/** Render semantic rows as Pango markup (empty stays empty). */
export function renderPendingMarkup(rows: PendingRow[]): string {
  return rows
    .map((row) => {
      const parts: string[] = [];
      if (row.header !== null) {
        parts.push('<span foreground="#6ea8fe">' + escapeMarkup(row.header) + '</span>');
      }
      parts.push(
        row.html
          .replaceAll('<s>', '<span foreground="#e08585"><s>')
          .replaceAll('</s>', '</s></span>')
          .replaceAll('<b>', '<span foreground="#7bc47f"><b>')
          .replaceAll('</b>', '</b></span>'),
      );
      return parts.join(String.fromCharCode(10));
    })
    .join(String.fromCharCode(10));
}
