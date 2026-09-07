// Display-only {{PLACEHOLDER}} substitution for icon previews.
//
// Mirrors PlaceholderSubstitutionService (non-unsafe mode) with one deliberate
// difference: unresolvable placeholders render UNRESOLVED_FILL instead of
// raising, so the preview never crashes. The authoritative substitution stays
// in ITR; agreement between the two is pinned by
// tests/fixtures/substitution.json (see tests/contract.mjs and the Python
// test_substitution_agreement.py).
//
// Kept dependency-free with erasable types only so plain node can run it.

export const UNRESOLVED_FILL = "url(#icme-unresolved)";

export interface MappingTable {
  [placeholder: string]: string;
}

export interface SchemeTable {
  [token: string]: string;
}

const PLACEHOLDER_RE = /\{\{(\w+)\}\}/g;

export function substitute(
  svg: string,
  mappings: MappingTable,
  scheme: SchemeTable,
): string {
  return svg.replace(PLACEHOLDER_RE, (match: string, name: string) => {
    const token = mappings[name];
    if (token === undefined) return UNRESOLVED_FILL;
    if (token.startsWith("#")) return token;
    const hex = scheme[token];
    return hex === undefined ? UNRESOLVED_FILL : hex;
  });
}
